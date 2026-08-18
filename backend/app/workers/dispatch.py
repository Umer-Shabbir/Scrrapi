"""The concurrency gate in front of the scrape queue.

Before this existed, `POST /api/jobs` called `.delay()` once per target and the
whole job landed on the broker in one go. Nothing bounded it: queue two hundred
ZIP codes and two hundred feed tasks were pending immediately, every one of them
holding a browser slot the moment a worker thread came free. The number of areas
actually being scraped at once was whatever the worker pool happened to be sized
at, which is a deploy-time flag nobody can change from the app.

So targets are now created "queued but not dispatched" and handed to the broker
a slot at a time. A slot is occupied by any target that is

  * `running`  -- a worker has it, or
  * `queued` with `dispatched_at` set -- its task is on the broker.

and `concurrent_targets` (app.core.runtime_settings, edited from the Settings
page) says how many slots there are. `dispatch_ready_targets` is called whenever
that arithmetic can have changed: a job is created, a target reaches a terminal
state, or the setting itself is raised.

Two processes can free a slot at the same instant, so claiming is serialised
with a Postgres advisory lock rather than optimism -- without it, two workers
both read "1 slot free" and dispatch two targets into it, and the limit the user
set quietly stops meaning anything.

Note the scope of the limit: it counts *areas* (keyword x location targets), not
browser tabs. Inside one area, the individual business pages its feed produced
are ordinary queue work, bounded by the worker pool's own `--concurrency`. That
pool is started fixed at `max_concurrent_targets` (scripts/dev.mjs,
docker-compose.yml) rather than tuned separately -- Celery has no way to
live-resize a running pool on every backend, so instead of a second knob to
keep in sync with this one, the pool is simply always big enough for whatever
`concurrent_targets` (this module) lets through. Idle threads/processes cost
nothing: a browser only opens once a task is actually picked up.

A paused or cancelled job is simply not a source of waiting targets (see
`_runnable_job`), which is all "pause" means mechanically: its rows stay exactly
where they are and stop being eligible. That is why pausing costs nothing and
resuming loses nothing.

A "running" target is assumed to have a worker, per `count_in_flight`'s
docstring -- but that assumption breaks if the worker dies or the broker loses
the task after pickup and before the next heartbeat. Celery's own
`task_reject_on_worker_lost` only redelivers a task the broker still has; if
the broker itself is what lost it (restart, eviction), nothing brings it back
and the row is orphaned at "running" forever, permanently holding a slot.
`_reclaim_stuck_running` is the sweep that catches that case using
`JobTarget.heartbeat_at`, stamped by the worker on pickup and on every place
it finishes (see `app.workers.tasks`).
"""

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.runtime_settings import get_concurrent_targets
from app.db.models.job import HALTED_STATUSES, Job, JobTarget

logger = logging.getLogger(__name__)
settings = get_settings()

# Any constant works as long as every process picks the same one; this is just a
# recognisable value to see in `pg_locks` while debugging.
_DISPATCH_LOCK_KEY = 0x1EAD_6E17


def _occupies_a_slot():
    """Targets that are using up one of the `concurrent_targets` slots."""
    return or_(
        JobTarget.status == "running",
        and_(JobTarget.status == "queued", JobTarget.dispatched_at.is_not(None)),
    )


def _waiting_for_a_slot():
    """Targets created but never handed to the broker."""
    return and_(JobTarget.status == "queued", JobTarget.dispatched_at.is_(None))


def _runnable_job():
    """Jobs that still want work. Excludes paused and cancelled ones."""
    return Job.status.notin_(tuple(HALTED_STATUSES))


def count_in_flight(db: Session) -> int:
    """Slots in use. Deliberately not filtered by job status: a paused job's
    running areas are still holding real browsers, and pretending otherwise
    would let the dispatcher hand out slots that don't exist."""
    return db.scalar(select(func.count()).select_from(JobTarget).where(_occupies_a_slot())) or 0


def count_waiting(db: Session) -> int:
    """Targets that would start if a slot came free right now -- so, unlike the
    in-flight count, this one *does* exclude paused and cancelled jobs. Their
    areas are queued but not waiting for anything, and counting them makes the
    Settings page report a backlog that will never move."""
    return (
        db.scalar(
            select(func.count())
            .select_from(JobTarget)
            .join(Job, Job.id == JobTarget.job_id)
            .where(_waiting_for_a_slot(), _runnable_job())
        )
        or 0
    )


def dispatch_ready_targets(db: Session) -> int:
    """Fill every free slot from the waiting targets. Returns how many started.

    Safe to call from anywhere and as often as you like -- with no free slots or
    nothing waiting it is two counts and a return.
    """
    claimed = _claim_slots(db)
    if not claimed:
        return 0

    # Deferred: app.workers.tasks imports this module, so importing it at module
    # level would be circular.
    from app.workers import tasks

    task_for_source = {
        "google": tasks.scrape_google_maps,
        "bing": tasks.scrape_bing_maps,
    }
    for target_id, source, task_id in claimed:
        task = task_for_source.get(source, tasks.scrape_google_maps)
        # The task id is chosen here rather than by Celery because it was already
        # written to `dispatch_id` inside the claim transaction -- that is what
        # lets a superseded copy of the task recognise itself and exit.
        task.apply_async(args=[str(target_id)], task_id=task_id)

    logger.info("targets dispatched", extra={"count": len(claimed)})
    return len(claimed)


