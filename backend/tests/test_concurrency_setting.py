"""The scrape concurrency limit: clamping, reading, and the superseded-task guard.

These are the pieces that decide how many areas run at once and which copy of a
re-issued task is allowed to scrape. Getting them wrong is expensive in both
directions -- a limit of 0 means nothing ever runs again, and a task that fails
to notice it has been superseded scrapes the same area twice and doubles every
row it writes.
"""

import uuid

from app.core.config import get_settings
from app.core.runtime_settings import (
    CONCURRENT_TARGETS_KEY,
    clamp_concurrent_targets,
    get_concurrent_targets,
)
from app.db.models.job import JobTarget
from app.workers.tasks import _is_superseded

settings = get_settings()


class StubSession:
    """Just enough Session for the accessor: one primary-key lookup."""

    def __init__(self, row=None):
        self.row = row

    def get(self, _model, _key):
        return self.row


class StubSetting:
    def __init__(self, value):
        self.key = CONCURRENT_TARGETS_KEY
        self.value = value


class StubTask:
    """Stand-in for a bound Celery task's request."""

    def __init__(self, task_id):
        self.request = type("Request", (), {"id": task_id})()


def _target(dispatch_id=None) -> JobTarget:
    return JobTarget(id=uuid.uuid4(), dispatch_id=dispatch_id)


# ------------------------------------------------------------------- clamping


def test_zero_and_negative_clamp_up_to_one():
    # A stored 0 would stall the dispatcher permanently: no slots, so no target
    # is ever handed out and nothing ever finishes to free one.
    assert clamp_concurrent_targets(0) == 1
    assert clamp_concurrent_targets(-5) == 1


def test_values_above_the_ceiling_clamp_down():
    assert clamp_concurrent_targets(10_000) == settings.max_concurrent_targets


def test_values_in_range_pass_through():
    assert clamp_concurrent_targets(4) == 4


# ---------------------------------------------------------------------- reads


def test_default_is_used_until_something_is_saved():
    assert get_concurrent_targets(StubSession()) == clamp_concurrent_targets(
        settings.default_concurrent_targets
    )


def test_stored_value_wins():
    assert get_concurrent_targets(StubSession(StubSetting("7"))) == 7


def test_stored_value_is_clamped_on_read_too():
    """A row can predate a lowered ceiling, or have been edited in the database."""
    assert get_concurrent_targets(StubSession(StubSetting("0"))) == 1
    assert (
        get_concurrent_targets(StubSession(StubSetting("999999")))
        == settings.max_concurrent_targets
    )


def test_unparseable_value_falls_back_to_the_default():
    assert get_concurrent_targets(StubSession(StubSetting("lots"))) == clamp_concurrent_targets(
        settings.default_concurrent_targets
    )


# ------------------------------------------------------------ superseded tasks


def test_task_whose_dispatch_id_still_matches_runs():
    task_id = str(uuid.uuid4())
    assert not _is_superseded(StubTask(task_id), _target(dispatch_id=task_id))


def test_task_replaced_by_a_later_dispatch_is_superseded():
    # The dispatcher decided this target's task was lost and re-issued it. Two
    # copies scraping the same area would write every result row twice.
    assert _is_superseded(StubTask(str(uuid.uuid4())), _target(dispatch_id=str(uuid.uuid4())))


def test_target_with_no_dispatch_id_is_never_superseded():
    """Rows queued before the dispatcher existed carry no id to compare."""
    assert not _is_superseded(StubTask(str(uuid.uuid4())), _target(dispatch_id=None))


def test_direct_call_with_no_task_id_is_never_superseded():
    """Calling the task body directly (tests, `celery call --eager`) has no id."""
    assert not _is_superseded(StubTask(None), _target(dispatch_id=str(uuid.uuid4())))
