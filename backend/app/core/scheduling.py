"""Cron cadence helpers shared by the schedules router and the dispatcher task.

A `Schedule.cadence` is always a standard 5-field cron expression, evaluated in
`Schedule.timezone`. The UI's daily/weekly/custom picker compiles down to one
of these before it reaches the API -- this module never sees "daily at 9am",
only "0 9 * * *" -- so there is exactly one code path that understands cron
syntax, and it doesn't care which UI control produced the string.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import CroniterBadCronError, croniter

_EPSILON = timedelta(seconds=1)

# A schedule whose next_run_at is older than this when the dispatcher gets to
# it is treated as misfired (skipped, not run late) rather than fired --
# running a job hours after it was due against stale "current" data would be
# worse than just admitting it was missed. Matches the dispatcher's own poll
# cadence with headroom for one missed tick.
MISFIRE_GRACE_MINUTES = 5


class InvalidCadence(ValueError):
    pass


def validate_cadence(cadence: str, tz_name: str) -> None:
    """Raises InvalidCadence if `cadence` isn't a valid 5-field cron expression
    or `tz_name` isn't a real IANA zone. Called on create/update so a typo is
    caught at save time, not the first time the dispatcher tries to use it."""
    try:
        croniter(cadence)
    except (CroniterBadCronError, ValueError) as exc:
        raise InvalidCadence(f"invalid cadence: {exc}") from exc
    try:
        ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise InvalidCadence(f"unknown timezone: {tz_name!r}") from exc


def next_run_after(cadence: str, tz_name: str, after: datetime) -> datetime:
    """The next UTC instant `cadence` fires at or after `after`.

    `after` is naive and always UTC (every caller passes `datetime.utcnow()`,
    matching every other timestamp in this codebase) -- it has to be tagged
    explicitly before converting zones, since `.astimezone()` on a naive
    datetime assumes local *system* time, not UTC, which would silently shift
    every fire time by the server's own UTC offset.

    Cron fields are evaluated in `tz_name` (so "0 9 * * *" means 9am local,
    not 9am UTC), then converted back to UTC -- the only timezone `next_run_at`
    is ever stored in, so the dispatcher's `next_run_at <= now` comparison
    never has to know what zone a given schedule is in.
    """
    aware_after = after.replace(tzinfo=ZoneInfo("UTC"))
    local_after = aware_after.astimezone(ZoneInfo(tz_name))
    it = croniter(cadence, local_after)
    next_local = it.get_next(datetime)
    return next_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def next_n_runs(cadence: str, tz_name: str, after: datetime, count: int = 5) -> list[datetime]:
    """The next `count` UTC fire times at or after `after` -- what the
    schedule-builder's live preview shows before the row is even saved."""
    out: list[datetime] = []
    cursor = after
    for _ in range(count):
        cursor = next_run_after(cadence, tz_name, cursor)
        out.append(cursor)
        cursor = cursor + _EPSILON
    return out


def describe_cadence(cadence: str) -> str:
    """Best-effort plain-English summary for the schedule-builder preview.
    Falls back to echoing the cron string for anything not in the common set
    the UI's picker actually produces -- this is a convenience label, not a
    full cron-to-English engine."""
    parts = cadence.split()
    if len(parts) != 5:
        return cadence
    minute, hour, dom, month, dow = parts

    def time_of_day() -> str:
        try:
            return f"{int(hour):02d}:{int(minute):02d} UTC-relative"
        except ValueError:
            return f"at {minute} {hour} (cron minute/hour fields)"

    if dom == "*" and month == "*" and dow == "*":
        return f"Daily at {time_of_day()}"
    if dom == "*" and month == "*" and dow != "*":
        days = {"0": "Sun", "1": "Mon", "2": "Tue", "3": "Wed", "4": "Thu", "5": "Fri", "6": "Sat"}
        named = ", ".join(days.get(d, d) for d in dow.split(","))
        return f"Weekly on {named} at {time_of_day()}"
    return cadence
