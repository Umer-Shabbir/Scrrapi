"""Deep crawl of a business website for contact details.

The shallow path (`place_enrichment`) fetches the home page and takes the first
email off it. That finds the address on maybe half of sites, because the home
page is a hero image and a phone number -- the email lives on /contact, the
second location's number lives on /locations, and the social profiles live in a
footer that only renders on inner pages.

This module walks the site instead. Given the URL Maps handed us it:

1. reads `robots.txt` for the crawl rules and for any `Sitemap:` lines,
2. seeds a frontier with the home page, the sitemap's URLs, and every internal
   link it finds as it goes,
3. orders that frontier by how likely a URL is to hold contact details --
   `/contact`, `/impressum`, `/about`, `/team` before `/blog/2019/why-we-love-pipes`,
4. fetches pages a few at a time until the page budget or the deadline runs out,
5. and merges the emails, phone numbers and social profiles found on each.

Budgets, not completeness, are the design constraint: this runs once per scraped
place, so a job with 2000 places pays this cost 2000 times. Every dimension is
bounded -- pages, depth, wall-clock, response size, concurrency -- and the whole
thing degrades to "whatever it had found when the budget ran out" rather than
failing the enrichment.

Politeness: `robots.txt` is honoured by default (`deep_crawl_respect_robots`),
concurrency is capped so a small site never sees more than a handful of
simultaneous requests, and nothing here retries -- a page that errors is simply
skipped.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.scraping.common.email_miner import extract_emails, is_valid_email
from app.scraping.common.phone_miner import extract_phones, phone_key
from app.scraping.common.social_miner import extract_social_links
from app.scraping.common.structured_data import extract_structured_contacts

logger = logging.getLogger(__name__)

# URL path fragments that mark a page as likely to carry contact details, with
# the weight they add. Deliberately multilingual: the address on a German site is
# on /impressum (where it is a legal requirement), on a Spanish one it is
# /contacto, and a crawler that only knows the English words wastes its whole
# page budget on the blog.
PAGE_HINTS: list[tuple[tuple[str, ...], int]] = [
    (
        (
            "contact", "contacts", "contact-us", "contactus", "contact_us",
            "kontakt", "kontakta", "contacto", "contatti", "contato", "contactez",
            "nous-contacter", "iletisim", "connect", "get-in-touch", "getintouch",
            "reach-us", "enquiry", "enquiries", "inquiry", "impressum", "imprint",
            "mentions-legales", "aviso-legal", "colofon",
        ),
        100,
    ),
    (
        (
            "about", "about-us", "aboutus", "about_us", "ueber-uns", "uber-uns",
            "quienes-somos", "chi-siamo", "a-propos", "om-oss", "team", "our-team",
            "staff", "people", "management", "leadership", "meet-the-team",
        ),
        70,
    ),
    (
        (
            "location", "locations", "branch", "branches", "office", "offices",
            "stores", "store-locator", "find-us", "visit", "directions",
            "support", "help", "customer-service", "service", "book", "booking",
            "appointment", "quote", "estimate", "franchise",
        ),
        45,
    ),
    (
        # Rarely the *intended* contact page, but on a small site the legal
        # boilerplate is often the only place a real address is written out.
        ("privacy", "terms", "legal", "datenschutz", "faq", "careers", "jobs"),
        20,
    ),
]

# Never worth a request: binaries, assets, and pages that exist to change state.
SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".bmp",
    ".css", ".js", ".json", ".zip", ".rar", ".7z", ".gz", ".tar", ".mp3", ".mp4",
    ".avi", ".mov", ".wmv", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".exe", ".dmg", ".apk", ".woff", ".woff2", ".ttf", ".eot", ".rss", ".csv",
)

SKIP_PATH_MARKERS = (
    "/wp-admin", "/wp-json", "/wp-content", "/cdn-cgi/", "/cart", "/checkout",
    "/basket", "/my-account", "/login", "/signin", "/sign-in", "/register",
    "/logout", "/feed", "add-to-cart", "/comment", "?replytocom",
)

# A page that is 8MB of inlined base64 is not going to yield a phone number that
# the first 2MB didn't, and parsing it costs real time.
PARSE_CHARS_CAP = 400_000

# Per-result caps. A staff directory can list two hundred addresses; the columns
# these end up in are a lead's contact details, not a mailing list.
MAX_EMAILS = 25
MAX_PHONES = 15
MAX_SOCIALS_PER_NETWORK = 3


@dataclass(frozen=True)
class CrawlBudget:
    """Everything that bounds one site crawl. Built from settings by
    `budget_from_settings`, so a caller normally never constructs this."""

    max_pages: int = 25
    max_depth: int = 3
    total_timeout_s: float = 45.0
    request_timeout_s: float = 10.0
    concurrency: int = 4
    max_page_bytes: int = 2_000_000
    use_sitemap: bool = True
    respect_robots: bool = True


@dataclass
class SiteContacts:
    """What a crawl found. Empty lists, never `None` -- a site with nothing on it
    is the normal case, not an error."""

    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    socials: dict[str, list[str]] = field(default_factory=dict)
    pages_crawled: int = 0
    pages_discovered: int = 0
    #: True when the budget ran out with URLs still queued -- i.e. the site has
    #: more pages than were looked at.
    truncated: bool = False

    def is_empty(self) -> bool:
        return not (self.emails or self.phones or self.socials)


def budget_from_settings(max_pages: int | None = None) -> CrawlBudget:
    """Build a budget from deployment config, with the runtime page limit (the
    one on the Settings page) overriding `deep_crawl_max_pages`."""
    settings = get_settings()
    return CrawlBudget(
        max_pages=max_pages if max_pages is not None else settings.deep_crawl_max_pages,
        max_depth=settings.deep_crawl_max_depth,
        total_timeout_s=settings.deep_crawl_timeout_s,
        request_timeout_s=settings.deep_crawl_request_timeout_s,
        concurrency=settings.deep_crawl_concurrency,
        max_page_bytes=settings.deep_crawl_max_page_bytes,
        use_sitemap=settings.deep_crawl_use_sitemap,
        respect_robots=settings.deep_crawl_respect_robots,
    )


async def crawl_site(
    start_url: str,
    *,
    budget: CrawlBudget | None = None,
    client: httpx.AsyncClient | None = None,
) -> SiteContacts:
    """Crawl `start_url`'s site and return every contact detail found.

    Never raises for anything the network does: a dead host, a redirect off-site,
    a 403 on every page all come back as an empty `SiteContacts`. Pass `client`
    to reuse a connection pool (or to inject a mock transport in tests).
    """
    budget = budget or budget_from_settings()

    if client is not None:
        return await _crawl(start_url, budget, client)

    settings = get_settings()
    headers = {"User-Agent": settings.default_user_agent} if settings.default_user_agent else {}
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=budget.request_timeout_s, headers=headers
    ) as owned_client:
        return await _crawl(start_url, budget, owned_client)


async def _crawl(start_url: str, budget: CrawlBudget, client: httpx.AsyncClient) -> SiteContacts:
    contacts = SiteContacts()
    deadline = time.monotonic() + budget.total_timeout_s

    base_host = _host_of(start_url)
    if not base_host:
        return contacts

    robots = await _load_robots(client, start_url, budget) if budget.respect_robots else None
    user_agent = client.headers.get("User-Agent", "*")

    frontier: dict[str, tuple[int, int]] = {}  # url -> (score, depth)
    visited: set[str] = set()

    _offer(frontier, visited, start_url, base_host, depth=0, budget=budget)
    if budget.use_sitemap:
        for url in await _sitemap_urls(client, start_url, robots, budget, deadline):
            _offer(frontier, visited, url, base_host, depth=1, budget=budget)

    while frontier and len(visited) < budget.max_pages:
        remaining_time = deadline - time.monotonic()
        if remaining_time <= 0:
            logger.info("deep crawl hit its time budget", extra={"host": base_host})
            break

        batch = _take_batch(frontier, min(budget.concurrency, budget.max_pages - len(visited)))
        if not batch:
            break

        for url, _ in batch:
            visited.add(url)

        pages = await asyncio.gather(
            *(
                _fetch_page(client, url, budget, robots, user_agent)
                for url, _ in batch
            )
        )

        for (_queued_url, depth), page in zip(batch, pages, strict=True):
            if page is None:
                continue
            html, final_url = page
            contacts.pages_crawled += 1
            _absorb(contacts, html, final_url)

            if depth + 1 > budget.max_depth:
                continue
            for link in _links(html, final_url):
                _offer(frontier, visited, link, base_host, depth=depth + 1, budget=budget)

    contacts.pages_discovered = len(visited) + len(frontier)
    contacts.truncated = bool(frontier)
    _finalize(contacts, base_host)

    logger.info(
        "deep crawl finished",
        extra={
            "host": base_host,
            "pages_crawled": contacts.pages_crawled,
            "pages_discovered": contacts.pages_discovered,
            "emails": len(contacts.emails),
            "phones": len(contacts.phones),
            "networks": sorted(contacts.socials),
            "truncated": contacts.truncated,
        },
    )
    return contacts


# --------------------------------------------------------------------------- #
# Fetching
# --------------------------------------------------------------------------- #


async def _fetch_page(
    client: httpx.AsyncClient,
    url: str,
    budget: CrawlBudget,
    robots: RobotFileParser | None,
    user_agent: str,
) -> tuple[str, str] | None:
    """`(html, final_url)` for one page, or `None` if it isn't usable.

    Not usable covers: disallowed by robots, a transport error, a non-2xx, a
    non-HTML content type, and a response larger than the size cap (which is
    checked on the header first so an 80MB video doesn't get buffered on the way
    to being rejected).
    """
    if robots is not None and not robots.can_fetch(user_agent, url):
        return None

    try:
        response = await client.get(url, timeout=budget.request_timeout_s)
    except (httpx.HTTPError, UnicodeDecodeError):
        return None

    if response.status_code >= 400:
        return None

    content_type = response.headers.get("content-type", "").lower()
    if content_type and "html" not in content_type and "xml" not in content_type:
        return None

    declared = response.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > budget.max_page_bytes:
        return None
    if len(response.content) > budget.max_page_bytes:
        return None

    try:
        return response.text[:PARSE_CHARS_CAP], str(response.url)
    except (UnicodeDecodeError, ValueError):
        return None


async def _load_robots(
    client: httpx.AsyncClient, start_url: str, budget: CrawlBudget
) -> RobotFileParser | None:
    """Fetch and parse `robots.txt`. A missing or unreadable file means "no rules",
    which is the standard's own default -- not "crawl nothing"."""
    parser = RobotFileParser()
    robots_url = urljoin(_origin(start_url), "/robots.txt")
    try:
        response = await client.get(robots_url, timeout=budget.request_timeout_s)
    except httpx.HTTPError:
        parser.parse([])
        return parser

    if response.status_code >= 400:
        parser.parse([])
        return parser

    parser.parse(response.text.splitlines())
    return parser


