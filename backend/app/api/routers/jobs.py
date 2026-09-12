"""Job endpoints: create job (keyword x location pairs), list, get status, live
progress, and the queue controls.

POST   /api/jobs               -> create Job + JobTarget rows, enqueue Celery tasks
GET    /api/jobs               -> list jobs for current user, paginated
GET    /api/jobs/{id}          -> job detail + status
GET    /api/jobs/{id}/results  -> paginated results grid data
WS     /api/jobs/{id}/stream   -> live progress (result counts, status transitions)
POST   /api/jobs/{id}/pause    -> stop starting new areas, keep the queue
POST   /api/jobs/{id}/resume   -> put a paused job back in the dispatch pool
POST   /api/jobs/{id}/cancel   -> retire every unfinished area, keep the results
DELETE /api/jobs/{id}          -> remove the job, its targets, results and exports

The four controls live in `app.workers.control`; that module's docstring is where
the semantics are written down (in particular: pause is a queue gate, so areas
already being scraped finish rather than being thrown away). Each of them answers
with the job's fresh payload, whose `actions` block says which controls are legal
from the new state -- the same predicates these endpoints validate against, so
the UI can't offer a button that would 409.
"""

import asyncio
import logging
import uuid
from contextlib import suppress
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import authenticate_ws_token, get_app_db, get_current_user, require_active_license
from app.core.config import get_settings
from app.core.events import STREAM_START, read_job_events
from app.core.logging import log_context
from app.core.runtime_settings import get_score_weights
from app.db.models.job import ACTIVE_STATUSES, TERMINAL_STATUSES, Job, JobTarget
from app.db.models.result import LEAD_STATUSES, Result, ResultHistory
from app.db.models.user import User
from app.scraping.common.lead_score import lead_score
from app.workers.control import (
    can_cancel,
    can_pause,
    can_resume,
    cancel_job,
    delete_job,
    job_actions,
    pause_job,
    resume_job,
)
from app.workers.dispatch import dispatch_ready_targets

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

SUPPORTED_SOURCES = {"google", "bing"}


class LocationSpec(BaseModel):
    """One search area -- normally a single postal code.

    `label` is what gets appended to the keyword in the Maps query, so it has to
    read like something a person would type ("78701, Austin, Texas"). The rest is
    the selection it was built from, kept so results can be attributed back to a
    ZIP without re-parsing the address off the place panel.
    """

    model_config = ConfigDict(populate_by_name=True)

    label: str
    zip_code: str | None = Field(default=None, alias="zipCode")
    city: str | None = None
    region: str | None = None
    country: str | None = None


class CreateJobRequest(BaseModel):
    keywords: list[str] = Field(min_length=1)
    # A bare string is still a valid location -- the hand-typed path on the
    # Locations page produces those, and so does the curl example in the README.
    # It just carries no ZIP, so its results get no city/state/country/zip columns.
    locations: list[LocationSpec | str] = Field(min_length=1)
    source: str = "google"
    name: str | None = Field(default=None, max_length=255)


def normalize_locations(raw: list[LocationSpec | str]) -> list[LocationSpec]:
    """Coerce the mixed string/object list into specs, trimmed and deduplicated.

    Deduplication is on the label, case-insensitively: the frontend can queue the
    same ZIP twice (append after a partial re-selection) and every duplicate is a
    full extra scrape of the same area for the same keyword.
    """
    out: list[LocationSpec] = []
    seen: set[str] = set()
    for entry in raw:
        spec = LocationSpec(label=entry) if isinstance(entry, str) else entry
        label = spec.label.strip()
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            LocationSpec(
                label=label,
                zip_code=(spec.zip_code or "").strip() or None,
                city=(spec.city or "").strip() or None,
                region=(spec.region or "").strip() or None,
                country=(spec.country or "").strip() or None,
            )
        )
    return out


