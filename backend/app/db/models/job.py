import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AppBase

# Lifecycle statuses, shared by `Job.status` and `JobTarget.status`. Kept here
# rather than in the router or the dispatcher because all three plus the workers
# have to agree on what counts as finished.
#
# "paused" and "cancelled" are only ever written by the control endpoints
# (`app.workers.control`); no worker sets them. A *target* can be "cancelled" --
# that is how a job's unstarted areas are retired -- but never "paused", because
# pausing is a property of the job: an area already being scraped either runs to
# completion or is cancelled outright.
ACTIVE_STATUSES = frozenset({"queued", "running"})
TERMINAL_STATUSES = frozenset({"done", "error", "cancelled"})

# Jobs the dispatcher must not hand any more areas to. Note that "paused" is not
# terminal: its targets stay queued and go back on the broker on resume.
HALTED_STATUSES = frozenset({"paused", "cancelled"})


def settled_status(statuses: list[str]) -> str | None:
    """The status a job rolls up to once none of its targets are active.

    None while any target is still queued or running, i.e. "not settled yet".
    A job whose targets all ended cancelled settles as cancelled rather than
    errored -- telling a deliberate stop apart from a failure is the whole point
    of having the state, and reporting one as the other is how a red badge stops
    meaning anything.
    """
    if not statuses or any(s in ACTIVE_STATUSES for s in statuses):
        return None
    if any(s == "done" for s in statuses):
        return "done"
    if any(s == "error" for s in statuses):
        return "error"
    return "cancelled"


class Job(AppBase):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # queued | running | paused | done | error | cancelled -- see the status sets
    # above. Workers only ever write the first two and the last two of those.
    status: Mapped[str] = mapped_column(String(20), default="queued")
    # source: "google" | "bing"
    source: Mapped[str] = mapped_column(String(20))
    # Optional human label set on the New Job Wizard's review step ("Plumbers —
    # Austin Metro"). NULL for jobs created before this existed or through the
    # bare API; the UI falls back to the id in that case.
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    # Set only for jobs the scheduler fired (app.workers.tasks.dispatch_due_schedules).
    # NULL for anything started by a person -- the Schedule & Monitoring screen's
    # run history is exactly "jobs where schedule_id = this schedule".
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("schedules.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Stamped at every status transition (dashboard activity feed derives
    # "started"/"finished" timestamps from this -- there is no separate event log).
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class JobTarget(AppBase):
    """One keyword x location pair belonging to a job.

    The location is normally a single postal code: the search is run per ZIP,
    not per city, so a city with forty ZIPs is forty targets rather than one
    broad query that Maps truncates at ~120 places. `zip_code` plus the
    `city`/`region`/`country` it was picked under are kept alongside the
    rendered `location_label` so results can be attributed back to the area
    they were scraped for -- Google's place panel gives one address string and
    nothing splits it (MODULES 3.4), so the target is the only source for those
    columns. All four stay nullable: a hand-typed location ("Austin, TX") has a
    label and nothing else.

    A target's work is two-phase: scroll the search feed for place URLs, then
    scrape each of those places. `places_found` is set once the feed phase ends
    and `places_done` counts places that reached a terminal outcome (row
    written, nothing to write, or retries exhausted). The target only becomes
    terminal when `places_done >= places_found` -- without the counters there is
    nothing to distinguish "finished" from "finished handing work to the queue",
    which is what made a job report `done` with zero results.

    Creating a job no longer puts every target straight on the broker: the
    dispatcher (`app.workers.dispatch`) hands over only as many as the
    `concurrent_targets` setting allows, so `status == "queued"` covers two
    different things and `dispatched_at` is what separates them. NULL means the
    target is still waiting for a free slot; set means its task is on the queue
    and it is occupying one. `dispatch_id` is the Celery task id of that
    hand-off -- a task whose id no longer matches has been superseded (the
    dispatcher re-queued the target after deciding the original was lost) and
    exits instead of scraping the same area twice.
    """

    __tablename__ = "job_targets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"))
    keyword: Mapped[str] = mapped_column(String(255))
    location_label: Mapped[str] = mapped_column(String(255))
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    places_found: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    places_done: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    dispatch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Stamped whenever a worker proves it still has this target: on pickup
    # (entering "running") and on every place counted off by `_finish_place`.
    # NULL while queued. This is the only signal that tells a target genuinely
    # abandoned by a dead worker/lost broker task apart from one that is merely
    # a slow multi-hour scrape -- Celery's own redelivery only fires if the
    # broker still has the task, which is not the case when the broker itself
    # loses it (restart, eviction). `dispatch._reclaim_stuck_running` uses this
    # to hand the slot back instead of holding it for the lifetime of the
    # deployment.
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