async def _sitemap_urls(
    client: httpx.AsyncClient,
    start_url: str,
    robots: RobotFileParser | None,
    budget: CrawlBudget,
    deadline: float,
) -> list[str]:
    """URLs advertised by the site's own sitemap.

    This is what makes "every page" mean something on a site whose navigation
    hides the contact page behind a hamburger menu rendered in JavaScript: the
    sitemap lists it regardless. Sitemap *indexes* are followed one level deep,
    which covers the usual `sitemap_index.xml -> page-sitemap.xml` shape.
    """
    candidates: list[str] = []
    if robots is not None:
        candidates.extend(robots.site_maps() or [])
    origin = _origin(start_url)
    candidates.extend(
        urljoin(origin, path) for path in ("/sitemap.xml", "/sitemap_index.xml")
    )

    urls: list[str] = []
    seen_sitemaps: set[str] = set()
    queue = list(dict.fromkeys(candidates))
    followed_indexes = 0

    while queue and len(urls) < budget.max_pages * 4:
        if time.monotonic() >= deadline:
            break
        sitemap_url = queue.pop(0)
        if sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap_url)

        try:
            response = await client.get(sitemap_url, timeout=budget.request_timeout_s)
        except httpx.HTTPError:
            continue
        if response.status_code >= 400:
            continue

        body = response.text[:PARSE_CHARS_CAP]
        locations = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body, re.IGNORECASE)
        is_index = "<sitemapindex" in body[:2000].lower()

        if is_index and followed_indexes < 3:
            followed_indexes += 1
            queue.extend(locations[:10])
            continue
        urls.extend(locations)

    return urls