def create_job_from_spec(
    db: Session,
    *,
    user: User,
    keywords: list[str],
    locations: list[LocationSpec | str],
    source: str,
    name: str | None,
    schedule_id: uuid.UUID | None = None,
) -> tuple[Job, list[JobTarget]]:
    """Cross keywords x locations into one `JobTarget` row per pair, then let the
    dispatcher start as many of them as the concurrency setting allows.

    Shared by `POST /api/jobs` and the templates router's run endpoint -- a
    template run is exactly this, just with keywords/locations/source read back
    off a saved row instead of the request body.

    Note what this does *not* do: put the whole job on the broker. Targets are
    written as "queued, not dispatched" and `dispatch_ready_targets` hands over
    only enough to fill the free slots (`concurrent_targets`, editable from the
    Settings page); the rest are picked up as running targets finish. Enqueuing
    everything up front is what made a two-hundred-ZIP job try to scrape two
    hundred areas at once.

    Locations are ZIP-scoped, so the cross product grows fast: "every ZIP in
    Texas" is ~2600 targets per keyword, each its own browser session. Anything
    over `max_job_targets` is refused here rather than accepted and left to
    starve the queue for a day.
    """
    clean_keywords = [k.strip() for k in keywords if k.strip()]
    clean_locations = normalize_locations(locations)
    if not clean_keywords or not clean_locations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="keywords and locations must not be empty",
        )
    if source not in SUPPORTED_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unsupported source: {source!r}",
        )

    target_count = len(clean_keywords) * len(clean_locations)
    if target_count > settings.max_job_targets:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "target_limit_exceeded",
                "message": (
                    f"{target_count} targets ({len(clean_keywords)} keywords x "
                    f"{len(clean_locations)} locations) exceeds the {settings.max_job_targets} "
                    "per-job limit — split it across several jobs"
                ),
                "targetCount": target_count,
                "maxTargets": settings.max_job_targets,
            },
        )

    job = Job(
        source=source,
        created_by=user.id,
        status="queued",
        name=(name or "").strip() or None,
        schedule_id=schedule_id,
    )
    db.add(job)
    db.flush()  # populate job.id (client-side uuid4 default) before targets reference it

    targets = [
        JobTarget(
            job_id=job.id,
            keyword=keyword,
            location_label=location.label,
            zip_code=location.zip_code,
            city=location.city,
            region=location.region,
            country=location.country,
        )
        for keyword in clean_keywords
        for location in clean_locations
    ]
    db.add_all(targets)
    db.commit()

    with log_context(job_id=str(job.id), source=source):
        started = dispatch_ready_targets(db)
        logger.info(
            "job enqueued",
            extra={"targets": len(targets), "dispatched": started},
        )

    return job, targets


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_job(
    payload: CreateJobRequest,
    user: User = Depends(require_active_license),
    db: Session = Depends(get_app_db),
) -> dict:
    job, targets = create_job_from_spec(
        db,
        user=user,
        keywords=payload.keywords,
        locations=payload.locations,
        source=payload.source,
        name=payload.name,
    )
    return _job_dict(job, targets)


