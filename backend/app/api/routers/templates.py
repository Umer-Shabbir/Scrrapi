"""Job template endpoints: saved keyword/area/source combinations, run again
without re-filling the wizard.

GET    /api/templates       -> list templates owned by the current user
POST   /api/templates       -> save one (from the wizard's review step, or standalone)
PATCH  /api/templates/{id}  -> rename or replace its keywords/areas/source
DELETE /api/templates/{id}  -> remove it
POST   /api/templates/{id}/run -> create a real Job from the stored definition

Running shares `create_job_from_spec` with `POST /api/jobs` -- a template run
is exactly that function fed from a saved row instead of the request body, so
the target-limit check, dispatch, and job shape all stay in one place.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_app_db, get_current_user, require_active_license
from app.api.routers.jobs import SUPPORTED_SOURCES, LocationSpec, _job_dict, create_job_from_spec
from app.db.models.template import JobTemplate
from app.db.models.user import User

router = APIRouter()


class TemplateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=255)
    keywords: list[str] = Field(min_length=1)
    locations: list[LocationSpec | str] = Field(min_length=1)
    source: str = "google"


class TemplateUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    keywords: list[str] | None = None
    locations: list[LocationSpec | str] | None = None
    source: str | None = None


@router.get("/")
def list_templates(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> list[dict]:
    rows = (
        db.execute(
            select(JobTemplate)
            .where(JobTemplate.owner_id == user.id)
            .order_by(JobTemplate.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_template_dict(t) for t in rows]


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_template(
    payload: TemplateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    if payload.source not in SUPPORTED_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unsupported source: {payload.source!r}",
        )
    template = JobTemplate(
        name=payload.name.strip(),
        owner_id=user.id,
        source=payload.source,
        keywords=[k.strip() for k in payload.keywords if k.strip()],
        locations=[_location_dict(loc) for loc in payload.locations],
    )
    db.add(template)
    db.commit()
    return _template_dict(template)


@router.patch("/{template_id}")
def update_template(
    template_id: str,
    payload: TemplateUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    template = _get_owned_template(db, template_id, user)

    if payload.name is not None:
        template.name = payload.name.strip()
    if payload.source is not None:
        if payload.source not in SUPPORTED_SOURCES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"unsupported source: {payload.source!r}",
            )
        template.source = payload.source
    if payload.keywords is not None:
        template.keywords = [k.strip() for k in payload.keywords if k.strip()]
    if payload.locations is not None:
        template.locations = [_location_dict(loc) for loc in payload.locations]

    db.commit()
    return _template_dict(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> None:
    template = _get_owned_template(db, template_id, user)
    db.delete(template)
    db.commit()


@router.post("/{template_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_template(
    template_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    template = _get_owned_template(db, template_id, user)
    copy = JobTemplate(
        name=f"{template.name} (copy)",
        owner_id=user.id,
        source=template.source,
        keywords=list(template.keywords),
        locations=list(template.locations),
    )
    db.add(copy)
    db.commit()
    return _template_dict(copy)


@router.post("/{template_id}/run", status_code=status.HTTP_201_CREATED)
def run_template(
    template_id: str,
    user: User = Depends(require_active_license),
    db: Session = Depends(get_app_db),
) -> dict:
    template = _get_owned_template(db, template_id, user)
    locations = [LocationSpec(**loc) for loc in template.locations]

    job, targets = create_job_from_spec(
        db,
        user=user,
        keywords=list(template.keywords),
        locations=locations,
        source=template.source,
        name=template.name,
    )

    template.last_run_at = datetime.utcnow()
    db.commit()

    return _job_dict(job, targets)


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


def _location_dict(entry: LocationSpec | str) -> dict:
    spec = LocationSpec(label=entry) if isinstance(entry, str) else entry
    return spec.model_dump(by_alias=True)


def _template_dict(template: JobTemplate) -> dict:
    return {
        "id": str(template.id),
        "name": template.name,
        "source": template.source,
        "keywordCount": len(template.keywords),
        "areaCount": len(template.locations),
        "targetCount": len(template.keywords) * len(template.locations),
        "keywords": template.keywords,
        "locations": template.locations,
        "createdAt": template.created_at.isoformat(),
        "lastRunAt": template.last_run_at.isoformat() if template.last_run_at else None,
    }
