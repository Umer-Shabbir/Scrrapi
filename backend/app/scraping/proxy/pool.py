"""Proxy pool with three modes: single, list, or fetched free-list
(aggregator-style). Applies a configurable random delay between requests (see
core.config.scrape_min_delay_ms / scrape_max_delay_ms).

Legacy equivalent: ProxyServer.

"list" mode is DB-backed (Proxies screen, app.db.models.proxy.Proxy) rather
than a flat file, as of the Proxies screen cycle -- "single"/"free" modes are
unchanged. The actual queries/updates live in app.scraping.proxy.store as
plain `Session`-taking functions (unit-tested there against in-memory
SQLite); this class is a thin wrapper that opens its own short-lived
`AppSessionLocal()` around them, same self-contained-fetch shape "free" mode's
`_fetch_free_list` already uses -- the 4 scraper call sites that use this pool
(google/bing x place/feed) aren't otherwise DB-aware, and threading a session
through their signatures would be a bigger change than this pool owning its
own short connection.
"""

import asyncio
import random
import time
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

import httpx
from playwright.async_api import ProxySettings

from app.core.config import get_settings
from app.db.session import AppSessionLocal
from app.scraping.proxy.store import (
    reactivate_cooled_proxies,
    record_proxy_outcome,
    select_active_proxy,
)

ProxyMode = Literal["single", "list", "free"]
ProxyOutcome = Literal["success", "failure", "blocked"]

# proxyscrape's free-list endpoint: plain-text, one "ip:port" per line, no auth.
DEFAULT_FREE_LIST_URL = (
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http"
    "&timeout=10000&country=all&ssl=all&anonymity=all"
)
DEFAULT_FREE_LIST_TTL_S = 600
FREE_LIST_FETCH_TIMEOUT_S = 10


class ProxyPool:
    def __init__(
        self,
        mode: ProxyMode,
        *,
        single_url: str | None = None,
        list_path: str | None = None,
        free_list_url: str = DEFAULT_FREE_LIST_URL,
        free_list_ttl_s: int = DEFAULT_FREE_LIST_TTL_S,
    ):
        self.mode = mode
        self.single_url = single_url
        # Unused by "list" mode since the DB backing change -- kept only so
        # existing constructor calls (get_proxy_pool()) don't need updating
        # for a setting that predates this and may still be read elsewhere.
        self.list_path = list_path
        self.free_list_url = free_list_url
        self.free_list_ttl_s = free_list_ttl_s

        self._list_index = 0
        self._free_cache: list[str] = []
        self._free_cached_at: float = 0.0
        # Consecutive-block counters, kept in-process (not persisted) --
        # reset on any success and on process restart. Persisted state is
        # cooling_until/block_count on the Proxy row itself.
        self._consecutive_blocks: dict[str, int] = {}

    def get_proxy(self) -> str | None:
        """Return the next proxy URL to use, or None for a direct connection.

        Never raises on a missing/unreachable source -- a misconfigured or
        exhausted proxy source just means "scrape without a proxy" rather than
        crashing the run.
        """
        if self.mode == "single":
            return _normalize(self.single_url)

        if self.mode == "list":
            return self._get_from_db()

        if self.mode == "free":
            return self._get_from_free_list()

        raise ValueError(f"Unknown proxy mode: {self.mode!r}")

    def record_outcome(
        self, proxy_url: str | None, outcome: ProxyOutcome, *, latency_ms: int
    ) -> None:
        """Update the Proxy row's running counters after a request that used
        `proxy_url`. No-op for "single"/"free" modes or a direct connection
        (no Proxy row exists to update) -- only "list" mode's DB-backed
        entries are tracked.
        """
        if self.mode != "list" or not proxy_url:
            return

        host, port = _host_port(proxy_url)
        if host is None or port is None:
            return

        db = AppSessionLocal()
        try:
            record_proxy_outcome(
                db,
                host,
                port,
                outcome,
                latency_ms=latency_ms,
                consecutive_blocks=self._consecutive_blocks,
            )
        finally:
            db.close()

    async def delay(self, min_ms: int, max_ms: int) -> None:
        """Sleep a random duration in [min_ms, max_ms] before/between requests."""
        if max_ms < min_ms:
            raise ValueError(f"max_ms ({max_ms}) must be >= min_ms ({min_ms})")
        await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)

    # -- list mode (DB-backed) ----------------------------------------------

    def _get_from_db(self) -> str | None:
        db = AppSessionLocal()
        try:
            reactivate_cooled_proxies(db)
            row = select_active_proxy(db, self._list_index)
            if row is None:
                return None
            self._list_index += 1
            return row.url()
        finally:
            db.close()

    # -- free mode -----------------------------------------------------------

    def _get_from_free_list(self) -> str | None:
        if self._free_list_stale():
            fetched = self._fetch_free_list()
            if fetched:
                self._free_cache = fetched
                self._free_cached_at = time.monotonic()
            # Fetch failed or returned nothing: keep serving the stale cache
            # (if any) rather than going proxy-less for one bad request.

        if not self._free_cache:
            return None

        proxy = random.choice(self._free_cache)
        return _normalize(proxy)

    def _free_list_stale(self) -> bool:
        if not self._free_cache:
            return True
        return time.monotonic() - self._free_cached_at >= self.free_list_ttl_s

    def _fetch_free_list(self) -> list[str]:
        try:
            response = httpx.get(self.free_list_url, timeout=FREE_LIST_FETCH_TIMEOUT_S)
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        return [line.strip() for line in response.text.splitlines() if line.strip()]


def _normalize(proxy: str | None) -> str | None:
    """Add an http:// scheme to a bare "ip:port" / "user:pass@ip:port" entry."""
    if not proxy:
        return None
    return proxy if "://" in proxy else f"http://{proxy}"


def _host_port(proxy_url: str) -> tuple[str | None, int | None]:
    parts = urlsplit(proxy_url)
    if not parts.hostname or not parts.port:
        return None, None
    return parts.hostname, parts.port


def to_playwright_proxy(proxy_url: str | None) -> ProxySettings | None:
    """Convert a proxy URL into the shape Playwright's launch()/new_context()
    `proxy` argument expects, or None if there's no proxy to apply."""
    if not proxy_url:
        return None

    parts = urlsplit(proxy_url)
    server = f"{parts.scheme}://{parts.hostname}"
    if parts.port:
        server += f":{parts.port}"

    proxy = ProxySettings(server=server)
    if parts.username:
        proxy["username"] = parts.username
    if parts.password:
        proxy["password"] = parts.password
    return proxy


@lru_cache
def get_proxy_pool() -> ProxyPool:
    settings = get_settings()
    return ProxyPool(
        settings.proxy_mode,  # type: ignore[arg-type]
        single_url=settings.proxy_single_url,
        list_path=settings.proxy_list_path,
        free_list_url=settings.proxy_free_list_url,
        free_list_ttl_s=settings.proxy_free_list_ttl_s,
    )
