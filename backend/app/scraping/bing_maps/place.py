"""Loads a single /maps/place/ URL and extracts name, address, phone, category, rating,
lat/long. Uses a spoofed Chrome 140 user agent (see core.config.default_user_agent).
Mirrors google_maps/place.py's interface/return shape.

Legacy equivalent: BingMapsScraper (place detail leg).
"""

import logging
import re
import time

from playwright.async_api import Locator, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.core.config import get_settings
from app.core.logging import log_context
from app.scraping.common.rate_limit import RateLimited, guarded_goto
from app.scraping.google_maps.place import PlaceData
from app.scraping.proxy.pool import get_proxy_pool, to_playwright_proxy

logger = logging.getLogger(__name__)

# Bing's entity-panel DOM classes are minified/obfuscated and shift periodically --
# these selectors are current as of writing. If extraction silently starts coming
# back empty, check these against a live page first before anything else.
NAME_SELECTOR = "h1"
ADDRESS_SELECTOR = 'div[class*="address"]'
PHONE_SELECTOR = 'a[href^="tel:"]'
WEBSITE_SELECTOR = 'a[class*="website"], a[data-tag="websiteText"]'
CATEGORY_SELECTOR = 'div[class*="category"]'
RATING_SELECTOR = 'div[class*="rating"] span'
REVIEWS_COUNT_SELECTOR = 'span[class*="reviewCount"], div[class*="rating"] + span'

RATING_RE = re.compile(r"(\d+(?:[.,]\d+)?)")
REVIEWS_COUNT_RE = re.compile(r"\(?([\d,.\s]+)\)?")

# Bing Maps centers the map on the entity's coordinates via a `cp=<lat>~<lng>` query
# param on the URL once a place is opened -- no separate DOM lookup needed.
LAT_LNG_RE = re.compile(r"cp=(-?\d+\.\d+)~(-?\d+\.\d+)")
CLAIM_BUSINESS_SELECTOR = 'a[href*="placeservicesservice.bing.com"]'

FEED_WAIT_MS = 15_000


async def get_place_data(place_url: str) -> PlaceData:
    """Open one place URL and scrape its entity panel.

    Degrades gracefully: a missing field (renamed selector, A/B-tested layout,
    a place with no phone/website) is just absent from the returned dict rather
    than raising, except for a page that never renders at all -- that returns
    an empty dict. A rate-limited load is the one hard failure: `guarded_goto`
    raises `RateLimited` so the caller can retry it later instead of recording
    an empty place.

    Reports the outcome (Proxies screen, "list" mode only -- see
    app.scraping.proxy.pool) of whichever proxy was checked out: `blocked` on
    `RateLimited`, `failure` on anything else that escapes, `success` otherwise.
    """
    settings = get_settings()
    data: PlaceData = {}

    pool = get_proxy_pool()
    raw_proxy = pool.get_proxy()
    proxy = to_playwright_proxy(raw_proxy)
    started = time.monotonic()

    with log_context(source="bing", place_url=place_url):
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
    return text.strip()


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


def _lat_lng_from_url(url: str) -> tuple[float | None, float | None]:
    match = LAT_LNG_RE.search(url)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))