@router.get("/")
def list_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    base = select(Job).where(Job.created_by == user.id).order_by(Job.created_at.desc())
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(base.offset((page - 1) * page_size).limit(page_size)).scalars().all()

    job_ids = [job.id for job in rows]
    progress = _progress_by_job(db, job_ids)
    leads = _lead_counts_by_job(db, job_ids)

    items = [
        _job_dict(job, progress=progress.get(job.id), leads=leads.get(job.id, 0)) for job in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


def _progress_by_job(db: Session, job_ids: list[uuid.UUID]) -> dict[uuid.UUID, float]:
    """Places-done / places-found per job, in one grouped query rather than one
    per row -- the Recent Jobs table renders up to a page's worth of these."""
    if not job_ids:
        return {}
    rows = db.execute(
        select(
            JobTarget.job_id,
            func.sum(JobTarget.places_done),
            func.sum(JobTarget.places_found),
        )
        .where(JobTarget.job_id.in_(job_ids))
        .group_by(JobTarget.job_id)
    ).all()
    return {job_id: (done / found if found else 0.0) for job_id, done, found in rows}


def _lead_counts_by_job(db: Session, job_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not job_ids:
        return {}
    rows = db.execute(
        select(Result.job_id, func.count())
        .where(Result.job_id.in_(job_ids))
        .group_by(Result.job_id)
    ).all()
    return dict(rows)


@router.get("/stats")
def get_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """Dashboard stat row. Scoped to the current user's own jobs/results, same as
    every other jobs endpoint -- there is no cross-account rollup anywhere else.

    Quota/usage stays absent here: license-level quota is a display concept
    (see app.core.plans.quota_for_plan, surfaced on GET /license and the
    account/usage endpoint) with nothing enforcing it against actual usage yet,
    so a number here would read as a ceiling that means something when it
    doesn't. Proxy health is NOT part of this response -- it's per-proxy, not
    per-user, and pool-wide across every account rather than scoped to one, so
    it's its own endpoint: GET /api/proxies/stats (app.api.routers.proxies).
    """
    jobs_running = (
        db.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.created_by == user.id, Job.status.in_(tuple(ACTIVE_STATUSES)))
        )
        or 0
    )

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    user_job_ids = select(Job.id).where(Job.created_by == user.id)
    places_today = (
        db.scalar(
            select(func.count())
            .select_from(Result)
            .where(Result.job_id.in_(user_job_ids), Result.scraped_at >= today_start)
        )
        or 0
    )

    results_today_with_email = (
        db.scalar(
            select(func.count())
            .select_from(Result)
            .where(
                Result.job_id.in_(user_job_ids),
                Result.scraped_at >= today_start,
                Result.email.is_not(None),
            )
        )
        or 0
    )
    leads_with_email_pct = (
        round(100 * results_today_with_email / places_today) if places_today else None
    )

    return {
        "jobsRunning": jobs_running,
        "placesScrapedToday": places_today,
        "leadsWithEmailPct": leads_with_email_pct,
    }


