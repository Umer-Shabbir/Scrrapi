"""Loads a single /maps/place/ URL and extracts name, address, phone, category, rating,
lat/long. Uses a spoofed Chrome 140 user agent (see core.config.default_user_agent).

Legacy equivalent: GMCompanyPageScraper.GetData / GooglePageScraper.
"""

import logging
import re
import time
from typing import TypedDict

from playwright.async_api import Locator, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.core.config import get_settings
from app.core.logging import log_context
from app.scraping.common.rate_limit import RateLimited, guarded_goto
from app.scraping.proxy.pool import get_proxy_pool, to_playwright_proxy

logger = logging.getLogger(__name__)

# Google's Maps DOM classes are minified/obfuscated and shift periodically -- these
# selectors are current as of writing. If extraction silently starts coming back
# empty, check these against a live page first before anything else.
NAME_SELECTOR = "h1"
ADDRESS_SELECTOR = 'button[data-item-id="address"]'
PHONE_SELECTOR = 'button[data-item-id^="phone:tel:"], a[href^="tel:"]'
WEBSITE_SELECTOR = 'a[data-item-id="authority"]'
CATEGORY_SELECTOR = "button.DkEaL"
RATING_SELECTOR = 'div.F7nice span[aria-hidden="true"]'
REVIEWS_COUNT_SELECTOR = (
    'div.F7nice span:last-child, button[data-tab-index="1"], span[aria-label*="review"]'
)
REVIEW_SNIPPET_SELECTOR = "span.wiI7pd, div.MyEned span"
CLAIM_BUSINESS_SELECTOR = 'a[data-item-id="merchant"]' # Typically contains "Claim this business" or "Own this business?" or similar link

RATING_RE = re.compile(r"(\d+(?:[.,]\d+)?)")
REVIEWS_COUNT_RE = re.compile(r"\(?([\d,.\s]+)\)?")

# Each detail-panel button (address, phone, ...) pairs an icon-font glyph with the
# label text; the glyph is a Private Use Area code point that `inner_text()` returns
# as its own line, so it has to be scrubbed out to get a clean field value.
ICON_GLYPH_RE = re.compile("[-]")

# Coordinates show up in the page URL in one of two shapes depending on how the
# place was reached: `/@<lat>,<lng>,<zoom>z/` when Maps has centered the map on
# it, or `!3d<lat>!4d<lng>!` inside the `data=` blob for links opened directly
# from a feed anchor (no `/@.../` segment present at all in that case).
LAT_LNG_PATTERNS = [
    re.compile(r"/@(-?\d+\.\d+),(-?\d+\.\d+)"),
    re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)"),
]

FEED_WAIT_MS = 15_000


class PlaceData(TypedDict, total=False):
    name: str
    address: str
    phone: str
    category: str
    rating: float
    reviews_count: int
    reviews: list[str]
    latitude: float
    longitude: float
    website: str | None
    is_unclaimed: bool


