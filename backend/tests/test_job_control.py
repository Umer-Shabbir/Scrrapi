"""The queue controls: which transitions are legal, what a job settles at, and
when a worker drops the task it just picked up.

These are the rules that decide whether a pause loses work. The expensive
mistakes are all quiet ones -- a cancelled job that reports "error", a paused job
whose targets keep getting dispatched, a place task that keeps scraping for a job
the user deleted (and then fails on a foreign key when it writes the row) -- so
each is pinned here rather than left to the endpoint that calls it.
"""

import uuid

from app.db.models.job import Job, JobTarget, settled_status
from app.workers.control import can_cancel, can_delete, can_pause, can_resume, job_actions
from app.workers.tasks import _abandon_reason, _place_halt_reason


class StubSession:
    """Just enough Session for the halt check: `expire_all` and one lookup."""

    def __init__(self, row=None):
        self.row = row

    def expire_all(self):
        pass

    def get(self, _model, _key):
        return self.row


def _job(status: str) -> Job:
    return Job(id=uuid.uuid4(), status=status, source="google")


# ---------------------------------------------------------- allowed transitions


def test_only_live_jobs_can_be_paused():
    assert can_pause("queued")
    assert can_pause("running")
    assert not can_pause("paused")  # already there
    assert not can_pause("done")
    assert not can_pause("cancelled")


def test_only_a_paused_job_can_be_resumed():
    assert can_resume("paused")
    assert not can_resume("running")
    assert not can_resume("done")


def test_anything_unfinished_can_be_cancelled_including_a_paused_job():
    # Pause, look at what came back, drop the rest is the normal way a run gets
    # abandoned -- refusing to cancel from "paused" would force a resume first.
    assert can_cancel("paused")
    assert can_cancel("queued")
    assert can_cancel("running")
    assert not can_cancel("done")
    assert not can_cancel("error")
    assert not can_cancel("cancelled")


def test_delete_is_allowed_from_every_status():
    """A live job is cancelled on the way out; refusing until the user stops it
    first is the same two steps with an error in between."""
    for status in ("queued", "running", "paused", "done", "error", "cancelled"):
        assert can_delete(status)


def test_actions_block_matches_the_predicates():
    assert job_actions("running") == {
        "pause": True,
        "resume": False,
        "cancel": True,
        "delete": True,
    }
    assert job_actions("done") == {
        "pause": False,
        "resume": False,
        "cancel": False,
        "delete": True,
    }


# --------------------------------------------------------------- settled status


def test_a_job_is_unsettled_while_any_target_is_active():
    assert settled_status(["done", "running"]) is None
    assert settled_status(["done", "queued"]) is None


def test_no_targets_is_not_settled():
    """An empty list means the rows aren't visible to this session yet, not that
    the job finished -- settling on it would mark a job done before it started."""
    assert settled_status([]) is None


def test_one_success_is_enough_to_call_the_job_done():
    assert settled_status(["done", "error", "cancelled"]) == "done"


def test_errors_outrank_cancellations():
    assert settled_status(["error", "cancelled"]) == "error"


def test_an_all_cancelled_job_settles_as_cancelled_not_error():
    # Reporting a deliberate stop as a failure is how a red badge stops meaning
    # anything.
    assert settled_status(["cancelled", "cancelled"]) == "cancelled"


# ------------------------------------------------------- worker abandon checks


def test_a_task_for_a_live_job_carries_on():
    assert _abandon_reason(_job("queued")) is None
    assert _abandon_reason(_job("running")) is None


def test_a_task_picked_up_after_a_pause_is_abandoned():
    """Revocation is a best-effort broadcast, so the row is what decides."""
    assert _abandon_reason(_job("paused")) == "paused"


def test_a_task_for_a_cancelled_or_deleted_job_is_abandoned():
    assert _abandon_reason(_job("cancelled")) == "cancelled"
    assert _abandon_reason(None) == "missing"


def test_place_tasks_keep_going_while_the_job_is_paused():
    # Pause stops new areas, not the area already open: dropping its places would
    # strand the target's places_done short of places_found, and it would never
    # reach a terminal state.
    assert _place_halt_reason(StubSession(_job("paused")), str(uuid.uuid4())) is None


def test_place_tasks_drop_themselves_when_the_job_is_cancelled_or_gone():
    assert _place_halt_reason(StubSession(_job("cancelled")), str(uuid.uuid4())) == "cancelled"
    assert _place_halt_reason(StubSession(None), str(uuid.uuid4())) == "missing"


def test_target_rows_are_untouched_by_the_status_helpers():
    """`settled_status` reads target statuses; make sure a target's own vocabulary
    (which never includes "paused") is what it is being fed."""
    target = JobTarget(id=uuid.uuid4(), status="cancelled")
    assert settled_status([target.status]) == "cancelled"
