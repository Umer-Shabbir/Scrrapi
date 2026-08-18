"""Celery tasks: run a scrape job (per keyword/location target), scrape a single place,
and build exports. Retries on browser crash instead of the legacy process-level watchdog
(AutoRestartManager + GLeadsLauncher.exe).

Retry policy (11.1): every failure is retried with exponential backoff plus jitter --
`base * 2**retries`, capped at `task_retry_backoff_max_s`, multiplied by a random
factor around 1. Two failure classes get special treatment:

- `RateLimited` (11.3): the host told us (or showed us) how long to stay away, so the
  countdown is at least that long rather than the generic backoff.
- `SoftTimeLimitExceeded`: a wedged browser, retried like any other transient fault --
  Celery's hard time limit then kills the child if the soft limit didn't unstick it.

Every log line in here carries job/target/place context (11.2), so a single job's
progress can be followed with one filter across API and worker output.
"""

import asyncio
import logging
import os
import random
import uuid
from contextlib import suppress
from datetime import datetime, timedelta
from hashlib import sha256

from sqlalchemy import delete, func, select, update

# app.api.routers.jobs doesn't import anything from app.workers, so there's no
# cycle importing it here at module level.
from app.api.routers.jobs import LocationSpec, create_job_from_spec
from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.events import publish_job_event
from app.core.logging import log_context
from app.core.runtime_settings import (
    get_deep_crawl_enabled,
    get_deep_crawl_max_pages,
    get_export_retention_days,
    get_results_retention_days,
    get_retry_ceiling,
    get_tech_fingerprint_enabled,
)
from app.core.scheduling import MISFIRE_GRACE_MINUTES, next_run_after
from app.db.models.export import Export
from app.db.models.job import HALTED_STATUSES, TERMINAL_STATUSES, Job, JobTarget, settled_status
from app.db.models.result import (
    HISTORY_FIELDS,
    OTHER_SOCIALS_CHARS,
    SOCIAL_COLUMN_CHARS,
    SOCIAL_COLUMNS,
    Result,
    ResultHistory,
)
from app.db.models.schedule import Schedule
from app.db.models.suppression import SuppressionEntry
from app.db.models.template import JobTemplate
from app.db.models.user import User
from app.db.session import AppSessionLocal
from app.export.csv_writer import write_csv
from app.export.jsonl_writer import write_jsonl
from app.export.kml_writer import write_kml
from app.export.sheets_writer import write_sheets
from app.export.xlsx_writer import write_xlsx
from app.scraping.bing_maps.feed import get_place_urls as get_bing_place_urls
from app.scraping.bing_maps.place import get_place_data as get_bing_place_data
from app.scraping.bing_maps.query import build_search_url as build_bing_search_url
from app.scraping.common.place_enrichment import enrich_place_data
from app.scraping.common.rate_limit import RateLimited
from app.scraping.common.site_crawler import SiteContacts, budget_from_settings
from app.scraping.common.social_miner import OTHER_KEY as OTHER_SOCIAL_KEY
from app.scraping.common.suppression import result_is_suppressed
from app.scraping.common.tech_fingerprint import fetch_tech_stack
from app.scraping.google_maps.feed import get_place_urls
from app.scraping.google_maps.place import get_place_data
from app.scraping.google_maps.query import build_search_url
from app.workers.dispatch import dispatch_ready_targets

logger = logging.getLogger(__name__)
settings = get_settings()

# "sheets" returns a URL, not a local path -- export_job branches on that
# (see its own comment) rather than needing a second dict here.
_EXPORT_WRITERS = {
    "csv": write_csv,
    "xlsx": write_xlsx,
    "kml": write_kml,
    "jsonl": write_jsonl,
    "sheets": write_sheets,
}


def retry_countdown(retries: int, exc: BaseException | None = None) -> float:
    """Seconds to wait before attempt `retries + 1`.

    Exponential in the attempt number, capped, then jittered so a batch of tasks
    that all tripped the same block don't come back in lockstep. A `RateLimited`
    exception carries the host's own cooldown, which floors the result -- retrying
    inside a known cooldown just burns an attempt.
    """
    backoff = min(
        settings.task_retry_backoff_base_s * (2**retries),
        settings.task_retry_backoff_max_s,
    )
    if isinstance(exc, RateLimited) and exc.retry_after:
        backoff = max(backoff, exc.retry_after)

    jitter = settings.task_retry_jitter
    return round(backoff * random.uniform(1 - jitter, 1 + jitter), 2)


