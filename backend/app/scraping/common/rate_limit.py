"""Adaptive rate-limit / 429 handling for Maps page loads (11.3).

Phase 5 gave every request a fixed random delay. That's enough to look human on a
healthy run, but it does nothing once Maps actually starts pushing back: the
scraper keeps hammering at the same cadence and every subsequent page comes back
blocked. This module adds the reactive half.

Two mechanisms, per host:

1. **Detection.** A navigation counts as rate-limited when the response status is
   429/503, or when the final URL is one of the interstitials Google/Bing bounce
   blocked clients to (`google.com/sorry/...`, `bing.com/challenge...`) -- those
   answer HTTP 200, so status alone would miss them.

2. **Escalating cooldown.** Each consecutive hit doubles the host's cooldown
   (`base`, `2x base`, `4x base` ... capped at `rate_limit_max_cooldown_s`), and a
   `Retry-After` header wins if it asks for longer. A clean load resets it to zero.

A blocked load raises `RateLimited` rather than sleeping it off in place: a Celery
worker slot holds an open Chromium, so it's much cheaper to fail the task and let
`app.workers.tasks` reschedule it with a countdown (see 11.1) than to park the
browser for fifteen minutes. Requests that arrive while a host is still cooling
down raise straight away, before a browser is even launched.

Cooldown state lives in-process, so with the prefork pool each worker process
tracks a host independently. Good enough at current concurrency -- move
`_HostState` into Redis if the worker fleet ever grows past one box.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from functools import lru_cache
from urllib.parse import urlsplit

from playwright.async_api import Page, Response

from app.core.config import get_settings
from app.scraping.proxy.pool import get_proxy_pool

logger = logging.getLogger(__name__)

RATE_LIMIT_STATUSES = frozenset({429, 503})

# Interstitials that answer 200 but contain no results: Google's "unusual traffic"
# page and Bing's bot challenge. Matched against the URL the page ended up on.
BLOCK_URL_MARKERS = ("/sorry/", "/challenge", "captcha")


class RateLimited(RuntimeError):
    """Raised when a host is refusing to serve us, or is still in cooldown.

    `retry_after` is the number of seconds the caller should wait before trying
    this host again -- taken from the `Retry-After` header when the host sent
    one, otherwise the escalating cooldown this module computed.
    """

    def __init__(
        self,
        url: str,
        *,
        status: int | None = None,
        retry_after: float | None = None,
        reason: str = "rate limited",
    ) -> None:
        super().__init__(f"{reason}: {url} (status={status}, retry_after={retry_after})")
        self.url = url
        self.status = status
        self.retry_after = retry_after
        self.reason = reason


@dataclass
class _HostState:
    consecutive: int = 0
    cooldown_until: float = 0.0  # time.monotonic() deadline


@dataclass
class RateLimitTracker:
    """Per-host cooldown bookkeeping. One instance per process (`get_tracker()`)."""

    base_cooldown_s: float
    max_cooldown_s: float
    _hosts: dict[str, _HostState] = field(default_factory=dict)

    def cooldown_remaining(self, host: str) -> float:
        state = self._hosts.get(host)
        if state is None:
            return 0.0
        return max(0.0, state.cooldown_until - time.monotonic())

    def raise_if_cooling_down(self, url: str) -> None:
        """Refuse a request to a host we already know is blocking us."""
        host = _host_of(url)
        remaining = self.cooldown_remaining(host)
        if remaining <= 0:
            return
        logger.warning(
            "host in rate-limit cooldown, deferring",
            extra={"host": host, "cooldown_remaining_s": round(remaining, 1)},
        )
        raise RateLimited(url, retry_after=remaining, reason="host in cooldown")

    def record_rate_limited(
        self, url: str, *, status: int | None = None, retry_after: float | None = None
    ) -> float:
        """Escalate the host's cooldown. Returns the seconds to wait before retrying."""
        host = _host_of(url)
        state = self._hosts.setdefault(host, _HostState())
        state.consecutive += 1

        cooldown = min(
            self.base_cooldown_s * (2 ** (state.consecutive - 1)), self.max_cooldown_s
        )
        if retry_after is not None:
            cooldown = max(cooldown, retry_after)

        state.cooldown_until = time.monotonic() + cooldown
        logger.warning(
            "rate limited by host",
            extra={
                "host": host,
                "status": status,
                "consecutive": state.consecutive,
                "cooldown_s": round(cooldown, 1),
            },
        )
        return cooldown

    def record_success(self, url: str) -> None:
        """A clean load clears the host's escalation -- next block starts at `base`."""
        self._hosts.pop(_host_of(url), None)