def _claim_slots(db: Session) -> list[tuple[uuid.UUID, str, str]]:
    """Reserve as many waiting targets as there are free slots.

    Everything up to the commit runs under the advisory lock, so the read of
    "how many are in flight" and the write that puts more in flight can't
    interleave with another process doing the same thing.

    Returns `(target_id, source, task_id)` and leaves the sending to the caller:
    the rows must be committed before their tasks exist, or a worker can pick one
    up and find the target still looking undispatched.
    """
    _lock(db)
    try:
        reclaimed = _reclaim_lost_dispatches(db)
        if reclaimed:
            logger.warning(
                "re-queued targets whose dispatch never started",
                extra={"count": reclaimed, "stale_after_s": settings.target_dispatch_stale_s},
            )

        stuck = _reclaim_stuck_running(db)
        if stuck:
            logger.warning(
                "re-queued running targets with no heartbeat",
                extra={"count": stuck, "stale_after_s": settings.target_running_stale_s},
            )

        free_slots = get_concurrent_targets(db) - count_in_flight(db)
        if free_slots <= 0:
            return []

        # Oldest job first, so a job that was queued while a big one was running
        # doesn't have its targets interleaved with the backlog forever.
        rows = db.execute(
            select(JobTarget.id, Job.source)
            .join(Job, Job.id == JobTarget.job_id)
            .where(_waiting_for_a_slot(), _runnable_job())
            .order_by(Job.created_at, JobTarget.id)
            .limit(free_slots)
        ).all()
        if not rows:
            return []

        now = datetime.utcnow()
        claimed = [(row.id, row.source, str(uuid.uuid4())) for row in rows]
        for target_id, _source, task_id in claimed:
            db.execute(
                update(JobTarget)
                .where(JobTarget.id == target_id)
                .values(dispatched_at=now, dispatch_id=task_id)
            )
        return claimed
    finally:
        # Commits the claim and releases the transaction-scoped advisory lock.
        # On the empty paths this is just how the lock is given back.
        db.commit()


def _reclaim_lost_dispatches(db: Session) -> int:
    """Hand back slots held by targets whose task will never run.

    A worker killed between the claim and the first ack leaves a target sitting
    at "queued, dispatched" with nothing on the broker, and that slot would
    otherwise be lost for the lifetime of the deployment. Time is the only
    signal available -- Celery cannot tell "still waiting in the queue" from
    "gone" -- so the window is deliberately generous, and a target that is
    merely slow to start getting re-issued is harmless: the original task sees
    its `dispatch_id` no longer matches and exits without scraping.

    Only ever touches targets still in `queued`. One that reached `running` has
    a worker, and Celery's own `task_reject_on_worker_lost` is what recovers it.
    """
    cutoff = datetime.utcnow() - timedelta(seconds=settings.target_dispatch_stale_s)
    result = db.execute(
        update(JobTarget)
        .where(
            JobTarget.status == "queued",
            JobTarget.dispatched_at.is_not(None),
            JobTarget.dispatched_at < cutoff,
        )
        .values(dispatched_at=None, dispatch_id=None)
    )
    return result.rowcount or 0


def _reclaim_stuck_running(db: Session) -> int:
    """Hand back slots held by "running" targets whose worker is gone.

    `heartbeat_at` is stamped on pickup and on every place finished, so a
    target still genuinely being scraped keeps refreshing it no matter how
    long the feed takes. One that stops -- worker killed, broker restarted
    and lost the task after delivery -- has no such update coming, and
    `target_running_stale_s` is deliberately long precisely so this never
    fires on a target that is merely slow rather than dead.

    Sent back to "queued, not dispatched" rather than straight to "error": the
    dispatcher re-issues it like any other waiting target next slot, and if
    the original task somehow *is* still alive, `_is_superseded` will not
    match this row's cleared `dispatch_id` -- it exits instead of scraping the
    area twice.
    """
    cutoff = datetime.utcnow() - timedelta(seconds=settings.target_running_stale_s)
    result = db.execute(
        update(JobTarget)
        .where(
            JobTarget.status == "running",
            JobTarget.heartbeat_at.is_not(None),
            JobTarget.heartbeat_at < cutoff,
        )
        .values(status="queued", dispatched_at=None, dispatch_id=None, heartbeat_at=None)
    )
    return result.rowcount or 0


def _lock(db: Session) -> None:
    """Serialise claiming across API and worker processes.

    `pg_advisory_xact_lock` blocks until it is granted and is released by the
    commit in `_claim_slots`, so there is no lock to leak on an exception. Other
    backends (the SQLite used by some tests) have no equivalent; they run
    single-process, where the lock has nothing to protect against anyway.
    """
    if db.get_bind().dialect.name != "postgresql":
        return
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _DISPATCH_LOCK_KEY})
