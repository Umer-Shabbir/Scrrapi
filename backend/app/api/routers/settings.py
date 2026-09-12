"""Runtime settings endpoints.

GET   /api/settings              -> current values + the live queue counts they govern
PATCH /api/settings              -> change one or more of them
POST  /api/settings/reset        -> Danger Zone: restore every setting to its default
POST  /api/settings/purge-results -> Danger Zone: delete every stored result + export artifact

All installation-wide rather than per-user -- there is one worker fleet, so a
per-user limit would not bound anything:

- `concurrentTargets`: how many areas (keyword x location targets) may be
  scraped at the same time.
- `deepCrawl*`: whether a result's website is crawled for extra contact
  details, and how many of its pages.
- `cooldownBaseS`/`retryCeiling`: per-host adaptive cooldown base and the
  Celery retry ceiling (see app.scraping.common.rate_limit,
  app.workers.tasks.retries_left). Cooldown base takes effect for scrapes
  started by a worker process that (re)starts after the change -- see
  app.scraping.common.rate_limit.get_tracker's docstring for why it can't be
  live mid-run without threading a DB session through the scraper call chain.
- `techFingerprintEnabled`: whether a result's website gets an extra fetch to
  detect its platform/tooling (app.scraping.common.tech_fingerprint).
- `emailVerificationMode`: "off" or "syntax_mx". Syntax validation always runs
  during extraction; "syntax_mx" is a real DNS MX lookup
  (app.scraping.common.email_verify) but is not yet wired into the scrape
  pipeline -- see that module's docstring for why (network cost per lead,
  out of scope for a Settings-screen cycle). The setting is stored correctly;
  it does not yet change a running job's behavior. Figma's third option
  ("+ SMTP", a live handshake) is not offered at all -- it means originating
  a connection to a third party's mail server per lead with no rate-limit/
  blocklist story, a real abuse-surface this cycle doesn't have an answer for.
- `scoreWeights`: the six signals app.scraping.common.lead_score already
  computes (email/website/phone/social/rating tiers). Figma's handoff lists
  several more (review count, opening hours, claimed listing, contact form,
  permanently closed, chain/franchise match) that have no backing column on
  `Result` and nothing scrapes -- same reasoning as the Export screen's
  Column Selection already omitting "reviews" (app.db.models.export.
  COLUMN_GROUPS docstring). Not offered as configurable weights for signals
  that don't exist.
- `resultsRetentionDays`/`exportRetentionDays`: age-based purge windows
  (app.workers.tasks.purge_expired_results/purge_expired_exports), both on a
  daily Celery Beat tick.

PATCH is a partial update: a field that isn't sent keeps its stored value, so
the Settings page can save one control without echoing the rest back.
"""

import logging
import os
from contextlib import suppress

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_app_db, get_current_user
from app.core.audit import client_ip, log_audit_event
from app.core.config import get_settings
from app.core.runtime_settings import (
    ALL_WATERFALL_PROVIDERS,
    EMAIL_VERIFICATION_MODES,
    SCORE_WEIGHT_KEYS,
    get_concurrent_targets,
    get_cooldown_base_s,
    get_deep_crawl_enabled,
    get_deep_crawl_max_pages,
    get_email_verification_mode,
    get_export_retention_days,
    get_provider_api_key,
    get_results_retention_days,
    get_retry_ceiling,
    get_score_weights,
    get_tech_fingerprint_enabled,
    get_waterfall_enrichment_enabled,
    get_waterfall_providers,
    reset_to_defaults,
    set_concurrent_targets,
    set_cooldown_base_s,
    set_deep_crawl_enabled,
    set_deep_crawl_max_pages,
    set_email_verification_mode,
    set_export_retention_days,
    set_provider_api_key,
    set_results_retention_days,
    set_retry_ceiling,
    set_score_weight,
    set_tech_fingerprint_enabled,
    set_waterfall_enrichment_enabled,
    set_waterfall_providers,
)
from app.db.models.export import Export
from app.db.models.result import Result, ResultHistory
from app.db.models.user import User
from app.workers.dispatch import count_in_flight, count_waiting, dispatch_ready_targets

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

_AUDITED_SETTINGS_KEYS = (
    "concurrentTargets",
    "deepCrawlEnabled",
    "deepCrawlMaxPages",
    "cooldownBaseS",
    "retryCeiling",
    "techFingerprintEnabled",
    "emailVerificationMode",
    "scoreWeights",
    "resultsRetentionDays",
    "exportRetentionDays",
    "waterfallEnrichmentEnabled",
    "waterfallProviders",
)


def _require_owner(user: User = Depends(get_current_user)) -> User:
    """Danger Zone actions are owner-only, same gate as audit/api-keys/team --
    purging every result or resetting every setting is workspace-wide, not a
    per-user action."""
    if user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the workspace owner can do this",
        )
    return user


class UpdateSettingsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Bounded here as well as in the `clamp_*` helpers so a bad value comes back
    # as a 422 naming the field instead of being silently rounded into range.
    # Optional so each control on the Settings page can save on its own.
    concurrent_targets: int | None = Field(default=None, alias="concurrentTargets", ge=1)
    deep_crawl_enabled: bool | None = Field(default=None, alias="deepCrawlEnabled")
    deep_crawl_max_pages: int | None = Field(default=None, alias="deepCrawlMaxPages", ge=1)
    cooldown_base_s: float | None = Field(default=None, alias="cooldownBaseS", ge=1)
    retry_ceiling: int | None = Field(default=None, alias="retryCeiling", ge=0)
    tech_fingerprint_enabled: bool | None = Field(default=None, alias="techFingerprintEnabled")
    email_verification_mode: str | None = Field(default=None, alias="emailVerificationMode")
    score_weights: dict[str, int] | None = Field(default=None, alias="scoreWeights")
    results_retention_days: int | None = Field(default=None, alias="resultsRetentionDays", ge=1)
    export_retention_days: int | None = Field(default=None, alias="exportRetentionDays", ge=1)
    waterfall_enrichment_enabled: bool | None = Field(
        default=None, alias="waterfallEnrichmentEnabled"
    )
    waterfall_providers: list[str] | None = Field(default=None, alias="waterfallProviders")
    hunter_api_key: str | None = Field(default=None, alias="hunterApiKey")
    prospeo_api_key: str | None = Field(default=None, alias="prospeoApiKey")
    datagma_api_key: str | None = Field(default=None, alias="datagmaApiKey")
    findymail_api_key: str | None = Field(default=None, alias="findymailApiKey")


@router.get("/")
def read_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    return _settings_dict(db)


@router.patch("/")
def update_settings(
    request: Request,
    payload: UpdateSettingsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    before = _settings_dict(db)
    changed: dict = {}

    if payload.deep_crawl_enabled is not None:
        changed["deep_crawl_enabled"] = set_deep_crawl_enabled(db, payload.deep_crawl_enabled)
    if payload.deep_crawl_max_pages is not None:
        changed["deep_crawl_max_pages"] = set_deep_crawl_max_pages(db, payload.deep_crawl_max_pages)
    if payload.cooldown_base_s is not None:
        changed["cooldown_base_s"] = set_cooldown_base_s(db, payload.cooldown_base_s)
    if payload.retry_ceiling is not None:
        changed["retry_ceiling"] = set_retry_ceiling(db, payload.retry_ceiling)
    if payload.tech_fingerprint_enabled is not None:
        changed["tech_fingerprint_enabled"] = set_tech_fingerprint_enabled(
            db, payload.tech_fingerprint_enabled
        )
    if payload.email_verification_mode is not None:
        if payload.email_verification_mode not in EMAIL_VERIFICATION_MODES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"emailVerificationMode must be one of {EMAIL_VERIFICATION_MODES}",
            )
        changed["email_verification_mode"] = set_email_verification_mode(
            db, payload.email_verification_mode
        )
    if payload.score_weights is not None:
        unknown = set(payload.score_weights) - set(SCORE_WEIGHT_KEYS)
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"unknown score signal(s): {sorted(unknown)}",
            )
        for signal, value in payload.score_weights.items():
            set_score_weight(db, signal, value)
        changed["score_weights"] = payload.score_weights
    if payload.results_retention_days is not None:
        changed["results_retention_days"] = set_results_retention_days(
            db, payload.results_retention_days
        )
    if payload.export_retention_days is not None:
        changed["export_retention_days"] = set_export_retention_days(
            db, payload.export_retention_days
        )
    if payload.waterfall_enrichment_enabled is not None:
        changed["waterfall_enrichment_enabled"] = set_waterfall_enrichment_enabled(
            db, payload.waterfall_enrichment_enabled
        )
    if payload.waterfall_providers is not None:
        changed["waterfall_providers"] = set_waterfall_providers(db, payload.waterfall_providers)
    if payload.hunter_api_key is not None:
        changed["hunter_api_key"] = set_provider_api_key(db, "hunter", payload.hunter_api_key)
    if payload.prospeo_api_key is not None:
        changed["prospeo_api_key"] = set_provider_api_key(db, "prospeo", payload.prospeo_api_key)
    if payload.datagma_api_key is not None:
        changed["datagma_api_key"] = set_provider_api_key(db, "datagma", payload.datagma_api_key)
    if payload.findymail_api_key is not None:
        changed["findymail_api_key"] = set_provider_api_key(
            db, "findymail", payload.findymail_api_key
        )

    if payload.concurrent_targets is not None:
        changed["concurrent_targets"] = set_concurrent_targets(db, payload.concurrent_targets)
        # Only the concurrency limit frees slots, so this is the only change that
        # can put work on the broker right now.
        changed["dispatched"] = dispatch_ready_targets(db)

    logger.info("settings updated", extra=changed)

    if changed:
        after = _settings_dict(db)
        log_audit_event(
            db,
            actor_email=user.email,
            action="settings.updated",
            ip_address=client_ip(request),
            before_after={
                "before": {k: before[k] for k in _AUDITED_SETTINGS_KEYS},
                "after": {k: after[k] for k in _AUDITED_SETTINGS_KEYS},
            },
        )
        db.commit()

    return _settings_dict(db)


