import time

import httpx
import pytest

from app.scraping.proxy.pool import ProxyPool, to_playwright_proxy


def test_single_mode_returns_configured_url() -> None:
    pool = ProxyPool("single", single_url="http://1.2.3.4:8080")

    assert pool.get_proxy() == "http://1.2.3.4:8080"


def test_single_mode_adds_scheme_if_missing() -> None:
    pool = ProxyPool("single", single_url="1.2.3.4:8080")

    assert pool.get_proxy() == "http://1.2.3.4:8080"


def test_single_mode_with_no_url_returns_none() -> None:
    pool = ProxyPool("single")

    assert pool.get_proxy() is None


# "list" mode's round-robin/cooldown/outcome-recording behavior is covered in
# test_proxy_store.py (app.scraping.proxy.store), against in-memory SQLite --
# ProxyPool itself is just a thin AppSessionLocal() wrapper around those
# functions (see pool.py's module docstring) and has nothing mode-specific
# left to unit-test without a real app DB connection.


def test_free_mode_fetches_and_caches(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_get(url, timeout):
        calls["count"] += 1
        return httpx.Response(
            200, text="9.9.9.9:80\n8.8.8.8:80\n", request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    pool = ProxyPool("free", free_list_ttl_s=600)

    proxies = {pool.get_proxy() for _ in range(10)}

    assert proxies <= {"http://9.9.9.9:80", "http://8.8.8.8:80"}
    assert calls["count"] == 1  # served from cache after first fetch


def test_free_mode_refetches_after_ttl_expires(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_get(url, timeout):
        calls["count"] += 1
        return httpx.Response(200, text="9.9.9.9:80\n", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    pool = ProxyPool("free", free_list_ttl_s=0)

    pool.get_proxy()
    pool.get_proxy()

    assert calls["count"] == 2


def test_free_mode_falls_back_to_stale_cache_on_fetch_error(monkeypatch) -> None:
    responses = iter(
        [
            httpx.Response(200, text="9.9.9.9:80\n", request=httpx.Request("GET", "http://x")),
            httpx.ConnectError("boom"),
        ]
    )

    def fake_get(url, timeout):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(httpx, "get", fake_get)
    pool = ProxyPool("free", free_list_ttl_s=0)

    first = pool.get_proxy()
    second = pool.get_proxy()

    assert first == "http://9.9.9.9:80"
    assert second == "http://9.9.9.9:80"  # stale cache served, no crash


def test_free_mode_with_no_data_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, timeout: httpx.Response(200, text="", request=httpx.Request("GET", url)),
    )
    pool = ProxyPool("free")

    assert pool.get_proxy() is None


def test_unknown_mode_raises() -> None:
    pool = ProxyPool("bogus")  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        pool.get_proxy()


async def test_delay_sleeps_within_bounds() -> None:
    pool = ProxyPool("single")
    start = time.monotonic()

    await pool.delay(50, 100)

    elapsed_ms = (time.monotonic() - start) * 1000
    assert 50 <= elapsed_ms <= 300  # generous upper bound for test-runner jitter


async def test_delay_rejects_inverted_bounds() -> None:
    pool = ProxyPool("single")

    with pytest.raises(ValueError):
        await pool.delay(100, 50)


def test_to_playwright_proxy_none() -> None:
    assert to_playwright_proxy(None) is None


def test_to_playwright_proxy_basic() -> None:
    assert to_playwright_proxy("http://1.2.3.4:8080") == {"server": "http://1.2.3.4:8080"}


def test_to_playwright_proxy_with_credentials() -> None:
    result = to_playwright_proxy("http://user:pass@1.2.3.4:8080")

    assert result == {
        "server": "http://1.2.3.4:8080",
        "username": "user",
        "password": "pass",
    }