def retries_left(task, ceiling: int | None = None) -> bool:
    """Whether `task` may be retried again.

    `ceiling` overrides the decorator-bound `task.max_retries` when given --
    Settings > Scraping's retry ceiling (app.core.runtime_settings) is a live
    DB value, while `max_retries=` on `@celery_app.task` is fixed at process
    start, so callers with a `db` session in scope pass the live value through
    here instead of only ever honoring whatever the process booted with.

    Checked up front instead of catching `MaxRetriesExceededError`: Celery only
    raises that when `retry()` is called *without* an `exc`. Called with one --
    which is what we do, to keep the original traceback -- it re-raises that
    exception instead, so an `except MaxRetriesExceededError` cleanup block never
    runs and the row is left stuck at "running" forever.
    """
    limit = ceiling if ceiling is not None else task.max_retries
    return limit is None or task.request.retries < limit


def _retry(task, exc: BaseException, *, job_id: str | None = None, **event_fields):
    """Schedule the next attempt with a backed-off countdown, logging why."""
    countdown = retry_countdown(task.request.retries, exc)
    logger.warning(
        "task failed, retrying",
        extra={
            "task": task.name,
            "attempt": task.request.retries + 1,
            "max_retries": task.max_retries,
            "countdown_s": countdown,
            "error": type(exc).__name__,
            "rate_limited": isinstance(exc, RateLimited),
        },
        exc_info=exc,
    )
    if job_id:
        publish_job_event(
            job_id,
            "retry",
            attempt=task.request.retries + 1,
            maxRetries=task.max_retries,
            countdownS=countdown,
            error=f"{type(exc).__name__}: {exc}"[:300],
            rateLimited=isinstance(exc, RateLimited),
            **event_fields,
        )
    return task.retry(exc=exc, countdown=countdown)


def _run_maps_scrape_task(self, job_target_id: str, *, build_search_url, get_place_urls) -> None:
    """Shared body for `scrape_google_maps`/`scrape_bing_maps`: build the search URL
    with whichever source's query builder, scroll its results feed, enqueue a
    `scrape_place` task per place URL found.

    Marks the target "running" on pickup and records how many places the feed
    produced. The target stays "running" until those places have been scraped
    (`scrape_place` counts them off) -- only a feed that produced nothing is
    terminal here. "error" once retries are exhausted.
    """
    db = AppSessionLocal()
    try:
        target = db.get(JobTarget, uuid.UUID(job_target_id))
        if target is None:
            logger.warning("job target missing, dropping task", extra={"target_id": job_target_id})
            return

        if _is_superseded(self, target):
            logger.info(
                "superseded scrape task, dropping",
                extra={"target_id": job_target_id, "dispatch_id": target.dispatch_id},
            )
            return

        job = db.get(Job, target.job_id)
        source = job.source if job else "google"
        job_id = str(target.job_id)

        # The user paused, cancelled or deleted the job between the dispatch and
        # this pickup. Revocation is a broadcast and can miss (worker restarting,
        # broker blip), so the row -- not the broker -- is the authority on
        # whether this area is still wanted.
        reason = _abandon_reason(job)
        if reason:
            _abandon_target(db, target, reason)
            logger.info(
                "job no longer accepting work, dropping scrape task",
                extra={"target_id": job_target_id, "reason": reason},
            )
            return

        with log_context(
            job_id=job_id,
            target_id=str(target.id),
            source=source,
            keyword=target.keyword,
            location=target.location_label,
        ):
            target.status = "running"
            target.places_found = 0
            target.places_done = 0
            target.heartbeat_at = datetime.utcnow()
            if job is not None and job.status == "queued":
                job.status = "running"
            db.commit()
            logger.info("target scrape started", extra={"attempt": self.request.retries + 1})

            search_url = build_search_url(target.keyword, target.location_label)
            publish_job_event(
                job_id,
                "target_started",
                targetId=str(target.id),
                keyword=target.keyword,
                location=target.location_label,
                source=source,
                searchUrl=search_url,
                attempt=self.request.retries + 1,
            )

            try:
                place_urls = asyncio.run(get_place_urls(search_url))
            except Exception as exc:
                if retries_left(self, get_retry_ceiling(db)):
                    raise _retry(
                        self, exc, job_id=job_id, targetId=str(target.id), stage="feed"
                    ) from exc
                target.status = "error"
                db.commit()
                _refresh_job_status(db, target.job_id)
                # Terminal: the slot this target held is free for the next one
                # waiting behind the concurrency limit.
                dispatch_ready_targets(db)
                logger.error("target scrape failed, retries exhausted", exc_info=exc)
                publish_job_event(
                    job_id,
                    "target_error",
                    targetId=str(target.id),
                    keyword=target.keyword,
                    location=target.location_label,
                    error=f"{type(exc).__name__}: {exc}"[:300],
                )
                raise

            target.places_found = len(place_urls)
            # A feed with no places has no second phase to wait for, so it is
            # terminal right here; anything else stays "running" until its
            # places have been counted off by `scrape_place`.
            target.status = "done" if not place_urls else "running"
            db.commit()

            publish_job_event(
                job_id,
                "feed_done",
                targetId=str(target.id),
                keyword=target.keyword,
                location=target.location_label,
                placesFound=len(place_urls),
            )
            logger.info("feed scrape done", extra={"places_enqueued": len(place_urls)})

            for place_url in place_urls:
                scrape_place.delay(job_id, place_url, source, str(target.id))

            if not place_urls:
                _refresh_job_status(db, target.job_id)
                dispatch_ready_targets(db)  # nothing to scrape, so the slot is free now
    finally:
        db.close()


