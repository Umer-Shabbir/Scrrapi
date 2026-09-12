"""Detects a handful of well-known platforms/tools off a page's raw HTML.

Lead Detail's WEB block shows these as read-only chips ("what is this business
running on"). Deliberately isolated from the deep site crawler
(`app.scraping.common.site_crawler`): that module never retains page HTML once
a page's contacts are mined out of it, and threading HTML through it would mean
buffering page bodies for every job that runs with the crawler on, not just the
one page this feature needs. `detect_tech_stack` instead runs against a single
extra fetch of the business's own home page -- see `app.workers.tasks.fingerprint_site`.

Signature matching is deliberately narrow: a handful of unambiguous markers
(script src hosts, meta generator tags) rather than a general-purpose detector.
A false negative just means an empty chip row; a false positive would print a
platform name that isn't there, which is worse.
"""

import logging
import re

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10.0

# Each signature is a (display name, compiled pattern) pair. Matched against
# raw HTML, case-insensitively. Order is display order.
_SIGNATURES: list[tuple[str, re.Pattern[str]]] = [
    ("WordPress", re.compile(r"wp-content/|wp-includes/|generator[^>]*wordpress", re.IGNORECASE)),
    ("Shopify", re.compile(r"cdn\.shopify\.com|shopify-section", re.IGNORECASE)),
    ("Wix", re.compile(r"static\.wixstatic\.com|wix\.com", re.IGNORECASE)),
    ("Squarespace", re.compile(r"squarespace\.com|static1\.squarespace", re.IGNORECASE)),
    ("Webflow", re.compile(r"webflow\.com|data-wf-site", re.IGNORECASE)),
    (
        "Google Analytics",
        re.compile(
            r"googletagmanager\.com/gtag/js|google-analytics\.com/analytics\.js|gtag\(",
            re.IGNORECASE,
        ),
    ),
    ("HubSpot", re.compile(r"js\.hs-scripts\.com|hs-analytics\.net|hsforms\.com", re.IGNORECASE)),
    ("Mailchimp", re.compile(r"chimpstatic\.com|list-manage\.com", re.IGNORECASE)),
    ("Intercom", re.compile(r"widget\.intercom\.io", re.IGNORECASE)),
    ("Cloudflare", re.compile(r"cdn-cgi/|cloudflare\.com/cdn-cgi", re.IGNORECASE)),
]

MAX_SIGNATURES = 6


def detect_tech_stack(html: str) -> list[str]:
    """Every signature matched in `html`, in signature order, capped at `MAX_SIGNATURES`.

    Empty list, never `None` -- a site with no recognised platform is the
    normal case, not an error.
    """
    if not html:
        return []
    found = [name for name, pattern in _SIGNATURES if pattern.search(html)]
    return found[:MAX_SIGNATURES]


async def fetch_tech_stack(
    website: str | None, *, client: httpx.AsyncClient | None = None
) -> list[str]:
    """One GET on `website`'s home page, then `detect_tech_stack` on the body.

    Never raises for anything the network does -- a dead host, a timeout, a
    non-HTML response all come back as an empty list, same as "no website".
    This is deliberately its own request rather than reusing whatever the deep
    crawler already fetched: the crawler discards page HTML once a page's
    contacts are mined out of it, and this is the one feature that needs the
    HTML itself, so it asks again instead of changing what the crawler keeps.
    """
    if not website:
        return []

    async def _fetch(active: httpx.AsyncClient) -> list[str]:
        try:
            response = await active.get(website, timeout=REQUEST_TIMEOUT)
        except httpx.HTTPError:
            return []
        if response.status_code >= 400:
            return []
        content_type = response.headers.get("content-type", "").lower()
        if content_type and "html" not in content_type:
            return []
        return detect_tech_stack(response.text)

    if client is not None:
        return await _fetch(client)

    settings = get_settings()
    headers = {"User-Agent": settings.default_user_agent} if settings.default_user_agent else {}
    async with httpx.AsyncClient(follow_redirects=True, headers=headers) as owned_client:
        return await _fetch(owned_client)
