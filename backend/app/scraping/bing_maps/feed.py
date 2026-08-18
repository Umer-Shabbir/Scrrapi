"""Loads Bing Maps results in headless Playwright Chromium, scrolls the listings panel
until the count of place-card anchors stops growing, with a timeout guard. Mirrors
google_maps/feed.py's interface and scroll/stall strategy.

Legacy equivalent: BingMapsScraper.

Not covered by an automated test -- run it manually against one real query first
(`python -c "..."` or a scratch script) before wiring it into a Celery task; headless
scraping of a live Bing Maps page is exactly the kind of thing that shouldn't go in CI.
Bing's listings-panel DOM classes shift periodically -- if extraction silently starts
coming back empty, check these selectors against a live page before anything else.
"""

import logging
import re
import time

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.core.config import get_settings
from app.core.logging import log_context
from app.scraping.common.rate_limit import RateLimited, guarded_goto
from app.scraping.proxy.pool import get_proxy_pool, to_playwright_proxy

logger = logging.getLogger(__name__)

FEED_SELECTOR = "div.listContainer"
RESULT_ANCHOR_SELECTOR = "a.listItemContent"
PLACE_URL_RE = re.compile(r"/maps/place/")

# Consecutive scroll rounds with no new anchors before we call the feed "stalled"
# (end of results, or Bing stopped lazy-loading more for this session).
STALL_ROUNDS = 3
SCROLL_PAUSE_MS = 1000
FEED_WAIT_MS = 15_000


async def get_place_urls(search_url: str, *, timeout_s: int = 60) -> list[str]:
    """Scroll a Bing Maps results panel and return every distinct
    `/maps/place/...` URL it surfaced, in the order anchors first appeared.

    Bails out after `timeout_s` even if the panel is still growing. Returns an
    empty list (rather than raising) if no listings panel ever renders -- e.g. a
    zero-result query, or Bing redirecting straight to a single place.

    Raises `RateLimited` (via `guarded_goto`) if Bing answers 429/503 or bounces
    us to a bot challenge; the calling Celery task turns that into a backed-off
    retry rather than treating it as a zero-result query.

    Reports the outcome (Proxies screen, "list" mode only -- see
    app.scraping.proxy.pool) of whichever proxy was checked out: `blocked` on
    `RateLimited`, `failure` on anything else that escapes, `success` otherwise.
    """
    settings = get_settings()
    deadline = time.monotonic() + timeout_s
    hrefs: list[str] = []

    pool = get_proxy_pool()
    raw_proxy = pool.get_proxy()
    proxy = to_playwright_proxy(raw_proxy)
    started = time.monotonic()

    with log_context(source="bing", search_url=search_url):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, proxy=proxy)
                try:
                    context = await browser.new_context(
                        user_agent=settings.default_user_agent or None
                    )
                    page = await context.new_page()
                    await guarded_goto(page, search_url)

                    try:
                        await page.wait_for_selector(FEED_SELECTOR, timeout=FEED_WAIT_MS)
                    except PlaywrightTimeoutError:
                        logger.info("no listings panel rendered, treating as zero results")
                        return []

                    feed = page.locator(FEED_SELECTOR)
                    last_count = -1
                    stalled_for = 0

                    while stalled_for < STALL_ROUNDS and time.monotonic() < deadline:
                        count = await feed.locator(RESULT_ANCHOR_SELECTOR).count()
                        stalled_for = stalled_for + 1 if count == last_count else 0
                        last_count = count

                        await feed.evaluate("el => el.scrollTo(0, el.scrollHeight)")
                        await page.wait_for_timeout(SCROLL_PAUSE_MS)

                    hrefs = await feed.locator(RESULT_ANCHOR_SELECTOR).evaluate_all(
                        "els => els.map(el => el.href)"
                    )
                finally:
                    await browser.close()
        except RateLimited:
            pool.record_outcome(raw_proxy, "blocked", latency_ms=int((time.monotonic() - started) * 1000))
            raise
        except Exception:
            pool.record_outcome(raw_proxy, "failure", latency_ms=int((time.monotonic() - started) * 1000))
            raise
        else:
            pool.record_outcome(raw_proxy, "success", latency_ms=int((time.monotonic() - started) * 1000))

        place_urls = _dedupe_place_urls(hrefs)
        logger.info(
            "feed scrape finished",
            extra={"anchors": len(hrefs), "place_urls": len(place_urls)},
        )
        return place_urls


def _dedupe_place_urls(hrefs: list[str]) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for href in hrefs:
        if href and PLACE_URL_RE.search(href) and href not in seen:
            seen.add(href)
            urls.append(href)
    return urls
