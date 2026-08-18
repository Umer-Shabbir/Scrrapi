"""Cron cadence math (app.core.scheduling): the one place that understands
cadence strings, timezones, and what counts as a misfire. Wrong here means a
schedule either never fires, fires in the wrong timezone, or silently runs a
job hours late against stale data."""

from datetime import datetime

import pytest

from app.core.scheduling import (
    InvalidCadence,
    describe_cadence,
    next_n_runs,
    next_run_after,
    validate_cadence,
)


def test_validate_cadence_accepts_a_normal_cron_expression() -> None:
    validate_cadence("0 9 * * *", "UTC")  # daily at 9am -- must not raise


def test_validate_cadence_rejects_garbage_cadence() -> None:
    with pytest.raises(InvalidCadence):
        validate_cadence("not a cron expression", "UTC")


def test_validate_cadence_rejects_unknown_timezone() -> None:
    with pytest.raises(InvalidCadence):
        validate_cadence("0 9 * * *", "Mars/Olympus_Mons")


def test_next_run_after_daily_cadence_lands_on_the_right_hour() -> None:
    after = datetime(2026, 8, 11, 6, 0)  # 6am, before the 9am fire
    next_run = next_run_after("0 9 * * *", "UTC", after)

    assert next_run == datetime(2026, 8, 11, 9, 0)


def test_next_run_after_rolls_to_the_next_day_once_past_the_fire_time() -> None:
    after = datetime(2026, 8, 11, 10, 0)  # past today's 9am fire
    next_run = next_run_after("0 9 * * *", "UTC", after)

    assert next_run == datetime(2026, 8, 12, 9, 0)


def test_next_run_after_converts_a_local_fire_time_to_utc() -> None:
    # 9am America/Chicago in August is UTC-5 (CDT) -> 14:00 UTC.
    after = datetime(2026, 8, 11, 6, 0)
    next_run = next_run_after("0 9 * * *", "America/Chicago", after)

    assert next_run == datetime(2026, 8, 11, 14, 0)


def test_next_n_runs_returns_strictly_increasing_distinct_times() -> None:
    runs = next_n_runs("0 9 * * *", "UTC", datetime(2026, 8, 11, 6, 0), count=5)

    assert len(runs) == 5
    assert runs == sorted(set(runs))
    assert runs[0] == datetime(2026, 8, 11, 9, 0)
    assert runs[-1] == datetime(2026, 8, 15, 9, 0)


def test_describe_cadence_labels_a_plain_daily_cron() -> None:
    assert describe_cadence("0 9 * * *") == "Daily at 09:00 UTC-relative"


def test_describe_cadence_labels_a_weekly_cron() -> None:
    assert describe_cadence("30 8 * * 1,3,5") == "Weekly on Mon, Wed, Fri at 08:30 UTC-relative"


def test_describe_cadence_falls_back_to_the_raw_string_for_anything_else() -> None:
    # A day-of-month restriction isn't in the daily/weekly set the UI produces.
    assert describe_cadence("0 9 15 * *") == "0 9 15 * *"
