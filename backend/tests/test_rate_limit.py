"""Unit tests for 11.3: 429 detection and the escalating per-host cooldown.

No browser here -- `check_response` only needs an object with `.status` and
`.headers`, so a stub response covers the detection paths.
"""

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import pytest

from app.scraping.common.rate_limit import (
    RateLimited,
    RateLimitTracker,
    is_block_page,
    parse_retry_after,
)


class StubResponse:
    def __init__(self, status: int, headers: dict[str, str] | None = None):
        self.status = status
        self.headers = headers or {}


@pytest.fixture
def tracker(monkeypatch):
    """A fresh tracker, also installed as the module singleton `check_response` uses."""
    instance = RateLimitTracker(base_cooldown_s=10.0, max_cooldown_s=100.0)
    monkeypatch.setattr(
        "app.scraping.common.rate_limit.get_tracker", lambda: instance, raising=True
    )
    return instance


def _check(response, url):
    from app.scraping.common import rate_limit

    return rate_limit.check_response(response, url)


def test_ok_response_is_not_rate_limited(tracker):
    _check(StubResponse(200), "https://www.google.com/maps/place/x")
    assert tracker.cooldown_remaining("www.google.com") == 0


def test_404_is_the_places_problem_not_a_block(tracker):
    _check(StubResponse(404), "https://www.google.com/maps/place/x")
    assert tracker.cooldown_remaining("www.google.com") == 0


@pytest.mark.parametrize("status", [429, 503])
def test_rate_limit_statuses_raise(tracker, status):
    with pytest.raises(RateLimited) as excinfo:
        _check(StubResponse(status), "https://www.google.com/maps/search/x")
    assert excinfo.value.status == status
    assert tracker.cooldown_remaining("www.google.com") > 0


def test_block_interstitial_raises_despite_200(tracker):
    with pytest.raises(RateLimited) as excinfo:
        _check(StubResponse(200), "https://www.google.com/sorry/index?continue=...")
    assert excinfo.value.reason == "blocked interstitial"


def test_cooldown_doubles_per_consecutive_hit_and_caps(tracker):
    url = "https://www.google.com/maps"
    assert tracker.record_rate_limited(url) == 10.0
    assert tracker.record_rate_limited(url) == 20.0
    assert tracker.record_rate_limited(url) == 40.0
    assert tracker.record_rate_limited(url) == 80.0
    assert tracker.record_rate_limited(url) == 100.0  # capped
    assert tracker.record_rate_limited(url) == 100.0


def test_success_resets_escalation(tracker):
    url = "https://www.google.com/maps"
    tracker.record_rate_limited(url)
    tracker.record_rate_limited(url)
    tracker.record_success(url)
    assert tracker.cooldown_remaining("www.google.com") == 0
    assert tracker.record_rate_limited(url) == 10.0


def test_retry_after_header_wins_when_longer(tracker):
    with pytest.raises(RateLimited) as excinfo:
        _check(
            StubResponse(429, {"retry-after": "300"}),
            "https://www.bing.com/maps/search",
        )
    assert excinfo.value.retry_after == 300.0


def test_request_during_cooldown_is_refused_before_launching_a_browser(tracker):
    url = "https://www.google.com/maps"
    tracker.record_rate_limited(url)
    with pytest.raises(RateLimited) as excinfo:
        tracker.raise_if_cooling_down(url)
    assert excinfo.value.reason == "host in cooldown"


def test_hosts_are_tracked_independently(tracker):
    tracker.record_rate_limited("https://www.google.com/maps")
    assert tracker.cooldown_remaining("www.bing.com") == 0


def test_parse_retry_after_seconds():
    assert parse_retry_after("120") == 120.0


def test_parse_retry_after_http_date():
    future = datetime.now(tz=UTC) + timedelta(seconds=60)
    parsed = parse_retry_after(format_datetime(future))
    assert parsed is not None and 50 <= parsed <= 61


def test_parse_retry_after_garbage_is_none():
    assert parse_retry_after("soon") is None
    assert parse_retry_after(None) is None


@pytest.mark.parametrize(
    "url,blocked",
    [
        ("https://www.google.com/sorry/index", True),
        ("https://www.bing.com/challenge?ref=x", True),
        ("https://www.google.com/maps/place/Some+Cafe", False),
    ],
)
def test_is_block_page(url, blocked):
    assert is_block_page(url) is blocked