def _abandon_reason(job: Job | None) -> str | None:
    """Why this task should stop before it opens a browser, or None to carry on.

    Three ways a queued task can arrive at work nobody wants any more: the job
    was paused, it was cancelled, or it was deleted outright while the task sat
    on the broker. `app.workers.control` revokes on all three, but a revoke is a
    best-effort broadcast -- this is the check that actually holds.
    """
    if job is None:
        return "missing"
    if job.status in HALTED_STATUSES:
        return job.status
    return None


def _abandon_target(db, target: JobTarget, reason: str) -> None:
    """Give up a target's slot without scraping it.

    A pause leaves the target waiting -- undispatched, unchanged, ready to be
    handed out again by `resume_job`. Anything else is terminal, so the target is
    cancelled with it. Written as a bulk UPDATE because "the job was deleted" is
    one of the reasons we get here, and the row may be going away underneath us.
    """
    values = (
        {"dispatched_at": None, "dispatch_id": None}
        if reason == "paused"
        else {"status": "cancelled", "dispatched_at": None, "dispatch_id": None}
    )
    db.execute(update(JobTarget).where(JobTarget.id == target.id).values(**values))
    db.commit()
    # Whatever it was holding belongs to the next job in line.
    dispatch_ready_targets(db)


def _is_superseded(task, target: JobTarget) -> bool:
    """Whether this task is a stale copy the dispatcher has already replaced.

    The dispatcher stamps each hand-off with the Celery task id it used. If the
    target now carries a different one, it was re-queued (see
    `dispatch._reclaim_lost_dispatches`) and something else owns it -- running
    anyway would scrape the area twice and double every result row.

    Retries and broker re-deliveries keep the original task id, so they are not
    affected. `request.id` is None when a task body is called directly, which is
    how the unit tests exercise this; treat that as "not superseded".
    """
    task_id = getattr(task.request, "id", None)
    return bool(target.dispatch_id and task_id and target.dispatch_id != task_id)


@celery_app.task(bind=True, max_retries=settings.task_max_retries_feed)
def scrape_google_maps(self, job_target_id: str) -> None:
    """Run 3.2 -> 3.3 for one `JobTarget` against Google Maps."""
    _run_maps_scrape_task(
        self, job_target_id, build_search_url=build_search_url, get_place_urls=get_place_urls
    )


@celery_app.task(bind=True, max_retries=settings.task_max_retries_feed)
def scrape_bing_maps(self, job_target_id: str) -> None:
    """Run 9.1 -> 9.2 for one `JobTarget` against Bing Maps. Mirrors
    `scrape_google_maps`; same shared body, Bing's query builder/feed scroller."""
    _run_maps_scrape_task(
        self,
        job_target_id,
        build_search_url=build_bing_search_url,
        get_place_urls=get_bing_place_urls,
    )


