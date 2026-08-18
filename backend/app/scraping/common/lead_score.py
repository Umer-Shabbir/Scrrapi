"""Lead Detail's score dial + reason breakdown, shared with the Export
screen's SCORING column group -- one function, so a row's exported score
column can never disagree with what its own Lead Detail drawer shows.

Transparent, recomputed-on-read from columns already on the row -- never
persisted, never fabricated. A lead with no phone, no email, no website, no
rating and no tech signature scores 0, not some non-zero "everyone gets
something" floor.

Weights default to the values below but are overridable via `weights`
(Settings > Lead Scoring, app.core.runtime_settings.get_score_weights) --
callers with a DB session (app.api.routers.jobs) pass the live values;
callers without one (the export writers, run from a Celery task with no
request-scoped session handy) fall back to these same defaults, so a CSV/XLSX
export's score always matches what Lead Detail showed *unless* an operator
has changed the weights since -- documented, not silently inconsistent.
"""

from app.db.models.result import Result

SOCIAL_FIELDS = ("facebook", "instagram", "linkedin", "twitter", "youtube", "tiktok", "whatsapp")

DEFAULT_WEIGHTS = {
    "email": 20,
    "website": 15,
    "phone": 20,
    # Per-profile increment, capped at 2 profiles' worth (2 * social) -- matches
    # the original hardcoded "min(10, social_count * 5)" exactly.
    "social": 5,
    "rating_high": 15,
    "rating_good": 8,
}


def lead_score(result: Result, weights: dict[str, int] | None = None) -> dict:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    reasons: list[str] = []
    total = 0

    if result.phone and w["phone"]:
        total += w["phone"]
        reasons.append(f"verified phone ({w['phone']:+d})")
    if result.email and w["email"]:
        total += w["email"]
        reasons.append(f"verified email ({w['email']:+d})")
    if result.website and w["website"]:
        total += w["website"]
        reasons.append(f"active website ({w['website']:+d})")
    if result.rating is not None:
        if result.rating >= 4.5 and w["rating_high"]:
            total += w["rating_high"]
            reasons.append(f"high rating: {result.rating:g} ({w['rating_high']:+d})")
        elif result.rating >= 4.0 and w["rating_good"]:
            total += w["rating_good"]
            reasons.append(f"good rating: {result.rating:g} ({w['rating_good']:+d})")
    if result.tech_stack:
        total += 5
        reasons.append("active tech stack (+5)")
    social_count = sum(1 for field in SOCIAL_FIELDS if getattr(result, field))
    if social_count and w["social"]:
        social_points = min(abs(w["social"]) * 2, social_count * w["social"])
        total += social_points
        plural = "s" if social_count != 1 else ""
        reasons.append(f"{social_count} social profile{plural} ({social_points:+d})")

    return {"value": max(0, min(100, total)), "reasons": reasons}