# --------------------------------------------------------------------------- #
# Frontier
# --------------------------------------------------------------------------- #


def _offer(
    frontier: dict[str, tuple[int, int]],
    visited: set[str],
    url: str,
    base_host: str,
    *,
    depth: int,
    budget: CrawlBudget,
) -> None:
    """Add `url` to the frontier if it's on-site, crawlable and not already known.

    A URL already queued at a greater depth is re-scored at the shallower one:
    the same contact page is often linked from both the footer (depth 1) and a
    blog post (depth 3), and the depth it is *reachable* at is the honest one.
    """
    normalized = _normalize_url(url)
    if not normalized or normalized in visited or depth > budget.max_depth:
        return
    if not _same_site(normalized, base_host) or not _is_crawlable(normalized):
        return

    score = _score(normalized, depth)
    existing = frontier.get(normalized)
    if existing is None or score > existing[0]:
        frontier[normalized] = (score, depth)


def _take_batch(frontier: dict[str, tuple[int, int]], size: int) -> list[tuple[str, int]]:
    """Pop the `size` highest-scoring URLs, removing them from the frontier."""
    if size <= 0:
        return []
    ranked = sorted(frontier.items(), key=lambda item: (-item[1][0], item[1][1], item[0]))
    batch = [(url, meta[1]) for url, meta in ranked[:size]]
    for url, _ in batch:
        frontier.pop(url, None)
    return batch