@celery_app.task(bind=True, max_retries=settings.task_max_retries_place)
def scrape_place(
    self, job_id: str, place_url: str, source: str, target_id: str | None = None
) -> None:
    """Run the Phase 3/4 pipeline for one place (detail scrape -> website/email
    enrichment) and write a `Result` row. A place that never renders (empty dict
    from `get_place_data`) is skipped, not retried -- there's nothing to retry.

    `target_id` ties the place back to the `JobTarget` whose feed produced it, so
    finishing it (written, skipped, or failed for good) counts off that target's
    `places_done`. It defaults to `None` only so a task already sitting on the
    queue from an older deploy still runs; those simply don't advance a counter.
    """
    db = AppSessionLocal()
    try:
        with log_context(job_id=job_id, target_id=target_id, place_url=place_url, source=source):
            # A cancelled or deleted job can still have hundreds of place tasks on
            # the queue -- they are enqueued in one burst per feed, so revoking
            # them all is unreliable. This check is cheap (one row) and runs before
            # anything launches a browser, so a cancel takes effect in seconds
            # rather than at the end of the area. Paused jobs are not stopped here
            # on purpose: pause lets areas already open finish, and dropping their
            # places would strand the target's counters short of complete.
            halted = _place_halt_reason(db, job_id)
            if halted:
                logger.info("job halted, dropping place task", extra={"reason": halted})
                return

            publish_job_event(
                job_id,
                "place_started",
                targetId=target_id,
                placeUrl=place_url,
                attempt=self.request.retries + 1,
            )
            # Captured so the source of the final phone/email can be told apart
            # after enrichment merges the site crawl in -- Maps' own values always
            # sort first when present (place_enrichment._merge), so "did the raw
            # detail scrape already have one" is the whole test.
            raw_detail: dict = {}

            def _announce_detail(detail: dict) -> None:
                raw_detail.update(detail)
                publish_job_event(
                    job_id,
                    "place_detail",
                    targetId=target_id,
                    placeUrl=place_url,
                    name=detail.get("name"),
                    category=detail.get("category"),
                    address=detail.get("address"),
                    phone=detail.get("phone"),
                    website=detail.get("website"),
                )

            def _announce_crawl(contacts: SiteContacts) -> None:
                publish_job_event(
                    job_id,
                    "site_crawled",
                    targetId=target_id,
                    placeUrl=place_url,
                    pagesCrawled=contacts.pages_crawled,
                    pagesDiscovered=contacts.pages_discovered,
                    truncated=contacts.truncated,
                    emailsFound=len(contacts.emails),
                    phonesFound=len(contacts.phones),
                    networks=sorted(contacts.socials),
                )

            # Read per place rather than once per worker: the crawler is a
            # runtime setting, and someone turning it off because a job is
            # crawling too slowly expects the places still queued to obey.
            deep_crawl = get_deep_crawl_enabled(db)
            crawl_budget = (
                budget_from_settings(get_deep_crawl_max_pages(db)) if deep_crawl else None
            )

            try:
                place = asyncio.run(
                    _scrape_and_enrich(
                        place_url,
                        source,
                        _announce_detail,
                        deep_crawl=deep_crawl,
                        budget=crawl_budget,
                        on_crawl=_announce_crawl,
                    )
                )
            except Exception as exc:
                if retries_left(self, get_retry_ceiling(db)):
                    raise _retry(
                        self, exc, job_id=job_id, targetId=target_id,
                        placeUrl=place_url, stage="place",
                    ) from exc
                logger.error("place scrape failed, retries exhausted", exc_info=exc)
                publish_job_event(
                    job_id,
                    "place_error",
                    targetId=target_id,
                    placeUrl=place_url,
                    error=f"{type(exc).__name__}: {exc}"[:300],
                )
                _finish_place(db, job_id, target_id)
                raise

            if not place:
                logger.info("place produced no data, skipping")
                publish_job_event(
                    job_id,
                    "place_skipped",
                    targetId=target_id,
                    placeUrl=place_url,
                    reason="no data on page",
                )
                _finish_place(db, job_id, target_id)
                return

            # The place panel hands back one address string and nothing splits it,
            # so the target's own ZIP/city/region/country is where those four
            # columns come from. Sound because the search that produced this place
            # was run for exactly that postal code -- Maps does return the odd
            # neighbouring listing, but the area is right either way.
            area = _target_area(db, target_id)

            # Scraping one place takes tens of seconds, so re-read before writing:
            # the job may have been cancelled or deleted while this was in the
            # browser, and inserting a row against a job that no longer exists is
            # a foreign-key error in the worker rather than a clean drop.
            halted = _place_halt_reason(db, job_id)
            if halted:
                logger.info("job halted mid-scrape, discarding place", extra={"reason": halted})
                return

            socials = place.get("socials") or {}

            # Maps' own phone/email always sort first when present (see
            # place_enrichment._merge), so whether the *raw* detail scrape --
            # captured before enrichment ran, via _announce_detail -- already
            # had a value is the whole test for where the final one came from.
            phone_source = "maps listing" if raw_detail.get("phone") else (
                "site crawl" if place.get("phone") else None
            )
            email_source = "maps listing" if raw_detail.get("email") else (
                "site crawl" if place.get("email") else None
            )

            # Off unless Settings > Enrichment turns it on (app.core.runtime_settings) --
            # previously ran unconditionally for every place with a website.
            tech_stack = (
                asyncio.run(fetch_tech_stack(place.get("website")))
                if get_tech_fingerprint_enabled(db) else []
            )

            place_key = compute_place_key(
                place.get("name"),
                place.get("address"),
                place.get("zip_code") or area.get("zip_code"),
            )
            prior = None
            if place_key:
                prior = db.execute(
                    select(Result)
                    .where(Result.place_key == place_key)
                    .order_by(Result.scraped_at.desc())
                    .limit(1)
                ).scalar_one_or_none()

            # Suppression List enforcement ("never scraped, never stored") --
            # checked here rather than before the Playwright launch because
            # domain/email suppression can only be evaluated once enrichment
            # has resolved them; a place-level rule (place_key) could in
            # theory skip earlier, but one extra query per place isn't worth
            # a second code path for that case alone. See
            # app.scraping.common.suppression for the exact-match rules.
            provisional = Result(
                website=place.get("website"), email=place.get("email"), place_key=place_key,
            )
            suppression_entries = db.execute(
                select(SuppressionEntry.kind, SuppressionEntry.value)
            ).all()
            if suppression_entries and result_is_suppressed(provisional, list(suppression_entries)):
                logger.info("place matched a suppression rule, discarding")
                publish_job_event(
                    job_id, "place_skipped", targetId=target_id, placeUrl=place_url,
                    reason="suppressed",
                )
                _finish_place(db, job_id, target_id)
                return

            result = Result(
                job_id=uuid.UUID(job_id),
                category=place.get("category"),
                name=place.get("name"),
                address=place.get("address"),
                city=place.get("city") or area.get("city"),
                state=place.get("state") or area.get("region"),
                country=place.get("country") or area.get("country"),
                zip_code=place.get("zip_code") or area.get("zip_code"),
                phone=place.get("phone"),
                email=place.get("email"),
                website=place.get("website"),
                latitude=place.get("latitude"),
                longitude=place.get("longitude"),
                rating=place.get("rating"),
                phone_source=phone_source,
                email_source=email_source,
                tech_stack=", ".join(tech_stack) or None,
                place_key=place_key,
                **_social_columns(socials),
            )
            db.add(result)
            db.flush()  # assigns result.id without committing, so history rows can reference it
            record_history(db, result, prior)
            db.commit()
            logger.info(
                "result written",
                extra={
                    "result_id": str(result.id),
                    "emails": len(place.get("emails") or []),
                    "phones": len(place.get("phones") or []),
                    "has_website": bool(place.get("website")),
                    "networks": sorted(socials),
                    "crawled_pages": place.get("crawled_pages") or 0,
                },
            )
            # The row itself, not just a count -- this is what the UI renders as
            # "currently scraping <name>, got phone/website/email".
            publish_job_event(
                job_id,
                "result",
                targetId=target_id,
                placeUrl=place_url,
                result={
                    "id": str(result.id),
                    "name": result.name,
                    "category": result.category,
                    "address": result.address,
                    "zipCode": result.zip_code,
                    "phone": result.phone,
                    "email": result.email,
                    "website": result.website,
                    "latitude": result.latitude,
                    "longitude": result.longitude,
                    "socials": socials,
                    "scrapedAt": result.scraped_at.isoformat(),
                },
            )
            _finish_place(db, job_id, target_id)
    finally:
        db.close()


