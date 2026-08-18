"""Finds/validates a business's website, or searches Startpage when the listing has none.

Legacy equivalent: WebMiner.GetWeb / FindCorrectWeb / SearchWebOnStartpage.
"""

import logging
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10.0

# Startpage's "no-JS" results page: plain HTML, and organic result links point
# straight at the destination rather than bouncing through startpage.com like
# Google's `/url?q=` redirects do -- so this can be scraped with a plain HTTP
# GET, no browser needed.
STARTPAGE_SEARCH_URL = "https://www.startpage.com/sp/search"

# Directory/social/aggregator domains that routinely outrank a small
# business's own site in search results. Never worth returning as "the"
# website even when they're the top hit -- these are listing pages *about*
# the business, not the business's own site.
SKIP_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "yelp.com",
    "yellowpages.com",
    "bbb.org",
    "mapquest.com",
    "tripadvisor.com",
    "indeed.com",
    "glassdoor.com",
    "foursquare.com",
    "google.com",
    "bing.com",
    "startpage.com",
    "youtube.com",
    "pinterest.com",
    "angi.com",
    "thumbtack.com",
    "nextdoor.com",
    "reddit.com",
    "wikipedia.org",
}


async def get_website(candidate_url: str, *, client: httpx.AsyncClient | None = None) -> str | None:
    """Confirm a candidate URL from a listing actually resolves/loads.

    Returns the final URL after redirects (so `http://` -> `https://` and
    bare-domain -> `www.` bounces resolve to the canonical form the browser
    would land on), or `None` if the request errors out entirely or comes
    back with a 4xx/5xx.

    Pass `client` in tests to inject a mocked transport; production callers
    can leave it unset and a short-lived client (with the configured spoofed
    UA) is used.
    """
    if not candidate_url or not candidate_url.strip():
        return None

    url = _normalize_url(candidate_url)
    if client is not None:
        return await _fetch_final_url(url, client)

    async with _default_client() as owned_client:
        return await _fetch_final_url(url, owned_client)


async def search_website_on_startpage(
    business_name: str, location: str, *, client: httpx.AsyncClient | None = None
) -> str | None:
    """When a listing has no website, search `<business_name> <location>` on Startpage.

    Returns the best candidate: the first organic result whose domain isn't a
    known directory/social site (`SKIP_DOMAINS`) and that itself passes
    `get_website` -- so the caller never gets back a link that's already dead.
    Returns `None` if the search fails or nothing survives filtering.
    """
    query = " ".join(part.strip() for part in (business_name, location) if part.strip())
    if not query:
        return None

    if client is not None:
        html = await _fetch_startpage_html(query, client)
    else:
        async with _default_client() as owned_client:
            html = await _fetch_startpage_html(query, owned_client)
    if html is None:
        return None

    for candidate in _result_urls(html):
        validated = await get_website(candidate, client=client)
        if validated:
            return validated
    return None


def _default_client() -> httpx.AsyncClient:
    settings = get_settings()
    headers = {"User-Agent": settings.default_user_agent} if settings.default_user_agent else {}
    return httpx.AsyncClient(follow_redirects=True, timeout=REQUEST_TIMEOUT, headers=headers)


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not urlparse(url).scheme:
        url = f"https://{url}"
    return url


def _registrable_domain(url: str) -> str:
    return urlparse(url).netloc.lower().split(":")[0].removeprefix("www.")


def _is_skipped(domain: str) -> bool:
    """Whether `domain` is (or sits under) one of `SKIP_DOMAINS`.

    Subdomains have to be matched too: Startpage's own results page links to
    `app.startpage.com`, which an exact-match check waves through -- and since
    that link outranks everything, the "website" mined for a business with no
    site of its own came back as the search engine we searched on.
    """
    return any(domain == skip or domain.endswith(f".{skip}") for skip in SKIP_DOMAINS)


async def _fetch_final_url(url: str, client: httpx.AsyncClient) -> str | None:
    try:
        response = await client.get(url)
    except httpx.HTTPError:
        return None
    if response.status_code >= 400:
        return None
    return str(response.url)


async def _fetch_startpage_html(query: str, client: httpx.AsyncClient) -> str | None:
    try:
        response = await client.get(STARTPAGE_SEARCH_URL, params={"query": query, "cat": "web"})
    except httpx.HTTPError:
        return None
    if response.status_code >= 400:
        return None
    # Startpage answers a blocked client with a 200 captcha page, and that page
    # carries ordinary-looking outbound links (its own help subreddit, for one).
    # Scraping it hands back a "website" that has nothing to do with the
    # business, so a challenge counts as no results, not as results.
    if _is_challenge(str(response.url)):
        logger.info("startpage served a challenge page, skipping website search")
        return None
    return response.text


def _is_challenge(url: str) -> bool:
    lowered = url.lower()
    return "captcha" in lowered or "/challenge" in lowered


def _result_urls(html: str) -> list[str]:
    """Extract organic result links from a Startpage results page, in rank order."""
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for anchor in soup.find_all("a", href=True):
        # bs4's stubs type an attribute value as `str | AttributeValueList`
        # (multi-valued attrs like `class` use the latter) -- `href` is always
        # single-valued in practice, but this keeps mypy honest about it.
        href = str(anchor["href"])
        if not href.startswith("http"):
            continue
        domain = _registrable_domain(href)
        if not domain or _is_skipped(domain):
            continue
        if href not in urls:
            urls.append(href)
    return urls