@router.get("/activity")
def get_activity(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    """Recent job status transitions, newest first -- the dashboard's Activity
    panel. Derived from `Job.updated_at` rather than a dedicated event log,
    which doesn't exist yet: this covers "job started/finished/failed" only,
    not the proxy/schedule events the Figma mock shows (those subsystems have
    no backing store either).
    """
    rows = (
        db.execute(
            select(Job)
            .where(Job.created_by == user.id, Job.status != "queued")
            .order_by(Job.updated_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )

    return {"items": [_activity_entry(job) for job in rows]}


def _activity_entry(job: Job) -> dict:
    kind = {
        "running": "started",
        "done": "finished",
        "error": "failed",
        "cancelled": "cancelled",
        "paused": "paused",
    }.get(job.status, job.status)
    return {
        "jobId": str(job.id),
        "jobName": job.name,
        "kind": kind,
        "status": job.status,
        "at": job.updated_at.isoformat(),
    }


@router.get("/{job_id}")
def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    job = _get_owned_job(db, job_id, user)
    targets = db.execute(select(JobTarget).where(JobTarget.job_id == job.id)).scalars().all()
    return _job_dict(job, targets)


@router.get("/{job_id}/results")
def get_job_results(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> dict:
    job = _get_owned_job(db, job_id, user)
    base = select(Result).where(Result.job_id == job.id).order_by(Result.scraped_at)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(base.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return {
        "items": [_result_dict(result) for result in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


class ResultUpdateRequest(BaseModel):
    """Lead Detail's three row-level actions. All optional/independent -- the
    drawer's SUPPRESS/TAG/CLAIM buttons each send only the one field they own,
    not a full replace, so two actions fired close together (e.g. a tag add
    while a suppress is in flight) can't stomp each other's other fields."""

    model_config = ConfigDict(populate_by_name=True)

    status: str | None = None
    tags: list[str] | None = None
    suppressed: bool | None = None


@router.get("/{job_id}/results/{result_id}")
def get_job_result(
    job_id: str,
    result_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    job = _get_owned_job(db, job_id, user)
    result = _get_owned_result(db, job.id, result_id)
    history = (
        db.execute(
            select(ResultHistory)
            .where(ResultHistory.result_id == result.id)
            .order_by(ResultHistory.changed_at.desc())
        )
        .scalars()
        .all()
    )
    return _result_dict(result, history=history, score_weights=get_score_weights(db))


@router.patch("/{job_id}/results/{result_id}")
def update_job_result(
    job_id: str,
    result_id: str,
    payload: ResultUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """Backs the Lead Detail drawer's CLAIM/SUPPRESS/TAG actions. Job-scoped
    only, same limitation `Result.suppressed`'s docstring already spells out --
    there is no cross-job place identity to key a global list against, so this
    marks one row, not a business."""
    job = _get_owned_job(db, job_id, user)
    result = _get_owned_result(db, job.id, result_id)

    if payload.status is not None:
        if payload.status not in LEAD_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"status must be one of {', '.join(LEAD_STATUSES)}",
            )
        result.status = payload.status
    if payload.tags is not None:
        clean = [t.strip() for t in payload.tags if t.strip()]
        result.tags = ", ".join(clean) or None
    if payload.suppressed is not None:
        result.suppressed = payload.suppressed

    db.commit()
    history = (
        db.execute(
            select(ResultHistory)
            .where(ResultHistory.result_id == result.id)
            .order_by(ResultHistory.changed_at.desc())
        )
        .scalars()
        .all()
    )
    return _result_dict(result, history=history, score_weights=get_score_weights(db))


def _get_owned_result(db: Session, job_id: uuid.UUID, result_id: str) -> Result:
    try:
        result_uuid = uuid.UUID(result_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid result id"
        ) from exc

    result = db.get(Result, result_uuid)
    if result is None or result.job_id != job_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="lead not found")
    return result


@router.post("/{job_id}/pause")
def pause(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """Stop handing this job new areas. Areas already scraping finish.

    The response's `paused` block is what the UI reports back: how many queued
    areas were pulled off the broker, and how many are still running and will
    keep going. "Paused, 3 areas finishing" is the honest message; a bare
    "Paused" invites a bug report when results keep arriving for a minute.
    """
    job = _get_owned_job(db, job_id, user)
    _require(can_pause(job.status), job.status, "pause")
    with log_context(job_id=str(job.id)):
        outcome = pause_job(db, job)
    return {**_job_dict(job), "paused": outcome}


@router.post("/{job_id}/resume")
def resume(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    job = _get_owned_job(db, job_id, user)
    _require(can_resume(job.status), job.status, "resume")
    with log_context(job_id=str(job.id)):
        outcome = resume_job(db, job)
    return {**_job_dict(job), "resumed": outcome}


@router.post("/{job_id}/cancel")
def cancel(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """Terminal stop. Unfinished areas are retired; collected results are kept,
    so a cancelled job can still be viewed and exported."""
    job = _get_owned_job(db, job_id, user)
    _require(can_cancel(job.status), job.status, "cancel")
    with log_context(job_id=str(job.id)):
        outcome = cancel_job(db, job)
    return {**_job_dict(job), "cancelled": outcome}


@router.delete("/{job_id}")
def delete(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """Remove the job and everything under it, running or not.

    Allowed from any status: a live job is cancelled first (see
    `control.delete_job`), because refusing until the user stops it themselves is
    just the same two steps with an error message in between.
    """
    job = _get_owned_job(db, job_id, user)
    with log_context(job_id=str(job.id)):
        return {"deleted": delete_job(db, job)}


def _require(allowed: bool, status_now: str, action: str) -> None:
    """409 rather than 422: the request is well-formed, the job is just in the
    wrong state for it -- which is what the client needs to be told, since it
    usually means someone else (or a worker) moved it first."""
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"cannot {action} a job that is {status_now}",
        )


@router.websocket("/{job_id}/stream")
async def job_stream(
    websocket: WebSocket,
    job_id: str,
    token: str = Query(...),
    db: Session = Depends(get_app_db),
) -> None:
    """Live progress feed. Browsers can't set an Authorization header on a
    WebSocket handshake, so the access token rides in as a query param instead.

    Simple polling for now (checks the DB every `job_stream_poll_interval_s`
    seconds and pushes only on change) -- swap for pub/sub (Redis, LISTEN/NOTIFY)
    if this gets noisy under load.
    """
    try:
        user = authenticate_ws_token(db, token)
        job = _get_owned_job(db, job_id, user)
    except HTTPException as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(exc.detail))
        return

    await websocket.accept()

    last_snapshot: dict | None = None
    last_event_id = STREAM_START
    try:
        while True:
            db.expire_all()  # drop cached rows so this sees commits made by other sessions
            job = db.get(Job, job.id)
            if job is None:
                break

            snapshot = _progress_snapshot(db, job)
            if snapshot != last_snapshot:
                await websocket.send_json({"kind": "progress", **snapshot})
                last_snapshot = snapshot

            # The activity events carry what the workers are doing right now --
            # which place is open, what came off it, what got retried -- so the
            # page can show the data arriving instead of just a rising count.
            events, last_event_id = await read_job_events(str(job.id), last_event_id)
            for event in events:
                await websocket.send_json({"kind": "activity", **event})

            # Paused is not terminal, so the socket stays up and the page keeps
            # showing the areas still finishing -- and starts moving again the
            # moment it is resumed, without a reconnect.
            if job.status in TERMINAL_STATUSES:
                # The worker commits the job's status before it publishes the
                # last events, so drain once more or the closing lines of the
                # feed are lost to the race.
                trailing, _ = await read_job_events(str(job.id), last_event_id)
                for event in trailing:
                    await websocket.send_json({"kind": "activity", **event})
                break
            await asyncio.sleep(settings.job_stream_poll_interval_s)
    except WebSocketDisconnect:
        return  # client hung up first; there's nothing left to close

    # Returning from a websocket endpoint does not send a close frame, so a job that
    # reaches a terminal status leaves the socket half-open: the browser sits there
    # until the transport gives up and reports an abnormal close (1006) instead of a
    # clean end-of-stream. Say goodbye explicitly.
    with suppress(RuntimeError):
        await websocket.close()


def _get_owned_job(db: Session, job_id: str, user: User) -> Job:
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid job id"
        ) from exc

    job = db.get(Job, job_uuid)
    if job is None or job.created_by != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return job


def _progress_snapshot(db: Session, job: Job) -> dict:
    """Counts the stream sends on every change: the job's status, how many rows
    have landed, and how far through its places each target is.

    Places are the real unit of work -- a job with one target spends almost all
    of its life inside that target -- so target counts alone make the progress
    bar sit at 0% until everything is finished.
    """
    targets = db.execute(select(JobTarget).where(JobTarget.job_id == job.id)).scalars().all()
    results_count = (
        db.scalar(select(func.count()).select_from(Result).where(Result.job_id == job.id)) or 0
    )
    return {
        "jobId": str(job.id),
        "status": job.status,
        "resultsCount": results_count,
        "placesFound": sum(target.places_found for target in targets),
        "placesDone": sum(target.places_done for target in targets),
        "targetsTotal": len(targets),
        "targetsDone": sum(1 for target in targets if target.status in TERMINAL_STATUSES),
        # Areas still behind the concurrency limit, i.e. not yet handed to a
        # worker at all -- the progress bar sitting still with a queue behind it
        # is normal now, so the UI has to be able to say so.
        "targetsWaiting": sum(
            1 for target in targets if target.status == "queued" and target.dispatched_at is None
        ),
        "targets": [_target_dict(target) for target in targets],
    }


def _job_dict(
    job: Job,
    targets: list[JobTarget] | None = None,
    *,
    progress: float | None = None,
    leads: int | None = None,
) -> dict:
    data = {
        "id": str(job.id),
        "status": job.status,
        "source": job.source,
        "name": job.name,
        "createdAt": job.created_at.isoformat(),
        # Which queue controls this job will accept right now. Sent rather than
        # left for the client to infer from the status, so the rule lives in one
        # place: the endpoints validate against these same predicates.
        "actions": job_actions(job.status),
    }
    if targets is not None:
        data["targets"] = [_target_dict(target) for target in targets]
    # Only list_jobs passes these (one grouped query for the whole page); the
    # detail/create paths already return the full `targets` block instead.
    if progress is not None or leads is not None:
        data["progressPct"] = round((progress or 0.0) * 100)
        data["leadsCount"] = leads or 0
    return data


def _target_dict(target: JobTarget) -> dict:
    return {
        "id": str(target.id),
        "keyword": target.keyword,
        "locationLabel": target.location_label,
        "zipCode": target.zip_code,
        "city": target.city,
        "region": target.region,
        "country": target.country,
        "status": target.status,
        "placesFound": target.places_found,
        "placesDone": target.places_done,
        # "queued" covers both "waiting for a concurrency slot" and "handed to
        # the broker, waiting for a worker"; this is what tells them apart.
        "dispatched": target.dispatched_at is not None,
    }


def _result_dict(
    result: Result,
    *,
    history: list[ResultHistory] | None = None,
    score_weights: dict[str, int] | None = None,
) -> dict:
    data: dict = {
        "id": str(result.id),
        "jobId": str(result.job_id),
        "category": result.category,
        "name": result.name,
        "address": result.address,
        "city": result.city,
        "state": result.state,
        "country": result.country,
        "zipCode": result.zip_code,
        # Both may carry several values joined with ", " -- everything the deep
        # site crawler found, appended to what Maps listed.
        "phone": result.phone,
        "email": result.email,
        "mobilePhone": result.mobile_phone,
        "decisionMaker": result.decision_maker,
        "reviewsCount": result.reviews_count,
        "sentimentScore": result.sentiment_score,
        "sentimentLabel": result.sentiment_label,
        "painPoints": result.pain_points,
        "website": result.website,
        "latitude": result.latitude,
        "longitude": result.longitude,
        "facebook": result.facebook,
        "instagram": result.instagram,
        "linkedin": result.linkedin,
        "twitter": result.twitter,
        "youtube": result.youtube,
        "tiktok": result.tiktok,
        "whatsapp": result.whatsapp,
        "otherSocials": result.other_socials,
        "scrapedAt": result.scraped_at.isoformat(),
        # Lead Detail only (below) -- absent from the Results grid response
        # shape, but same Result row, so always populated here regardless.
        "status": result.status,
        "tags": [t.strip() for t in (result.tags or "").split(",") if t.strip()],
        "suppressed": result.suppressed,
        "rating": result.rating,
        "phoneSource": result.phone_source,
        "emailSource": result.email_source,
        # Populated by a one-off home-page fetch (app.scraping.common.tech_fingerprint),
        # separate from the deep crawler -- NULL/empty on rows scraped before this
        # column existed, or where the fetch found no website/no known signature.
        "techStack": [t.strip() for t in (result.tech_stack or "").split(",") if t.strip()],
    }
    # Only the single-result endpoints pass this -- the paginated grid response
    # doesn't need per-row history and it would mean an extra query per row.
    if history is not None:
        data["history"] = [_history_dict(h) for h in history]
        data["score"] = lead_score(result, score_weights)
    return data


def _history_dict(entry: ResultHistory) -> dict:
    return {
        "field": entry.field,
        "oldValue": entry.old_value,
        "newValue": entry.new_value,
        "changedAt": entry.changed_at.isoformat(),
    }
