"""Plan -> monthly quota ceiling catalog (Account & Billing screen's QUOTA
section, SCREENLIST.md §21).

`License.plan` (app/db/models/license.py) is a free-text string set by whoever
runs `scripts/create_user.py --plan <name>` -- there is no enum/lookup table
anywhere today, so a plan name alone carries no numeric ceiling. This module
is that catalog: the minimum real (checked-in, not per-request fabricated)
decision needed to show "48,210 / 75,000" instead of either inventing a
number on the fly or showing no ceiling at all.

Unknown plan names (anything not in PLAN_QUOTAS, including "dev" -- the
default `create_user.py` assigns) fall back to DEFAULT_QUOTA rather than
raising or lying about capacity being unlimited.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanQuota:
    places_per_month: int
    exports_per_month: int


PLAN_QUOTAS: dict[str, PlanQuota] = {
    "starter": PlanQuota(places_per_month=15_000, exports_per_month=15),
    "growth": PlanQuota(places_per_month=75_000, exports_per_month=50),
    "scale": PlanQuota(places_per_month=250_000, exports_per_month=200),
}

# Applied to "dev" (scripts/create_user.py's default) and any other plan
# string with no catalog entry -- generous enough that a dev/test install
# never appears to be over quota, but still a real, bounded number rather
# than treating unknown plans as unlimited.
DEFAULT_QUOTA = PlanQuota(places_per_month=100_000, exports_per_month=100)


def quota_for_plan(plan: str | None) -> PlanQuota:
    if plan is None:
        return DEFAULT_QUOTA
    return PLAN_QUOTAS.get(plan.strip().lower(), DEFAULT_QUOTA)