def _score(url: str, depth: int) -> int:
    """How promising a URL looks. Higher is crawled first.

    Path hints dominate, depth breaks ties: an unremarkable page linked from the
    home page still beats an unremarkable page four clicks in, and the home page
    itself (empty path) is worth a bump because it carries the footer every other
    page's contact block is copied from.
    """
    path = urlsplit(url).path.lower()
    score = -depth * 5

    if path in ("", "/"):
        score += 60
    for keywords, weight in PAGE_HINTS:
        if any(_path_contains(path, keyword) for keyword in keywords):
            score += weight
            break

    # Dated archive paths (/2019/07/...) are blog posts; they crowd out
    # everything else on a site that has been running a news section for years.
    if re.search(r"/(19|20)\d{2}/", path):
        score -= 40
    return score


def _path_contains(path: str, keyword: str) -> bool:
    """Whether a path segment matches `keyword` as a word, not as a substring.

    Substring matching puts `/products/telecontactor-relays` above the real
    contact page, and `/services/` above everything because it contains "service".
    """
    return bool(re.search(rf"(?:^|[/\-_.]){re.escape(keyword)}(?:$|[/\-_.])", path))


def _is_crawlable(url: str) -> bool:
    split = urlsplit(url)
    if split.scheme not in ("http", "https"):
        return False
    path = split.path.lower()
    if path.endswith(SKIP_EXTENSIONS):
        return False
    haystack = f"{path}?{split.query}".lower()
    return not any(marker in haystack for marker in SKIP_PATH_MARKERS)


