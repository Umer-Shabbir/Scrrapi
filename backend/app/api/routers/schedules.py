"""Schedule endpoints: recurring runs of a JobTemplate.

GET    /api/schedules              -> list schedules owned by the current user
POST   /api/schedules              -> create one (validates cadence + timezone,
                                       computes the first next_run_at)
GET    /api/schedules/{id}         -> detail (Schedule & Monitoring screen header)
PATCH  /api/schedules/{id}         -> rename, re-cadence, enable/disable
DELETE /api/schedules/{id}         -> remove it
GET    /api/schedules/{id}/runs    -> run history -- every job this schedule fired
POST   /api/schedules/{id}/run     -> fire it immediately, outside its cadence
GET    /api/schedules/preview      -> next-5-fire-times preview for the builder,
                                       before a row is saved

Cadence-driven firing is `app.workers.tasks.dispatch_due_schedules`, a
periodic task on Celery Beat's minute tick (registered in
app.core.celery_app); `POST /{id}/run` shares the same `create_job_from_spec`
call for a manual "Run now" that doesn't wait for the next scheduled tick.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_app_db, get_current_user, require_active_license
from app.api.routers.jobs import LocationSpec, _job_dict, create_job_from_spec
from app.core.scheduling import InvalidCadence, next_n_runs, next_run_after, validate_cadence
from app.db.models.job import Job, JobTarget
from app.db.models.result import Result
from app.db.models.schedule import Schedule
from app.db.models.template import JobTemplate
from app.db.models.user import User

router = APIRouter()


class ScheduleRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=255)
    template_id: str = Field(alias="templateId")
    cadence: str
    timezone: str = "UTC"
    enabled: bool = True


class ScheduleUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    cadence: str | None = None
    timezone: str | None = None
    enabled: bool | None = None


@router.get("/")
def list_schedules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> list[dict]:
    rows = (
        db.execute(
            select(Schedule)
            .where(Schedule.owner_id == user.id)
            .order_by(Schedule.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_schedule_dict(s) for s in rows]


@router.get("/{schedule_id}")
def get_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    return _schedule_dict(_get_owned_schedule(db, schedule_id, user))


@router.get("/{schedule_id}/runs")
def list_schedule_runs(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """Every job this schedule has fired, newest first -- the Run History table.
    Deliberately does not attempt new/changed/disappeared lead counts: there is
    no place-identity tracking across separate jobs to diff against, so this
    reports what's actually knowable (targets, places, duration, status)
    rather than a number that looks precise but isn't backed by anything.
    """
    schedule = _get_owned_schedule(db, schedule_id, user)
    jobs = (
        db.execute(
            select(Job)
            .where(Job.schedule_id == schedule.id)
            .order_by(Job.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [_run_dict(db, job) for job in jobs]


@router.post("/{schedule_id}/run", status_code=status.HTTP_201_CREATED)
def run_schedule_now(
    schedule_id: str,
    user: User = Depends(require_active_license),
    db: Session = Depends(get_app_db),
) -> dict:
    """Fires immediately, outside the cadence -- does not touch next_run_at,
    so the regular schedule keeps its own timing undisturbed."""
    schedule = _get_owned_schedule(db, schedule_id, user)
    template = db.get(JobTemplate, schedule.template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")

    job, targets = create_job_from_spec(
        db,
        user=user,
        keywords=list(template.keywords),
        locations=[LocationSpec(**loc) for loc in template.locations],
        source=template.source,
        name=schedule.name,
        schedule_id=schedule.id,
    )
    schedule.last_run_at = datetime.utcnow()
    schedule.last_result = "done"
    schedule.last_job_id = job.id
    db.commit()
    return _job_dict(job, targets)


@router.get("/preview")
def preview_cadence(
    cadence: str,
    timezone: str = Query("UTC"),
) -> dict:
    """Next 5 fire times for whatever the builder currently has selected --
    called on every cadence/timezone change so the preview stays live before
    Save is even clicked."""
    try:
        validate_cadence(cadence, timezone)
    except InvalidCadence as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    runs = next_n_runs(cadence, timezone, datetime.utcnow())
    return {"nextRuns": [r.isoformat() for r in runs]}


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: ScheduleRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    try:
        validate_cadence(payload.cadence, payload.timezone)
    except InvalidCadence as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    template = _get_owned_template(db, payload.template_id, user)

    schedule = Schedule(
        name=payload.name.strip(),
        template_id=template.id,
        owner_id=user.id,
        cadence=payload.cadence,
        timezone=payload.timezone,
        enabled=payload.enabled,
        next_run_at=next_run_after(payload.cadence, payload.timezone, datetime.utcnow())
        if payload.enabled
        else None,
    )
    db.add(schedule)
    db.commit()
    return _schedule_dict(schedule)


@router.patch("/{schedule_id}")
def update_schedule(
    schedule_id: str,
    payload: ScheduleUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    schedule = _get_owned_schedule(db, schedule_id, user)

    if payload.name is not None:
        schedule.name = payload.name.strip()

    cadence_changed = payload.cadence is not None or payload.timezone is not None
    if payload.cadence is not None:
        schedule.cadence = payload.cadence
    if payload.timezone is not None:
        schedule.timezone = payload.timezone
    if cadence_changed:
        try:
            validate_cadence(schedule.cadence, schedule.timezone)
        except InvalidCadence as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc

    if payload.enabled is not None:
        schedule.enabled = payload.enabled

    # Any change that could move the next fire time recomputes it; disabling
    # clears it so the dispatcher's `next_run_at <= now` scan skips the row
    # outright rather than relying on the `enabled` flag alone.
    if not schedule.enabled:
        schedule.next_run_at = None
    elif cadence_changed or payload.enabled is True:
        schedule.next_run_at = next_run_after(
            schedule.cadence, schedule.timezone, datetime.utcnow()
        )

    db.commit()
    return _schedule_dict(schedule)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> None:
    schedule = _get_owned_schedule(db, schedule_id, user)
    db.delete(schedule)
    db.commit()


def _get_owned_schedule(db: Session, schedule_id: str, user: User) -> Schedule:
    try:
        schedule_uuid = uuid.UUID(schedule_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid schedule id"
        ) from exc
    schedule = db.get(Schedule, schedule_uuid)
    if schedule is None or schedule.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="schedule not found")
    return schedule


def _get_owned_template(db: Session, template_id: str, user: User) -> JobTemplate:
    try:
        template_uuid = uuid.UUID(template_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid template id"
        ) from exc
    template = db.get(JobTemplate, template_uuid)
    if template is None or template.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")
    return template


def _schedule_dict(schedule: Schedule) -> dict:
    return {
        "id": str(schedule.id),
        "name": schedule.name,
        "templateId": str(schedule.template_id),
        "cadence": schedule.cadence,
        "timezone": schedule.timezone,
        "enabled": schedule.enabled,
        "nextRunAt": schedule.next_run_at.isoformat() if schedule.next_run_at else None,
        "lastRunAt": schedule.last_run_at.isoformat() if schedule.last_run_at else None,
        "lastResult": schedule.last_result,
        "lastJobId": str(schedule.last_job_id) if schedule.last_job_id else None,
    }


def _run_dict(db: Session, job: Job) -> dict:
    targets = db.execute(select(JobTarget).where(JobTarget.job_id == job.id)).scalars().all()
    places_found = sum(t.places_found for t in targets)
    results_count = (
        db.scalar(select(func.count()).select_from(Result).where(Result.job_id == job.id)) or 0
    )
    # A still-running job has no end time yet; duration is "so far", not final.
    duration_s = (job.updated_at - job.created_at).total_seconds()
    return {
        "jobId": str(job.id),
        "startedAt": job.created_at.isoformat(),
        "durationSeconds": max(0, round(duration_s)),
        "targetsTotal": len(targets),
        "placesFound": places_found,
        "resultsCount": results_count,
        "status": job.status,
    }