_PLACE_SCRAPERS = {"google": get_place_data, "bing": get_bing_place_data}


async def _scrape_and_enrich(
    place_url: str,
    source: str,
    on_detail=None,
    *,
    deep_crawl: bool = False,
    budget=None,
    on_crawl=None,
) -> dict:
    """Detail scrape, then website/email enrichment.

    `on_detail` is called with the raw detail-panel fields before enrichment
    runs. Enrichment does its own network round-trips (site fetch, search
    fallback, email mining, and with `deep_crawl` on a walk of the whole site)
    and can take tens of seconds, so this is what lets the UI show a business the
    moment its name/phone are known rather than only once the whole record is
    finished. `on_crawl` reports the crawl once it lands.
    """
    get_data = _PLACE_SCRAPERS.get(source, get_place_data)
    place = await get_data(place_url)
    if not place:
        return {}
    if on_detail is not None:
        on_detail(dict(place))
    return await enrich_place_data(
        place, deep_crawl=deep_crawl, budget=budget, on_crawl=on_crawl
    )


def compute_place_key(name: str | None, address: str | None, zip_code: str | None) -> str | None:
    """Deterministic identity for "this business" across separate job runs.

    Results are otherwise insert-only with no cross-job identity (no
    Google/Bing place id is captured today, and parsing one out of the Maps
    URL means touching the untested live-scraper regex surface for a single
    screen's benefit -- see the migration docstring). Name+address+zip,
    normalized, is what's available without that: good enough to recognise
    "the same listing showed up in a later job", not good enough to be a real
    place id. Returns `None` when there isn't enough to key on (no name and
    no address is as good as no identity).
    """
    parts = [p.strip().lower() for p in (name, address, zip_code) if p and p.strip()]
    if not parts:
        return None
    return sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def record_history(db, result: Result, prior: Result | None) -> None:
    """Diff `result` against the most recent prior result for the same
    `place_key` (any job) and write one `result_history` row per changed field.

    Only ever compares against the immediately preceding result -- not the
    full chain -- so a value that changes and changes back still gets two
    honest entries rather than being collapsed against some older baseline.
    No-op when there is no prior result (first time this business was seen).
    """
    if prior is None:
        return
    now = datetime.utcnow()
    for field in HISTORY_FIELDS:
        old_value = getattr(prior, field)
        new_value = getattr(result, field)
        if field == "rating":
            changed = old_value != new_value
        else:
            changed = (old_value or None) != (new_value or None)
        if not changed:
            continue
        db.add(
            ResultHistory(
                result_id=result.id,
                field=field,
                old_value=None if old_value is None else str(old_value),
                new_value=None if new_value is None else str(new_value),
                changed_at=now,
            )
        )