def _same_site(url: str, base_host: str) -> bool:
    """Same site, generously: apex vs `www`, and subdomains in either direction.

    No public-suffix list involved, so this can't be fooled into treating
    `example.co.uk` and `other.co.uk` as one site -- it only ever relates hosts
    to the one the crawl actually started on.
    """
    host = _host_of(url)
    if not host:
        return False
    return host == base_host or host.endswith(f".{base_host}") or base_host.endswith(f".{host}")


def _normalize_url(url: str) -> str:
    """Drop the fragment and normalize the trailing slash, so `/contact`,
    `/contact/` and `/contact#form` are one page and not three requests."""
    cleaned, _ = urldefrag(url.strip())
    if not cleaned:
        return ""
    split = urlsplit(cleaned)
    if not split.scheme or not split.netloc:
        return ""

    path = split.path or "/"
    if len(path) > 1:
        path = path.rstrip("/") or "/"
    host = split.netloc.lower()
    return f"{split.scheme.lower()}://{host}{path}" + (f"?{split.query}" if split.query else "")


def _host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def _origin(url: str) -> str:
    split = urlsplit(url)
    return f"{split.scheme or 'https'}://{split.netloc}"


def _links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            continue
        links.append(urljoin(base_url, href))
    return links


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #


def _absorb(contacts: SiteContacts, html: str, url: str) -> None:
    """Merge one page's contact details into the running result."""
    soup = BeautifulSoup(html, "html.parser")
    # Script and style bodies are stripped before the text scan: they are full of
    # timestamps, ids and colour values that read as phone numbers. Emails and
    # social URLs are matched against the raw markup instead, where an inlined
    # config object is a legitimate hiding place for them.
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)

    structured = extract_structured_contacts(html)

    _extend(contacts.emails, extract_emails(html), MAX_EMAILS, key=str.lower)
    _extend(
        contacts.emails,
        [value for value in structured["emails"] if is_valid_email(value)],
        MAX_EMAILS,
        key=str.lower,
    )

    _extend(contacts.phones, extract_phones(html, text), MAX_PHONES, key=phone_key)
    _extend(contacts.phones, structured["phones"], MAX_PHONES, key=phone_key)

    for network, urls in extract_social_links(html).items():
        bucket = contacts.socials.setdefault(network, [])
        _extend(bucket, urls, MAX_SOCIALS_PER_NETWORK, key=str.lower)

    if structured["socials"]:
        for network, urls in extract_social_links(" ".join(structured["socials"])).items():
            bucket = contacts.socials.setdefault(network, [])
            _extend(bucket, urls, MAX_SOCIALS_PER_NETWORK, key=str.lower)


def _extend(target: list[str], values: list[str], cap: int, *, key) -> None:
    """Append what's new, keeping first-seen order, up to `cap`."""
    existing = {key(value) for value in target}
    for value in values:
        if len(target) >= cap:
            return
        identity = key(value)
        if not identity or identity in existing:
            continue
        existing.add(identity)
        target.append(value)


def _finalize(contacts: SiteContacts, base_host: str) -> None:
    """Put the business's own addresses first.

    A page footer routinely carries the web designer's address, a booking
    platform's support address, or a shared inbox at a franchise HQ. An address
    at the site's own domain is the one the lead is reached at, so it leads --
    everything else keeps its discovery order behind it.
    """
    own = [email for email in contacts.emails if _email_matches_host(email, base_host)]
    others = [email for email in contacts.emails if email not in own]
    contacts.emails = own + others
    contacts.socials = {
        network: urls for network, urls in sorted(contacts.socials.items()) if urls
    }


def _email_matches_host(email: str, base_host: str) -> bool:
    domain = email.rpartition("@")[2].lower().removeprefix("www.")
    if not domain:
        return False
    return domain == base_host or domain.endswith(f".{base_host}") or base_host.endswith(
        f".{domain}"
    )
