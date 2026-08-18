"""Pause, resume, cancel and delete for a job and everything hanging off it.

Until this existed a job was a one-way trip: once `POST /api/jobs` returned, the
only way to stop a two-thousand-ZIP run that was pointed at the wrong state was
to flush the broker, and the only way to get rid of a finished one was to open
psql. These four operations are what the Dashboard's row actions call.

What each one actually does, because the differences matter:

**pause** is a queue gate, not a freeze. The job stops being a source of work for
the dispatcher (`dispatch._runnable_job`), and any area that was handed to the
broker but not yet picked up is revoked and put back in the waiting pool, so its
slot goes to another job immediately. Areas *already being scraped* run to
completion. That is deliberate: a feed scrape holds the only copy of the place
URLs it scrolled, so killing one mid-flight doesn't save the work, it throws it
away and guarantees the whole area is re-scraped -- and the places already
written would come back as duplicate rows. With the default concurrency of a few
slots, "finish what's open, start nothing new" settles within one area's worth of
work, and it's resumable without losing or double-writing a single row.

**resume** puts the job back in the pool and dispatches straight away rather than
waiting for some other job's target to finish. A job whose areas all finished
while it was paused resumes directly into its settled status.

**cancel** is terminal. Every target that hasn't finished is marked "cancelled",
its task is revoked (running ones with `terminate`, so a wedged browser doesn't
hold a slot for another twenty minutes), and the results already collected are
kept -- cancelling half a run is normally how you stop paying for the rest of it,
not how you throw away what it found. Exporting a cancelled job still works.

**delete** removes the job, its targets, its results and its exports, including
the generated export files on disk. A job that is still live is cancelled first,
so nothing is left running against rows that no longer exist.

Revocation is best-effort by design. `celery_app.control.revoke` is a broadcast
to whatever workers are listening; a worker that is down, or a broker that is
unreachable, means a task can still be delivered later. That is why every task
body re-checks the job's status when it starts (`tasks._abandon_reason`) -- the
database, not the broker, is what decides whether work is still wanted.
"""

import logging
import os
import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.events import publish_job_event
from app.db.models.export import Export
from app.db.models.job import (
    ACTIVE_STATUSES,
    HALTED_STATUSES,
    TERMINAL_STATUSES,
    Job,
    JobTarget,
    settled_status,
)
from app.db.models.result import Result, ResultHistory
from app.workers.dispatch import dispatch_ready_targets

logger = logging.getLogger(__name__)


# --------------------------------------------------------------- what's allowed
#
# Pure functions of the status string, so the UI can grey out a button using the
# same rule the endpoint enforces (they ride along on every job payload as
# `actions`) and so they can be unit-tested without a database.


def can_pause(status: str) -> bool:
    return status in ACTIVE_STATUSES


def can_resume(status: str) -> bool:
    return status == "paused"


def can_cancel(status: str) -> bool:
    """Anything not already finished -- including a paused job, which is the
    normal way a run gets abandoned: pause it, look at what came back, drop it."""
    return status not in TERMINAL_STATUSES


def can_delete(_status: str) -> bool:
    """Always. A running job is cancelled on the way out rather than refused --
    "you must stop it before you can delete it" is a two-click way of saying yes."""
    return True


def job_actions(status: str) -> dict:
    return {
        "pause": can_pause(status),
        "resume": can_resume(status),
        "cancel": can_cancel(status),
        "delete": can_delete(status),
    }


# ------------------------------------------------------------------- operations


def pause_job(db: Session, job: Job) -> dict:
    """Stop starting new areas. Returns what the pause caught.

    The status is committed *before* anything is revoked: `dispatch_ready_targets`
    runs in the API process and in every worker, and a target released while the
    job still looked runnable would simply be picked straight back up.
    """
    job.status = "paused"
    db.commit()

    released = _release_undispatched(db, job.id)
    still_running = _count_targets(db, job.id, ("running",))

    publish_job_event(str(job.id), "job_paused", released=released, stillRunning=still_running)
    logger.info(
        "job paused",
        extra={"job_id": str(job.id), "released": released, "still_running": still_running},
    )

    # The released slots belong to whoever is waiting behind them -- usually
    # another job, which is the point of pausing this one.
    dispatch_ready_targets(db)
    return {"released": released, "stillRunning": still_running}


def resume_job(db: Session, job: Job) -> dict:
    """Put the job back in the dispatch pool and fill any free slots now."""
    statuses = _target_statuses(db, job.id)
    # A paused job whose in-flight areas all finished has nothing left to resume;
    # it resumes straight into whatever it would have settled at.
    job.status = settled_status(statuses) or ("running" if "running" in statuses else "queued")
    db.commit()

    started = dispatch_ready_targets(db)
    publish_job_event(str(job.id), "job_resumed", status=job.status, dispatched=started)
    logger.info("job resumed", extra={"job_id": str(job.id), "dispatched": started})
    return {"dispatched": started, "status": job.status}


def cancel_job(db: Session, job: Job) -> dict:
    """Retire every unfinished area. Results already written are kept."""
    running = _dispatch_ids(db, job.id, ("running",))
    queued = _dispatch_ids(db, job.id, ("queued",))

    cancelled = db.execute(
        update(JobTarget)
        .where(JobTarget.job_id == job.id, JobTarget.status.in_(tuple(ACTIVE_STATUSES)))
        .values(status="cancelled", dispatched_at=None, dispatch_id=None)
    ).rowcount or 0
    job.status = "cancelled"
    db.commit()

    # Order matters the same way it does in `pause_job`: the rows say "cancelled"
    # before the revokes go out, so a task that slips through the broadcast finds
    # a cancelled job and drops itself (tasks._abandon_reason).
    _revoke(queued)
    # A running feed scrape can sit inside one Playwright call for minutes and has
    # no checkpoint to notice the cancel at, so this one is a kill.
    _revoke(running, terminate=True)

    publish_job_event(str(job.id), "job_cancelled", targetsCancelled=cancelled)
    logger.info(
        "job cancelled",
        extra={"job_id": str(job.id), "targets": cancelled, "terminated": len(running)},
    )

    dispatch_ready_targets(db)
    return {"targetsCancelled": cancelled, "terminated": len(running)}


