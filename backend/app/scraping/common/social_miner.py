"""Harvests social profile links from a business website.

Matched by regex over the raw markup rather than by walking anchors, because a
profile URL is just as likely to sit in a `<meta property="og:see_also">` tag, a
JSON-LD `sameAs` array, or an inlined theme config as in an `<a href>` -- and all
three forms are equally usable.

Two things this has to get right, because both were the whole reason a naive
"does the href contain facebook.com" check produces unusable data:

- **Share widgets are not profiles.** `facebook.com/sharer/sharer.php?u=...`,
  `twitter.com/intent/tweet`, `linkedin.com/sharing/share-offsite` appear on
  every page of every site with a share button on it, and none of them belong to
  the business.
- **A bare domain is not a profile.** Themes ship with `href="https://facebook.com/"`
  in the footer, waiting to be filled in. Anything with no path below the host is
  dropped.
"""

import re
from urllib.parse import urlsplit, urlunsplit

# The networks that get their own result column. Order matters only for
# readability of the output dict.
SOCIAL_HOSTS: dict[str, tuple[str, ...]] = {
    "facebook": ("facebook.com", "fb.com", "fb.me"),
    "instagram": ("instagram.com", "instagr.am"),
    "linkedin": ("linkedin.com", "lnkd.in"),
    "twitter": ("twitter.com", "x.com"),
    "youtube": ("youtube.com", "youtu.be"),
    "tiktok": ("tiktok.com",),
    "whatsapp": ("wa.me", "whatsapp.com"),
}

# Recognised networks that don't earn a column of their own; they land together
# in `other`. Kept as an allowlist rather than "any outbound link" so the column
# stays a list of profiles instead of a dump of every link on the site.
OTHER_SOCIAL_HOSTS = (
    "pinterest.com",
    "t.me",
    "telegram.me",
    "snapchat.com",
    "threads.net",
    "threads.com",
    "vimeo.com",
    "xing.com",
    "vk.com",
    "yelp.com",
    "tripadvisor.com",
    "github.com",
    "behance.net",
    "dribbble.com",
    "medium.com",
    "reddit.com",
    "discord.gg",
    "trustpilot.com",
)

OTHER_KEY = "other"

URL_RE = re.compile(r"""https?://[^\s"'<>)\\]+""", re.IGNORECASE)

# Path fragments that mean "this link acts on the current page" rather than
# "this is our profile". Checked case-insensitively against the path + query.
SHARE_MARKERS = (
    "/sharer",
    "share.php",
    "/share?",
    "/sharing/",
    "share-offsite",
    "/intent/",
    "/dialog/",
    "/plugins/",
    "/widgets/",
    "/embed",
    "/oauth",
    "/login",
    "/signup",
    "/policies",
    "/legal",
    "/help",
    "/tr?",  # facebook tracking pixel
)

# Per-network paths that are content, not an account: a linked video or post
# tells us nothing about which account owns it.
CONTENT_MARKERS: dict[str, tuple[str, ...]] = {
    "facebook": (
        "/photo",
        "/events/",
        "/groups/",
    ),
    "instagram": ("/p/", "/reel/", "/reels/", "/explore/", "/stories/"),
    "twitter": ("/status/", "/hashtag/", "/search"),
    "youtube": ("/watch", "/shorts/", "/playlist"),
    "tiktok": ("/video/", "/tag/", "/music/"),
    "linkedin": ("/pulse/", "/jobs/"),
}

# Query strings are dropped as tracking noise, except where the query *is* the
# identity: `facebook.com/profile.php?id=100064…` and WhatsApp's click-to-chat.
QUERY_BEARING_PATHS = ("/profile.php", "/send", "/send/")


def extract_social_links(html: str) -> dict[str, list[str]]:
    """Group every social profile URL on the page by network.

    Returns `{network: [url, ...]}` in first-seen order, with unrecognised-but-
    known networks under `other` and networks with no hit absent entirely. URLs
    are canonicalised (scheme forced to https, `www.` and trailing slash
    stripped, tracking query dropped) so the same profile linked from the header
    and the footer counts once.
    """
    grouped: dict[str, list[str]] = {}
    seen: set[str] = set()

    for match in URL_RE.finditer(html):
        raw = match.group(0).rstrip(".,;:'\")]}")
        network = classify_social_url(raw)
        if network is None:
            continue

        canonical = canonicalize_social_url(raw)
        if not canonical or canonical.lower() in seen:
            continue
        seen.add(canonical.lower())
        grouped.setdefault(network, []).append(canonical)

    return grouped


def classify_social_url(url: str) -> str | None:
    """Which network a URL belongs to, or `None` if it isn't a usable profile link."""
    split = urlsplit(url)
    host = split.netloc.lower().split(":")[0].removeprefix("www.")
    if not host:
        return None

    network = _network_for_host(host)
    if network is None:
        return None

    path_and_query = f"{split.path}?{split.query}".lower()
    if any(marker in path_and_query for marker in SHARE_MARKERS):
        return None
    if any(marker in path_and_query for marker in CONTENT_MARKERS.get(network, ())):
        return None

    # No path below the host: an unfilled theme placeholder, not a profile.
    # WhatsApp is the exception in reverse -- `api.whatsapp.com/send?phone=…`
    # carries its identity in the query, so an empty path is fine there.
    if split.path.strip("/") == "" and not (network == "whatsapp" and split.query):
        return None
    return network


def canonicalize_social_url(url: str) -> str:
    """Normalize a profile URL so the same account is one string, not five."""
    split = urlsplit(url)
    host = split.netloc.lower().split(":")[0].removeprefix("www.")
    path = split.path.rstrip("/")

    keep_query = split.query and any(
        path.lower().endswith(marker.rstrip("/")) or path.lower() == marker.rstrip("/")
        for marker in QUERY_BEARING_PATHS
    )
    query = _clean_query(split.query) if keep_query else ""

    return urlunsplit(("https", host, path, query, ""))


def _network_for_host(host: str) -> str | None:
    for network, hosts in SOCIAL_HOSTS.items():
        if any(host == candidate or host.endswith(f".{candidate}") for candidate in hosts):
            return network
    for candidate in OTHER_SOCIAL_HOSTS:
        if host == candidate or host.endswith(f".{candidate}"):
            return OTHER_KEY
    return None


def _clean_query(query: str) -> str:
    """Drop tracking parameters from a query we're otherwise keeping."""
    kept = [
        part
        for part in query.split("&")
        if part and not part.lower().startswith(("utm_", "fbclid", "gclid", "ref=", "ref_"))
    ]
    return "&".join(kept)