@router.post("/reset")
def reset_settings(
    request: Request,
    user: User = Depends(_require_owner),
    db: Session = Depends(get_app_db),
) -> dict:
    """Danger Zone > Reset Settings. Restores every setting on this page to
    its factory default. Does not affect stored results/exports."""
    before = _settings_dict(db)
    reset_to_defaults(db)
    after = _settings_dict(db)
    log_audit_event(
        db,
        actor_email=user.email,
        action="settings.reset",
        ip_address=client_ip(request),
        before_after={
            "before": {k: before[k] for k in _AUDITED_SETTINGS_KEYS},
            "after": {k: after[k] for k in _AUDITED_SETTINGS_KEYS},
        },
    )
    db.commit()
    return after


@router.post("/purge-results")
def purge_results(
    request: Request,
    user: User = Depends(_require_owner),
    db: Session = Depends(get_app_db),
) -> dict:
    """Danger Zone > Purge All Results. Permanently deletes every stored
    result and export artifact across every job. Job history and settings are
    kept -- only `results` rows and export files/rows are removed, `jobs` and
    `job_targets` stay so the Jobs screen still shows what ran.

    Client-side typed-confirm ("Type PURGE") is the friction gate per Figma;
    this endpoint itself has no additional confirmation step because it's
    already owner-gated and audited, same trust boundary as every other
    Danger Zone action in this app.
    """
    result_count = db.scalar(select(func.count()).select_from(Result)) or 0
    export_rows = db.execute(select(Export)).scalars().all()

    for export in export_rows:
        if export.file_path and os.path.exists(export.file_path):
            with suppress(OSError):
                os.remove(export.file_path)

    export_count = len(export_rows)
    db.execute(delete(Export))
    # result_history FKs onto results.id -- must go first, same
    # ForeignKeyViolation risk as every other results delete site.
    db.execute(delete(ResultHistory))
    db.execute(delete(Result))

    log_audit_event(
        db,
        actor_email=user.email,
        action="settings.purge_results",
        ip_address=client_ip(request),
        before_after={"deleted": {"results": result_count, "exports": export_count}},
    )
    db.commit()
    logger.info(
        "purged all results and exports",
        extra={"results": result_count, "exports": export_count, "actor": user.email},
    )
    return {"resultsDeleted": result_count, "exportsDeleted": export_count}


def _settings_dict(db: Session) -> dict:
    """Current values plus what they are doing right now.

    The two queue counts are what makes the concurrency setting legible: "4
    running, 196 waiting" explains a queue that looks stalled far better than
    the number 4 on its own. The ceilings are what the UI builds its
    slider/range inputs from, so it never offers a value the API would reject.
    """
    return {
        "concurrentTargets": get_concurrent_targets(db),
        "maxConcurrentTargets": settings.max_concurrent_targets,
        "runningTargets": count_in_flight(db),
        "waitingTargets": count_waiting(db),
        "deepCrawlEnabled": get_deep_crawl_enabled(db),
        "deepCrawlMaxPages": get_deep_crawl_max_pages(db),
        "maxDeepCrawlPages": settings.max_deep_crawl_pages,
        "cooldownBaseS": get_cooldown_base_s(db),
        "maxCooldownBaseS": settings.max_cooldown_base_s,
        "retryCeiling": get_retry_ceiling(db),
        "maxRetryCeiling": settings.max_retry_ceiling,
        "techFingerprintEnabled": get_tech_fingerprint_enabled(db),
        "emailVerificationMode": get_email_verification_mode(db),
        "emailVerificationModes": list(EMAIL_VERIFICATION_MODES),
        "scoreWeights": get_score_weights(db),
        "resultsRetentionDays": get_results_retention_days(db),
        "maxResultsRetentionDays": settings.max_results_retention_days,
        "exportRetentionDays": get_export_retention_days(db),
        "maxExportRetentionDays": settings.max_export_retention_days,
        "waterfallEnrichmentEnabled": get_waterfall_enrichment_enabled(db),
        "waterfallProviders": get_waterfall_providers(db),
        "allWaterfallProviders": list(ALL_WATERFALL_PROVIDERS),
        "hunterApiKey": get_provider_api_key(db, "hunter"),
        "prospeoApiKey": get_provider_api_key(db, "prospeo"),
        "datagmaApiKey": get_provider_api_key(db, "datagma"),
        "findymailApiKey": get_provider_api_key(db, "findymail"),
    }
