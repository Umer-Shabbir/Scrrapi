"""app.scraping.proxy.store against in-memory SQLite -- these are the
DB-backed round-robin/cooldown/outcome-recording behaviors ProxyPool's "list"
mode delegates to; see pool.py's module docstring for why the split exists
(a real app DB isn't available to the unit test suite)."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import AppBase
from app.db.models.proxy import Proxy
from app.scraping.proxy.store import (
    CONSECUTIVE_BLOCKS_BEFORE_COOLING,
    reactivate_cooled_proxies,
    record_proxy_outcome,
    select_active_proxy,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    AppBase.metadata.create_all(engine, tables=[Proxy.__table__])
    with Session(engine) as session:
        yield session


@pytest.fixture
def add_proxy():
    """Explicit, strictly increasing timestamps rather than relying on
    wall-clock insert order -- created_at has millisecond resolution and
    several inserts in a tight test loop can tie, which would make
    round-robin order flaky."""
    counter = {"next": datetime(2026, 1, 1)}

    def _add(db: Session, host: str, port: int = 8080, status: str = "active") -> Proxy:
        proxy = Proxy(host=host, port=port, status=status, created_at=counter["next"])
        counter["next"] += timedelta(seconds=1)
        db.add(proxy)
        db.commit()
        return proxy

    return _add


def test_select_active_proxy_round_robins(db, add_proxy) -> None:
    add_proxy(db, "1.1.1.1")
    add_proxy(db, "2.2.2.2")
    add_proxy(db, "3.3.3.3")

    seen = [select_active_proxy(db, i).host for i in range(4)]

    assert seen == ["1.1.1.1", "2.2.2.2", "3.3.3.3", "1.1.1.1"]


def test_select_active_proxy_skips_non_active(db, add_proxy) -> None:
    add_proxy(db, "1.1.1.1", status="disabled")
    add_proxy(db, "2.2.2.2", status="active")
    add_proxy(db, "3.3.3.3", status="retired")

    assert select_active_proxy(db, 0).host == "2.2.2.2"
    assert select_active_proxy(db, 1).host == "2.2.2.2"  # only one active row


def test_select_active_proxy_empty_pool_returns_none(db) -> None:
    assert select_active_proxy(db, 0) is None


def test_record_outcome_success_increments_and_resets_block_streak(db, add_proxy) -> None:
    add_proxy(db, "1.1.1.1", 8080)
    blocks: dict[str, int] = {"1.1.1.1:8080": 2}

    record_proxy_outcome(db, "1.1.1.1", 8080, "success", latency_ms=120, consecutive_blocks=blocks)

    row = select_active_proxy(db, 0)
    assert row.success_count == 1
    assert row.latency_samples == 1
    assert row.latency_ms_total == 120
    assert blocks["1.1.1.1:8080"] == 0


def test_record_outcome_failure_increments_failure_count(db, add_proxy) -> None:
    add_proxy(db, "1.1.1.1", 8080)

    record_proxy_outcome(db, "1.1.1.1", 8080, "failure", latency_ms=50, consecutive_blocks={})

    row = select_active_proxy(db, 0)
    assert row.failure_count == 1
    assert row.success_count == 0


def test_record_outcome_auto_cools_after_consecutive_blocks(db, add_proxy) -> None:
    add_proxy(db, "1.1.1.1", 8080)
    blocks: dict[str, int] = {}

    for _ in range(CONSECUTIVE_BLOCKS_BEFORE_COOLING):
        record_proxy_outcome(db, "1.1.1.1", 8080, "blocked", latency_ms=10, consecutive_blocks=blocks)

    assert select_active_proxy(db, 0) is None  # no longer active -- cooling


def test_record_outcome_below_threshold_stays_active(db, add_proxy) -> None:
    add_proxy(db, "1.1.1.1", 8080)
    blocks: dict[str, int] = {}

    for _ in range(CONSECUTIVE_BLOCKS_BEFORE_COOLING - 1):
        record_proxy_outcome(db, "1.1.1.1", 8080, "blocked", latency_ms=10, consecutive_blocks=blocks)

    assert select_active_proxy(db, 0) is not None


def test_record_outcome_success_after_blocks_prevents_cooling(db, add_proxy) -> None:
    add_proxy(db, "1.1.1.1", 8080)
    blocks: dict[str, int] = {}

    record_proxy_outcome(db, "1.1.1.1", 8080, "blocked", latency_ms=10, consecutive_blocks=blocks)
    record_proxy_outcome(db, "1.1.1.1", 8080, "blocked", latency_ms=10, consecutive_blocks=blocks)
    record_proxy_outcome(db, "1.1.1.1", 8080, "success", latency_ms=10, consecutive_blocks=blocks)
    record_proxy_outcome(db, "1.1.1.1", 8080, "blocked", latency_ms=10, consecutive_blocks=blocks)
    record_proxy_outcome(db, "1.1.1.1", 8080, "blocked", latency_ms=10, consecutive_blocks=blocks)

    # 2 blocks, reset by a success, then 2 more blocks -- never reached 3 in a row.
    assert select_active_proxy(db, 0) is not None


def test_record_outcome_unknown_host_is_a_noop(db) -> None:
    record_proxy_outcome(db, "9.9.9.9", 8080, "success", latency_ms=10, consecutive_blocks={})
    # No error, and nothing to assert on -- the point is this doesn't raise.


def test_reactivate_cooled_proxies_only_past_the_window(db, add_proxy) -> None:
    still_cooling = add_proxy(db, "1.1.1.1", status="cooling")
    still_cooling.cooling_until = datetime.utcnow() + timedelta(minutes=10)
    past_cooling = add_proxy(db, "2.2.2.2", status="cooling")
    past_cooling.cooling_until = datetime.utcnow() - timedelta(minutes=1)
    db.commit()

    reactivated = reactivate_cooled_proxies(db)

    assert reactivated == 1
    db.refresh(still_cooling)
    db.refresh(past_cooling)
    assert still_cooling.status == "cooling"
    assert past_cooling.status == "active"
    assert past_cooling.cooling_until is None