def _social_columns(socials: dict) -> dict:
    """Map the crawler's `{network: [url, ...]}` onto the `results` columns.

    One column per network holding the first (best-ranked) profile found, plus
    `other_socials` for the recognised networks that don't have a column --
    joined, because that one is a list by definition. Networks with no hit are
    left out entirely, so the columns stay NULL rather than empty strings.
    """
    columns: dict = {}
    for network in SOCIAL_COLUMNS:
        urls = socials.get(network) or []
        if urls:
            columns[network] = urls[0][:SOCIAL_COLUMN_CHARS]
    other = socials.get(OTHER_SOCIAL_KEY) or []
    if other:
        columns["other_socials"] = ", ".join(other)[:OTHER_SOCIALS_CHARS]
    return columns


def _place_halt_reason(db, job_id: str) -> str | None:
    """Whether a place task should drop itself: "cancelled", "missing", or None.

    Narrower than `_abandon_reason` -- a paused job's places keep going, because
    pause means "start no new areas", not "abandon the one that's open". See the
    module docstring on `app.workers.control` for why stopping mid-area is worse
    than letting it finish.
    """
    db.expire_all()  # the control endpoint commits in another process's session
    job = db.get(Job, uuid.UUID(job_id))
    if job is None:
        return "missing"
    return "cancelled" if job.status == "cancelled" else None


def _target_area(db, target_id: str | None) -> dict:
    """The ZIP/city/region/country a target was queued for, or an empty map.

    Empty for a hand-typed location (no ZIP was ever picked) and for a
    `scrape_place` task queued before targets carried geo at all, so every
    caller has to treat the fields as optional.
    """
    if not target_id:
        return {}
    target = db.get(JobTarget, uuid.UUID(target_id))
    if target is None:
        return {}
    return {
        "zip_code": target.zip_code,
        "city": target.city,
        "region": target.region,
        "country": target.country,
    }


def _finish_place(db, job_id: str, target_id: str | None) -> None:
    """Count one place off its target, then roll the target (and maybe the job) up.

    The increment is a single UPDATE rather than read-modify-write: with more
    than one worker slot, several places under the same target finish at once
    and a Python-side `+= 1` would lose counts, leaving the target permanently
    one short of complete and the job stuck on "running" forever.
    """
    if not target_id:
        return

    target_uuid = uuid.UUID(target_id)
    db.execute(
        update(JobTarget)
        .where(JobTarget.id == target_uuid)
        .values(places_done=JobTarget.places_done + 1, heartbeat_at=datetime.utcnow())
    )
    db.commit()
    _refresh_target_status(db, target_uuid, job_id)


def _refresh_target_status(db, target_id: uuid.UUID, job_id: str) -> None:
    """Mark a target done once every place its feed produced has been accounted for."""
    db.expire_all()
    target = db.get(JobTarget, target_id)
    if target is None or target.status != "running":
        return
    if target.places_done < target.places_found:
        return

    target.status = "done"
    db.commit()
    logger.info(
        "target finished",
        extra={"target_id": str(target_id), "places": target.places_found},
    )
    publish_job_event(
        job_id,
        "target_done",
        targetId=str(target_id),
        keyword=target.keyword,
        location=target.location_label,
        placesFound=target.places_found,
    )
    _refresh_job_status(db, target.job_id)
    # This is the ordinary end of a target and so the ordinary place where the
    # next queued area gets its turn.
    dispatch_ready_targets(db)