@lru_cache
def get_tracker() -> RateLimitTracker:
    """One tracker per worker process (prefork pool), cached for its lifetime.

    `base_cooldown_s` can also be set from Settings > Scraping
    (app.core.runtime_settings.get_cooldown_base_s), but that setting is
    DB-backed while this cache is process-local with no DB session in scope
    (this runs deep inside an `asyncio.run()` call from Playwright scraping
    code, well past where a SQLAlchemy session is threaded through) -- so a
    change takes effect for scrapes started by a worker process that starts
    *after* the change, not mid-run. Same latency class as the other
    env-sourced tunable here (`max_cooldown_s`); documented rather than
    silently stale.
    """
    settings = get_settings()
    return RateLimitTracker(
        base_cooldown_s=settings.rate_limit_base_cooldown_s,
        max_cooldown_s=settings.rate_limit_max_cooldown_s,
    )


async def guarded_goto(page: Page, url: str, *, wait_until: str = "domcontentloaded") -> Response:
    """`page.goto` with the fixed delay in front and 429 detection behind.

    Raises `RateLimited` if the host is cooling down, if the response status is
    in `RATE_LIMIT_STATUSES`, or if we landed on a block interstitial. Any other
    outcome (including a plain 404, which is the place's problem, not ours)
    returns the response and resets the host's cooldown.
    """
    tracker = get_tracker()
    tracker.raise_if_cooling_down(url)

    settings = get_settings()
    await get_proxy_pool().delay(settings.scrape_min_delay_ms, settings.scrape_max_delay_ms)

    response = await page.goto(url, wait_until=wait_until)  # type: ignore[arg-type]
    check_response(response, page.url)
    return response  # type: ignore[return-value]


def check_response(response: Response | None, final_url: str) -> None:
    """Raise `RateLimited` (and escalate the host's cooldown) if we were blocked."""
    tracker = get_tracker()
    status = response.status if response is not None else None

    blocked_by_status = status in RATE_LIMIT_STATUSES
    blocked_by_url = is_block_page(final_url)
    if not blocked_by_status and not blocked_by_url:
        tracker.record_success(final_url)
        return

    retry_after = parse_retry_after(response.headers.get("retry-after") if response else None)
    cooldown = tracker.record_rate_limited(final_url, status=status, retry_after=retry_after)
    raise RateLimited(
        final_url,
        status=status,
        retry_after=cooldown,
        reason="blocked interstitial" if blocked_by_url else "rate limited",
    )


def is_block_page(url: str) -> bool:
    lowered = url.lower()
    return any(marker in lowered for marker in BLOCK_URL_MARKERS)


def parse_retry_after(header: str | None) -> float | None:
    """`Retry-After` is either delta-seconds or an HTTP-date (RFC 9110 10.2.3)."""
    if not header:
        return None

    header = header.strip()
    try:
        return max(0.0, float(header))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(header)
    except (TypeError, ValueError):
        return None

    now = datetime.now(tz=retry_at.tzinfo or UTC)
    return max(0.0, (retry_at - now).total_seconds())


async def sleep_with_jitter(seconds: float, *, jitter: float = 0.1) -> None:
    """Sleep `seconds` +/- `jitter` fraction, for callers that do wait in place."""
    await asyncio.sleep(seconds * random.uniform(1 - jitter, 1 + jitter))


def _host_of(url: str) -> str:
    return (urlsplit(url).hostname or url).lower()