async def get_place_data(place_url: str) -> PlaceData:
    """Open one place URL and scrape its detail panel.

    Degrades gracefully: a missing field (renamed selector, A/B-tested layout,
    a place with no phone/website) is just absent from the returned dict rather
    than raising, except for a page that never renders at all -- that returns
    an empty dict. A rate-limited load is the one hard failure: `guarded_goto`
    raises `RateLimited` so the caller can retry it later instead of recording
    an empty place.

    Reports the outcome (Proxies screen, "list" mode only -- see
    app.scraping.proxy.pool) of whichever proxy was checked out: `blocked` on
    `RateLimited`, `failure` on anything else that escapes, `success`
    otherwise -- including a rendered-but-empty panel, which is a real
    response from the proxy even though nothing useful was on the page.
    """
    settings = get_settings()
    data: PlaceData = {}

    pool = get_proxy_pool()
    raw_proxy = pool.get_proxy()
    proxy = to_playwright_proxy(raw_proxy)
    started = time.monotonic()

    with log_context(source="google", place_url=place_url):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, proxy=proxy)
                try:
                    context = await browser.new_context(
                        user_agent=settings.default_user_agent or None
                    )
                    page = await context.new_page()
                    await guarded_goto(page, place_url)

                    try:
                        await page.wait_for_selector(NAME_SELECTOR, timeout=FEED_WAIT_MS)
                    except PlaywrightTimeoutError:
                        logger.info("place panel never rendered, skipping")
                        return data

                    name = await _inner_text(page.locator(NAME_SELECTOR).first)
                    if name:
                        data["name"] = name

                    address = await _inner_text(page.locator(ADDRESS_SELECTOR).first)
                    if address:
                        data["address"] = address

                    phone = await _phone_number(page.locator(PHONE_SELECTOR).first)
                    if phone:
                        data["phone"] = phone

                    category = await _inner_text(page.locator(CATEGORY_SELECTOR).first)
                    if category:
                        data["category"] = category

                    rating = await _rating(page.locator(RATING_SELECTOR).first)
                    if rating is not None:
                        data["rating"] = rating

                    reviews_count = await _reviews_count(page.locator(REVIEWS_COUNT_SELECTOR).first)
                    if reviews_count is not None:
                        data["reviews_count"] = reviews_count

                    snippets = await _review_snippets(page.locator(REVIEW_SNIPPET_SELECTOR))
                    if snippets:
                        data["reviews"] = snippets

                    data["website"] = await _href(page.locator(WEBSITE_SELECTOR).first)

                    claim_link = await page.locator(CLAIM_BUSINESS_SELECTOR).count()
                    if claim_link > 0:
                        data["is_unclaimed"] = True
                    else:
                        data["is_unclaimed"] = False

                    latitude, longitude = _lat_lng_from_url(page.url)
                    if latitude is not None and longitude is not None:
                        data["latitude"] = latitude
                        data["longitude"] = longitude
                finally:
                    await browser.close()
        except RateLimited:
            latency = int((time.monotonic() - started) * 1000)
            pool.record_outcome(raw_proxy, "blocked", latency_ms=latency)
            raise
        except Exception:
            latency = int((time.monotonic() - started) * 1000)
            pool.record_outcome(raw_proxy, "failure", latency_ms=latency)
            raise
        else:
            latency = int((time.monotonic() - started) * 1000)
            pool.record_outcome(raw_proxy, "success", latency_ms=latency)

        logger.info("place scraped", extra={"fields": sorted(data)})
        return data


def _clean_text(text: str) -> str:
    return ICON_GLYPH_RE.sub("", text).strip()


async def _inner_text(locator: Locator) -> str | None:
    if await locator.count() == 0:
        return None
    text = _clean_text(await locator.inner_text())
    return text or None


async def _href(locator: Locator) -> str | None:
    if await locator.count() == 0:
        return None
    return await locator.get_attribute("href")


async def _phone_number(locator: Locator) -> str | None:
    if await locator.count() == 0:
        return None
    href = await locator.get_attribute("href")
    if href and href.startswith("tel:"):
        return href.removeprefix("tel:")
    return await _inner_text(locator)


async def _rating(locator: Locator) -> float | None:
    text = await _inner_text(locator)
    if not text:
        return None
    match = RATING_RE.search(text)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


async def _reviews_count(locator: Locator) -> int | None:
    text = await _inner_text(locator)
    if not text:
        return None
    match = REVIEWS_COUNT_RE.search(text)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return int(digits) if digits else None


async def _review_snippets(locator: Locator, limit: int = 10) -> list[str]:
    count = await locator.count()
    if count == 0:
        return []
    snippets: list[str] = []
    for i in range(min(count, limit)):
        text = await _inner_text(locator.nth(i))
        if text and len(text) > 10:
            snippets.append(text)
    return snippets


def _lat_lng_from_url(url: str) -> tuple[float | None, float | None]:
    for pattern in LAT_LNG_PATTERNS:
        match = pattern.search(url)
        if match:
            return float(match.group(1)), float(match.group(2))
    return None, None