def _refresh_job_status(db, job_id: uuid.UUID) -> None:
    """Once every target under a job is terminal (done/error/cancelled), roll that
    up into the job's own status. Left alone while any target is queued/running.

    A paused job normally has queued targets and so never settles here, which is
    what keeps it paused. One whose last running area finishes while paused has
    nothing left to resume, and settling it is right -- `resume_job` reaches the
    same conclusion from the same helper.
    """
    db.expire_all()  # other worker slots commit target rows in their own sessions
    statuses = list(
        db.execute(select(JobTarget.status).where(JobTarget.job_id == job_id)).scalars().all()
    )
    settled = settled_status(statuses)
    if settled is None:
        return

    job = db.get(Job, job_id)
    if job is None or job.status in TERMINAL_STATUSES:
        return
    job.status = settled
    db.commit()
    logger.info("job finished", extra={"job_id": str(job_id), "status": job.status})

    results_count = (
        db.scalar(select(func.count()).select_from(Result).where(Result.job_id == job_id)) or 0
    )
    publish_job_event(
        str(job_id), "job_done", status=job.status, resultsCount=results_count
    )


@celery_app.task(bind=True, max_retries=settings.task_max_retries_export)
def export_job(self, export_id: str) -> str:
    """Pulls the `Export` row (job_id/format/columns/row_scope already set by
    the endpoint), writes CSV/XLSX/KML/JSONL for that job's results (or pushes
    a Google Sheet for "sheets"), and stamps file_path (or external_url) /
    status/generated_at/expires_at/row_count/size_bytes on completion. Returns
    the generated file path, or the sheet URL for "sheets".

    `row_scope` is read but only "all" does anything today -- see
    `Export.row_scope`'s column comment for why "filter"/"selection" aren't
    wired yet. Every other scope value falls back to "all" rather than
    erroring, so an old row (row_scope=None) behaves exactly as before.
    """
    db = AppSessionLocal()
    try:
        export = db.get(Export, uuid.UUID(export_id))
        if export is None:
            logger.warning("export row missing, dropping task", extra={"export_id": export_id})
            return ""

        with log_context(job_id=str(export.job_id), export_id=str(export.id)):
            export.status = "running"
            db.commit()

            try:
                results = (
                    db.execute(
                        select(Result)
                        .where(Result.job_id == export.job_id)
                        .order_by(Result.scraped_at)
                    )
                    .scalars()
                    .all()
                )

                os.makedirs(settings.export_dir, exist_ok=True)
                output_path = os.path.join(settings.export_dir, f"{export.id}.{export.format}")

                columns = export.columns.split(",") if export.columns else None
                writer = _EXPORT_WRITERS[export.format]
                result_path = writer(results, output_path, columns=columns)
            except Exception as exc:
                if retries_left(self, get_retry_ceiling(db)):
                    raise _retry(self, exc) from exc
                export.status = "error"
                db.commit()
                logger.error("export failed, retries exhausted", exc_info=exc)
                raise

            now = datetime.utcnow()
            # "sheets" hands back a share URL, not a local path -- nothing to
            # stream/size on disk for that format (see sheets_writer.write_sheets).
            if export.format == "sheets":
                export.external_url = result_path
            else:
                export.file_path = result_path
                export.size_bytes = os.path.getsize(result_path) if os.path.exists(result_path) else None
            export.status = "done"
            export.generated_at = now
            export.expires_at = now + timedelta(days=get_export_retention_days(db))
            export.row_count = len(results)
            db.commit()
            logger.info(
                "export written",
                extra={"format": export.format, "rows": len(results), "result_path": result_path},
            )
            return result_path
    finally:
        db.close()


