"""DB-facing half of the proxy pool's "list" mode -- pulled out of
app.scraping.proxy.pool.ProxyPool so it can be unit-tested against a plain
Session (in-memory SQLite in tests) without the pool needing a live app DB.
ProxyPool itself is a thin wrapper that opens `AppSessionLocal()` and calls
these.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.proxy import Proxy

logger = logging.getLogger(__name__)

# After this many blocks in a row, a proxy is auto-cooled rather than kept in
# rotation -- mirrors app.scraping.common.rate_limit's per-host cooldown,
# applied per-proxy instead. Consecutive, not lifetime: a proxy that blocks
# twice then succeeds resets to zero, since a transient host-side block is
# what this guards against, not "this proxy has ever been blocked".
CONSECUTIVE_BLOCKS_BEFORE_COOLING = 3
COOLDOWN_MINUTES = 30


def reactivate_cooled_proxies(db: Session, *, now: datetime | None = None) -> int:
    """A cooling proxy whose window has passed goes back to active. Returns
    how many were reactivated. Called on every pool read rather than on a
    schedule -- "list" mode is read far more often than any beat interval
    would be, so a separate periodic task would just be a slower version of
    the same check."""
    now = now or datetime.utcnow()
    cooled = (
        db.execute(select(Proxy).where(Proxy.status == "cooling", Proxy.cooling_until <= now))
        .scalars()
        .all()
    )
    for row in cooled:
        row.status = "active"
        row.cooling_until = None
    if cooled:
        db.commit()
    return len(cooled)


def select_active_proxy(db: Session, index: int) -> Proxy | None:
    """The `index`-th active proxy, round-robin (mod row count). `index` is
    owned by the caller (ProxyPool._list_index) so consecutive calls rotate
    rather than always returning the first row.

    Ordered by `created_at`, not `id` -- `id` is a random UUID, so sorting by
    it would shuffle rotation order on every process restart for no reason;
    `created_at` at least gives a stable, meaningful order (oldest-added
    first) that ties break consistently within one call.
    """
    rows = (
        db.execute(
            select(Proxy).where(Proxy.status == "active").order_by(Proxy.created_at, Proxy.id)
        )
        .scalars()
        .all()
    )
    if not rows:
        return None
    return rows[index % len(rows)]


def record_proxy_outcome(
    db: Session,
    host: str,
    port: int,
    outcome: str,
    *,
    latency_ms: int,
    consecutive_blocks: dict[str, int],
    now: datetime | None = None,
) -> None:
    """Updates one Proxy row's running counters after a request that used it.

    `consecutive_blocks` is the caller's in-process counter dict (keyed
    "host:port"), mutated in place -- kept out of the database since it only
    needs to survive one process's lifetime, not be shared across workers.
    No-op if the host/port doesn't match any stored row (e.g. it was deleted
    between checkout and outcome).
    """
    now = now or datetime.utcnow()
    row = db.execute(
        select(Proxy).where(Proxy.host == host, Proxy.port == port)
    ).scalar_one_or_none()
    if row is None:
        return

    row.last_used_at = now
    row.latency_ms_total += latency_ms
    row.latency_samples += 1

    key = f"{host}:{port}"
    if outcome == "success":
        row.success_count += 1
        consecutive_blocks[key] = 0
    elif outcome == "failure":
        row.failure_count += 1
    elif outcome == "blocked":
        row.block_count += 1
        consecutive_blocks[key] = consecutive_blocks.get(key, 0) + 1
        if consecutive_blocks[key] >= CONSECUTIVE_BLOCKS_BEFORE_COOLING and row.status == "active":
            row.status = "cooling"
            row.cooling_until = now + timedelta(minutes=COOLDOWN_MINUTES)
            logger.info(
                "proxy auto-cooled after repeated blocks", extra={"host": host, "port": port}
            )

    db.commit()
