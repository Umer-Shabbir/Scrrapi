"""Unit tests for 11.1: the retry countdown that replaced the legacy watchdog."""

import pytest

from app.core.config import get_settings
from app.scraping.common.rate_limit import RateLimited
from app.workers.tasks import retries_left, retry_countdown

settings = get_settings()


class StubTask:
    """Minimal stand-in for a bound Celery task's retry bookkeeping."""

    def __init__(self, retries: int, max_retries: int | None):
        self.max_retries = max_retries
        self.request = type("Request", (), {"retries": retries})()


@pytest.fixture(autouse=True)
def _no_jitter(monkeypatch):
    """Pin the jitter factor to 1.0 so the exponential curve is assertable."""
    monkeypatch.setattr("app.workers.tasks.random.uniform", lambda a, b: 1.0)


def test_backoff_doubles_per_attempt():
    base = settings.task_retry_backoff_base_s
    assert retry_countdown(0) == pytest.approx(base)
    assert retry_countdown(1) == pytest.approx(base * 2)
    assert retry_countdown(2) == pytest.approx(base * 4)


def test_backoff_is_capped():
    assert retry_countdown(50) == pytest.approx(settings.task_retry_backoff_max_s)


def test_rate_limited_cooldown_floors_the_countdown():
    exc = RateLimited("https://www.google.com/maps", status=429, retry_after=450.0)
    assert retry_countdown(0, exc) == pytest.approx(450.0)


def test_generic_backoff_wins_when_longer_than_the_hosts_hint():
    exc = RateLimited("https://www.google.com/maps", status=429, retry_after=1.0)
    assert retry_countdown(3, exc) == pytest.approx(settings.task_retry_backoff_base_s * 8)


def test_retries_left_until_the_cap():
    assert retries_left(StubTask(retries=0, max_retries=2))
    assert retries_left(StubTask(retries=1, max_retries=2))


def test_no_retries_left_at_the_cap():
    """The exhaustion branch marks the row "error" -- it must actually be reached.

    Celery re-raises the original exception (not MaxRetriesExceededError) when
    `retry(exc=...)` runs out of attempts, so this check, not an except clause,
    is what makes a stuck target/export land in a terminal state.
    """
    assert not retries_left(StubTask(retries=2, max_retries=2))
    assert not retries_left(StubTask(retries=9, max_retries=2))


def test_unlimited_retries_when_max_is_none():
    assert retries_left(StubTask(retries=99, max_retries=None))


def test_jitter_spreads_retries(monkeypatch):
    """With jitter live, two tasks failing at the same attempt don't line up."""
    monkeypatch.undo()
    values = {retry_countdown(2) for _ in range(20)}
    assert len(values) > 1
    jitter = settings.task_retry_jitter
    nominal = settings.task_retry_backoff_base_s * 4
    assert all(nominal * (1 - jitter) <= v <= nominal * (1 + jitter) for v in values)