def delete_job(db: Session, job: Job) -> dict:
    """Remove the job and everything under it: targets, results, exports, files.

    Returns the counts, so the UI can say what actually went ("deleted 1 job,
    412 results, 2 exports") instead of a bare success toast.
    """
    job_id = job.id
    was_live = job.status not in TERMINAL_STATUSES
    if was_live:
        # Stop the work before the rows it writes into disappear underneath it.
        cancel_job(db, job)

    exports = db.execute(select(Export).where(Export.job_id == job_id)).scalars().all()
    files_removed = sum(_remove_export_file(export) for export in exports)

    # Plain DELETEs rather than ORM cascades: none of these relationships are
    # mapped (the models carry bare ForeignKeys), and a job can hold six figures
    # of result rows, which is not something to load into memory to throw away.
    #
    # result_history rows FK onto results.id (not job_id directly), and have to
    # go first -- deleting results while a re-scrape had already written history
    # against them raised psycopg.errors.ForeignKeyViolation on
    # result_history_result_id_fkey (see logs/api.log).
    export_count = db.execute(delete(Export).where(Export.job_id == job_id)).rowcount or 0
    db.execute(
        delete(ResultHistory).where(
            ResultHistory.result_id.in_(select(Result.id).where(Result.job_id == job_id))
        )
    )
    result_count = db.execute(delete(Result).where(Result.job_id == job_id)).rowcount or 0
    target_count = db.execute(delete(JobTarget).where(JobTarget.job_id == job_id)).rowcount or 0
    db.delete(job)
    db.commit()

    logger.info(
        "job deleted",
        extra={
            "job_id": str(job_id),
            "targets": target_count,
            "results": result_count,
            "exports": export_count,
            "files_removed": files_removed,
            "was_live": was_live,
        },
    )

    # Cancelling above freed slots; nothing else will call this now that the job
    # is gone, so it happens here.
    dispatch_ready_targets(db)
    return {
        "jobId": str(job_id),
        "wasLive": was_live,
        "targets": target_count,
        "results": result_count,
        "exports": export_count,
        "filesRemoved": files_removed,
    }


# ---------------------------------------------------------------------- helpers


def _release_undispatched(db: Session, job_id: uuid.UUID) -> int:
    """Hand back the slots of targets that are on the broker but not started.

    Same shape as `dispatch._reclaim_lost_dispatches`, different trigger: there
    it's a timeout, here it's the user. Only "queued" rows are touched -- one
    that reached "running" has a browser open and is left to finish.
    """
    task_ids = _dispatch_ids(db, job_id, ("queued",))
    released = db.execute(
        update(JobTarget)
        .where(
            JobTarget.job_id == job_id,
            JobTarget.status == "queued",
            JobTarget.dispatched_at.is_not(None),
        )
        .values(dispatched_at=None, dispatch_id=None)
    ).rowcount or 0
    db.commit()

    _revoke(task_ids)
    return released


def _dispatch_ids(db: Session, job_id: uuid.UUID, statuses: tuple[str, ...]) -> list[str]:
    return [
        row
        for row in db.execute(
            select(JobTarget.dispatch_id).where(
                JobTarget.job_id == job_id,
                JobTarget.status.in_(statuses),
                JobTarget.dispatch_id.is_not(None),
            )
        ).scalars()
        if row
    ]


def _target_statuses(db: Session, job_id: uuid.UUID) -> list[str]:
    return list(
        db.execute(select(JobTarget.status).where(JobTarget.job_id == job_id)).scalars().all()
    )


def _count_targets(db: Session, job_id: uuid.UUID, statuses: tuple[str, ...]) -> int:
    return sum(1 for s in _target_statuses(db, job_id) if s in statuses)


def _revoke(task_ids: list[str], *, terminate: bool = False) -> None:
    """Tell the workers to drop these tasks. Never raises.

    A failure here is not a failed pause: the rows have already been written, and
    `tasks._abandon_reason` re-reads them when a task starts, so the worst case is
    a task that spins up, sees the job is halted, and exits without scraping.
    """
    if not task_ids:
        return
    try:
        celery_app.control.revoke(task_ids, terminate=terminate, signal="SIGTERM")
    except Exception:  # noqa: BLE001 -- broker down, kombu error, anything
        logger.warning(
            "could not revoke tasks; relying on the in-task job status check",
            extra={"tasks": len(task_ids), "terminate": terminate},
            exc_info=True,
        )


def _remove_export_file(export: Export) -> bool:
    """Delete one generated export from disk. Missing is fine; anything else is
    logged and swallowed, because a file that won't unlink must not block the
    row deletion and leave the job half-gone."""
    if not export.file_path:
        return False
    try:
        os.remove(export.file_path)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        logger.warning(
            "could not remove export file",
            extra={"export_id": str(export.id), "file_path": export.file_path},
            exc_info=True,
        )
        return False


__all__ = [
    "HALTED_STATUSES",
    "can_cancel",
    "can_delete",
    "can_pause",
    "can_resume",
    "cancel_job",
    "delete_job",
    "job_actions",
    "pause_job",
    "resume_job",
    "settled_status",
]