@celery_app.task
def purge_expired_exports() -> dict:
    """Deletes the on-disk file for every `Export` whose `expires_at` has
    passed, then clears `file_path` (download/list endpoints already treat a
    missing file as "not ready" -- see exports.py::download_export). The row
    itself is kept so the History table can still show "expired · delete" per
    the Figma design, rather than the export disappearing outright.

    Registered on Celery Beat's daily tick (app.core.celery_app), same pattern
    as `dispatch_due_schedules`. Rows with `expires_at IS NULL` (every export
    written before this migration) are left alone -- there is nothing to
    compare against, and guessing an expiry for them would be inventing data
    the export never actually promised.
    """
    db = AppSessionLocal()
    purged = 0
    try:
        now = datetime.utcnow()
        expired = db.execute(
            select(Export).where(
                Export.expires_at.is_not(None),
                Export.expires_at <= now,
                Export.file_path.is_not(None),
            )
        ).scalars().all()

        for export in expired:
            if export.file_path and os.path.exists(export.file_path):
                with suppress(OSError):
                    os.remove(export.file_path)
            export.file_path = None
            purged += 1

        db.commit()
        if purged:
            logger.info("purged expired exports", extra={"count": purged})
        return {"purged": purged}
    finally:
        db.close()


@celery_app.task
def purge_expired_results() -> dict:
    """Deletes every `Result` row older than Settings > Data Retention's
    results retention window (app.core.runtime_settings.get_results_retention_days).

    Genuinely missing before this cycle -- no age-based cleanup of the
    `results` table existed anywhere; only whole-job deletion cascaded
    results (see jobs.py's `DELETE /api/jobs/{id}`). Registered on Celery
    Beat's daily tick, same pattern as `purge_expired_exports`. `job_id` is
    untouched -- only rows are removed, the job itself (and its status
    history) stays, same "history kept, data purged" contract the Settings
    copy describes for the Danger Zone's manual purge.
    """
    db = AppSessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=get_results_retention_days(db))
        # result_history FKs onto results.id and must go first -- same
        # ForeignKeyViolation risk as the whole-job delete in workers.control.
        db.execute(
            delete(ResultHistory).where(
                ResultHistory.result_id.in_(
                    select(Result.id).where(Result.scraped_at < cutoff)
                )
            )
        )
        purged = db.execute(delete(Result).where(Result.scraped_at < cutoff)).rowcount or 0
        db.commit()
        if purged:
            logger.info("purged expired results", extra={"count": purged})
        return {"purged": purged}
    finally:
        db.close()


@celery_app.task
def dispatch_due_schedules() -> dict:
    """Fires every enabled `Schedule` whose `next_run_at` has passed.

    Registered on Celery Beat's minute tick (app.core.celery_app), not called
    from anywhere else -- this is the only place a schedule actually creates a
    job. A schedule found more than MISFIRE_GRACE_MINUTES past due is skipped
    rather than run late (e.g. beat itself was down): running it against
    whatever "now" happens to be, hours after it was meant to fire, would be a
    worse outcome than admitting the run was missed.
    """
    db = AppSessionLocal()
    fired = 0
    misfired = 0
    try:
        now = datetime.utcnow()
        due = db.execute(
            select(Schedule).where(
                Schedule.enabled.is_(True),
                Schedule.next_run_at.is_not(None),
                Schedule.next_run_at <= now,
            )
        ).scalars().all()

        for schedule in due:
            grace_cutoff = now - timedelta(minutes=MISFIRE_GRACE_MINUTES)
            overdue = schedule.next_run_at < grace_cutoff
            with log_context(schedule_id=str(schedule.id)):
                if overdue:
                    schedule.last_result = "misfired"
                    misfired += 1
                    logger.warning(
                        "schedule misfired, skipping this run",
                        extra={"scheduled_for": schedule.next_run_at.isoformat()},
                    )
                else:
                    template = db.get(JobTemplate, schedule.template_id)
                    owner = db.get(User, schedule.owner_id)
                    if template is None or owner is None:
                        schedule.last_result = "error"
                        logger.error(
                            "schedule's template or owner is gone, disabling",
                            extra={"template_id": str(schedule.template_id)},
                        )
                        schedule.enabled = False
                        schedule.next_run_at = None
                        db.commit()
                        continue

                    try:
                        job, _targets = create_job_from_spec(
                            db,
                            user=owner,
                            keywords=list(template.keywords),
                            locations=[LocationSpec(**loc) for loc in template.locations],
                            source=template.source,
                            name=schedule.name,
                            schedule_id=schedule.id,
                        )
                        schedule.last_result = "done"
                        schedule.last_job_id = job.id
                        fired += 1
                        logger.info("schedule fired", extra={"job_id": str(job.id)})
                    except Exception as exc:  # noqa: BLE001 -- one bad schedule must not sink the tick
                        schedule.last_result = "error"
                        logger.error("schedule run failed", exc_info=exc)

                schedule.last_run_at = now
                schedule.next_run_at = next_run_after(schedule.cadence, schedule.timezone, now)
                db.commit()

            return {"fired": fired, "misfired": misfired, "checked": len(due)}
    finally:
        db.close()
