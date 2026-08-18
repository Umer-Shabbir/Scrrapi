"""Preferences the user edits at runtime, stored in the app DB.

Separate from `app.core.config.Settings` on purpose. That one is deployment
configuration: read from the environment once per process, identical for every
request, changed by editing `.env` and restarting. These are settings the UI
writes while the stack is running, so they have to be somewhere the API and
every worker process can both read *now* -- which means the database, not a
module-level object each process loaded at boot.

Reads are cheap (single primary-key lookup) and deliberately uncached: the
dispatcher consults `concurrent_targets` on every pass, and a cache would mean
raising the limit from the Settings page did nothing until the workers were
restarted, which is the exact thing this module exists to avoid.
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.setting import AppSetting

logger = logging.getLogger(__name__)
settings = get_settings()

# How many job targets may be in flight at once, across every job and user --
# there is one worker fleet, so the limit is global rather than per-job.
CONCURRENT_TARGETS_KEY = "concurrent_targets"

# Whether a scraped place's website gets crawled for extra contact details
# (app.scraping.common.site_crawler), and how many of its pages that crawl may
# read. Runtime rather than environment settings for the same reason as the
# concurrency limit: the workers have to pick a change up without a redeploy,
# and turning the crawler off is the first thing anyone does when a job is
# running slower than they want.
DEEP_CRAWL_ENABLED_KEY = "deep_crawl_enabled"
DEEP_CRAWL_MAX_PAGES_KEY = "deep_crawl_max_pages"

# Per-host cooldown base and the Celery retry ceiling (Settings > Scraping).
# Previously env-only constants (`rate_limit_base_cooldown_s`, a fixed
# `task_max_retries_*` per task type) -- now DB-backed so the Settings screen
# can change them without a redeploy, same reasoning as concurrency above.
# `retry_ceiling` governs all three task types uniformly rather than exposing
# three separate controls the Figma screen doesn't have room for.
COOLDOWN_BASE_S_KEY = "cooldown_base_s"
RETRY_CEILING_KEY = "retry_ceiling"

# Tech fingerprint (app.scraping.common.tech_fingerprint) ran unconditionally
# before this -- no on/off switch existed anywhere. Off by default matches
# nothing changing for installs that never touch the new toggle.
TECH_FINGERPRINT_ENABLED_KEY = "tech_fingerprint_enabled"

# "off" | "syntax_mx" -- syntax-only validation (app.scraping.common.email_miner)
# always runs during extraction and can't be turned off (it's mail-shape
# validation, not a separate enrichment step); this setting only gates the
# *additional* MX-record lookup. Figma's third option ("+ SMTP", a live
# handshake against the recipient's mail server) is deliberately not built --
# it means originating a connection to a third party's mail server per lead,
# which is a real anti-abuse/deliverability-risk surface this cycle doesn't
# have a rate-limit/blocklist story for. Not offered rather than faked.
EMAIL_VERIFICATION_MODE_KEY = "email_verification_mode"
EMAIL_VERIFICATION_MODES = ("off", "syntax_mx")

# Lead score weights (Settings > Lead Scoring). Mirrors the exact signals
# `app.scraping.common.lead_score.lead_score` already computes -- rating has
# two tiers (>=4.5 / >=4.0) matching the existing hardcoded thresholds. Figma's
# handoff lists several additional signals (review count, opening hours,
# claimed listing, contact form, permanently closed, chain/franchise) that
# have no backing column anywhere in `Result` and nothing scrapes them --
# same reasoning as the Export screen's Column Selection already omitting
# "reviews" (see app.db.models.export.COLUMN_GROUPS) -- so those rows are
# dropped from the weight table rather than shown as fake configurable knobs.
SCORE_WEIGHT_KEYS = {
    "email": "score_weight_email",
    "website": "score_weight_website",
    "phone": "score_weight_phone",
    "social": "score_weight_social",
    "rating_high": "score_weight_rating_high",
    "rating_good": "score_weight_rating_good",
}
SCORE_WEIGHT_DEFAULTS = {
    "email": 20,
    "website": 15,
    "phone": 20,
    # Per-profile increment, capped at 2 profiles' worth -- see
    # app.scraping.common.lead_score.DEFAULT_WEIGHTS' comment.
    "social": 5,
    "rating_high": 15,
    "rating_good": 8,
}

# Data retention (Settings > Data Retention). Export retention already existed
# as `settings.export_retention_days` (env-only, applied in
# app.workers.tasks.purge_expired_exports); results retention is new -- no
# age-based cleanup of the `results` table existed before this.
RESULTS_RETENTION_DAYS_KEY = "results_retention_days"
EXPORT_RETENTION_DAYS_KEY = "export_retention_days"

_TRUE_VALUES = {"1", "true", "yes", "on"}


def clamp_concurrent_targets(value: int) -> int:
    """Force `value` into the accepted range.

    Applied on write *and* on read: a row can predate a lowered
    `max_concurrent_targets`, or have been edited straight in the database, and
    neither should be able to hand the dispatcher a limit of 0 (nothing would
    ever be scraped again) or 5000.
    """
    return max(1, min(int(value), settings.max_concurrent_targets))


def clamp_deep_crawl_max_pages(value: int) -> int:
    """Same contract as `clamp_concurrent_targets`, for the crawl page budget.

    The floor is 1 rather than 0: "crawl zero pages" is what the enabled flag is
    for, and a 0 here would spend the whole enrichment path setting up a crawl
    that can never read anything.
    """
    return max(1, min(int(value), settings.max_deep_crawl_pages))


def get_concurrent_targets(db: Session) -> int:
    """The live limit, or the configured default when nothing is stored yet."""
    return _read_int(
        db,
        CONCURRENT_TARGETS_KEY,
        default=settings.default_concurrent_targets,
        clamp=clamp_concurrent_targets,
    )


def set_concurrent_targets(db: Session, value: int) -> int:
    """Store a new limit and return what was actually stored after clamping."""
    clamped = clamp_concurrent_targets(value)
    _write(db, CONCURRENT_TARGETS_KEY, str(clamped))
    logger.info("concurrency setting updated", extra={"concurrent_targets": clamped})
    return clamped


def get_deep_crawl_enabled(db: Session) -> bool:
    """Whether the deep site crawler runs during place enrichment."""
    row = db.get(AppSetting, DEEP_CRAWL_ENABLED_KEY)
    if row is None:
        return settings.deep_crawl_enabled
    return row.value.strip().lower() in _TRUE_VALUES


def set_deep_crawl_enabled(db: Session, value: bool) -> bool:
    _write(db, DEEP_CRAWL_ENABLED_KEY, "true" if value else "false")
    logger.info("deep crawl setting updated", extra={"deep_crawl_enabled": bool(value)})
    return bool(value)


def get_deep_crawl_max_pages(db: Session) -> int:
    """How many pages of one website a crawl may read."""
    return _read_int(
        db,
        DEEP_CRAWL_MAX_PAGES_KEY,
        default=settings.deep_crawl_max_pages,
        clamp=clamp_deep_crawl_max_pages,
    )


def set_deep_crawl_max_pages(db: Session, value: int) -> int:
    clamped = clamp_deep_crawl_max_pages(value)
    _write(db, DEEP_CRAWL_MAX_PAGES_KEY, str(clamped))
    logger.info("deep crawl page budget updated", extra={"deep_crawl_max_pages": clamped})
    return clamped


def clamp_cooldown_base_s(value: float) -> float:
    return max(1.0, min(float(value), settings.max_cooldown_base_s))


def get_cooldown_base_s(db: Session) -> float:
    """Base per-host cooldown seconds (app.scraping.common.rate_limit)."""
    return _read_float(
        db, COOLDOWN_BASE_S_KEY,
        default=settings.rate_limit_base_cooldown_s, clamp=clamp_cooldown_base_s,
    )


def set_cooldown_base_s(db: Session, value: float) -> float:
    clamped = clamp_cooldown_base_s(value)
    _write(db, COOLDOWN_BASE_S_KEY, str(clamped))
    logger.info("cooldown base updated", extra={"cooldown_base_s": clamped})
    return clamped


def clamp_retry_ceiling(value: int) -> int:
    return max(0, min(int(value), settings.max_retry_ceiling))


def get_retry_ceiling(db: Session) -> int:
    """Max retry attempts, applied uniformly to feed/place/export tasks."""
    return _read_int(
        db, RETRY_CEILING_KEY,
        default=settings.task_max_retries_feed, clamp=clamp_retry_ceiling,
    )


def set_retry_ceiling(db: Session, value: int) -> int:
    clamped = clamp_retry_ceiling(value)
    _write(db, RETRY_CEILING_KEY, str(clamped))
    logger.info("retry ceiling updated", extra={"retry_ceiling": clamped})
    return clamped


def get_tech_fingerprint_enabled(db: Session) -> bool:
    row = db.get(AppSetting, TECH_FINGERPRINT_ENABLED_KEY)
    if row is None:
        return False
    return row.value.strip().lower() in _TRUE_VALUES


def set_tech_fingerprint_enabled(db: Session, value: bool) -> bool:
    _write(db, TECH_FINGERPRINT_ENABLED_KEY, "true" if value else "false")
    logger.info("tech fingerprint setting updated", extra={"tech_fingerprint_enabled": bool(value)})
    return bool(value)


def get_email_verification_mode(db: Session) -> str:
    row = db.get(AppSetting, EMAIL_VERIFICATION_MODE_KEY)
    if row is None or row.value not in EMAIL_VERIFICATION_MODES:
        return "off"
    return row.value


def set_email_verification_mode(db: Session, value: str) -> str:
    if value not in EMAIL_VERIFICATION_MODES:
        raise ValueError(f"unknown email verification mode: {value!r}")
    _write(db, EMAIL_VERIFICATION_MODE_KEY, value)
    logger.info("email verification mode updated", extra={"email_verification_mode": value})
    return value


def get_score_weights(db: Session) -> dict[str, int]:
    return {
        signal: _read_int(
            db, key, default=SCORE_WEIGHT_DEFAULTS[signal], clamp=lambda v: max(-100, min(100, v))
        )
        for signal, key in SCORE_WEIGHT_KEYS.items()
    }


def set_score_weight(db: Session, signal: str, value: int) -> int:
    if signal not in SCORE_WEIGHT_KEYS:
        raise ValueError(f"unknown score signal: {signal!r}")
    clamped = max(-100, min(100, int(value)))
    _write(db, SCORE_WEIGHT_KEYS[signal], str(clamped))
    logger.info("score weight updated", extra={"signal": signal, "value": clamped})
    return clamped


def clamp_results_retention_days(value: int) -> int:
    return max(1, min(int(value), settings.max_results_retention_days))


def get_results_retention_days(db: Session) -> int:
    return _read_int(
        db, RESULTS_RETENTION_DAYS_KEY,
        default=settings.results_retention_days, clamp=clamp_results_retention_days,
    )


def set_results_retention_days(db: Session, value: int) -> int:
    clamped = clamp_results_retention_days(value)
    _write(db, RESULTS_RETENTION_DAYS_KEY, str(clamped))
    logger.info("results retention updated", extra={"results_retention_days": clamped})
    return clamped


def clamp_export_retention_days(value: int) -> int:
    return max(1, min(int(value), settings.max_export_retention_days))


def get_export_retention_days(db: Session) -> int:
    return _read_int(
        db, EXPORT_RETENTION_DAYS_KEY,
        default=settings.export_retention_days, clamp=clamp_export_retention_days,
    )


def set_export_retention_days(db: Session, value: int) -> int:
    clamped = clamp_export_retention_days(value)
    _write(db, EXPORT_RETENTION_DAYS_KEY, str(clamped))
    logger.info("export retention updated", extra={"export_retention_days": clamped})
    return clamped


def reset_to_defaults(db: Session) -> None:
    """Delete every stored runtime setting row -- Settings > Danger Zone >
    Reset Settings. Next read of any key falls back to its configured default,
    same code path as a fresh install. Does not touch stored results/exports.
    """
    db.query(AppSetting).delete()
    db.commit()
    logger.info("runtime settings reset to defaults")


def _read_float(db: Session, key: str, *, default: float, clamp) -> float:
    row = db.get(AppSetting, key)
    if row is None:
        return clamp(default)
    try:
        return clamp(float(row.value))
    except (TypeError, ValueError):
        logger.warning(
            "unreadable runtime setting, using the default",
            extra={"setting": key, "stored": row.value},
        )
        return clamp(default)


def _read_int(db: Session, key: str, *, default: int, clamp) -> int:
    row = db.get(AppSetting, key)
    if row is None:
        return clamp(default)

    try:
        return clamp(int(row.value))
    except (TypeError, ValueError):
        logger.warning(
            "unreadable runtime setting, using the default",
            extra={"setting": key, "stored": row.value},
        )
        return clamp(default)


def _write(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value
        row.updated_at = datetime.utcnow()
    db.commit()
