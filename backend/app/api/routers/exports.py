"""Export endpoints: trigger CSV/XLSX/KML/JSONL/Sheets generation for a completed
job, poll status, download the result, list/delete history.

POST   /api/exports                -> create an Export row, enqueue export_job Celery task
GET    /api/exports                -> export history for a job (Export History table)
GET    /api/exports/{id}            -> status + download URL once file_path/external_url is set
GET    /api/exports/{id}/download   -> stream the generated file, or redirect to the
                                        Sheets URL for format "sheets" (no local file)
DELETE /api/exports/{id}            -> remove the row and its on-disk file, if any
"""

import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_app_db, get_current_user
from app.db.models.export import COLUMN_GROUPS, ROW_SCOPES, Export
from app.db.models.job import Job
from app.db.models.user import User
from app.workers.tasks import export_job

router = APIRouter()


class CreateExportRequest(BaseModel):
    job_id: str
    format: str = Field(pattern="^(csv|xlsx|kml|jsonl|sheets)$")
    # None means every column -- the behavior every export had before the
    # Column Selection panel existed. Validated against COLUMN_GROUPS' keys
    # rather than an inline pattern since the group list lives on the model.
    columns: list[str] | None = None
    # Only "all" does anything (see Export.row_scope's comment); anything else
    # the client sends is accepted but stored as "all" rather than 422ing a
    # screen still finishing its Current filter/selection wiring.
    row_scope: str = "all"


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_export(
    payload: CreateExportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    job = _get_owned_job(db, payload.job_id, user)

    if payload.columns:
        unknown = [g for g in payload.columns if g not in COLUMN_GROUPS]
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"unknown column group(s): {', '.join(unknown)}",
            )

    export = Export(
        job_id=job.id,
        format=payload.format,
        status="pending",
        columns=",".join(payload.columns) if payload.columns else None,
        row_scope=payload.row_scope if payload.row_scope in ROW_SCOPES else "all",
    )
    db.add(export)
    db.commit()

    export_job.delay(str(export.id))

    return _export_dict(export)


@router.get("/")
def list_exports(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> list[dict]:
    job = _get_owned_job(db, job_id, user)
    exports = (
        db.execute(
            select(Export)
            .where(Export.job_id == job.id)
            .order_by(Export.generated_at.desc().nulls_first())
        )
        .scalars()
        .all()
    )
    return [_export_dict(export) for export in exports]


@router.get("/{export_id}")
def get_export(
    export_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    export = _get_owned_export(db, export_id, user)
    return _export_dict(export)


@router.get("/{export_id}/download", response_model=None)
def download_export(
    export_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> FileResponse | RedirectResponse:
    export = _get_owned_export(db, export_id, user)
    if export.status != "done":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export not ready")
    # "sheets" has no local file -- send the browser straight to the
    # spreadsheet instead of trying to stream something that doesn't exist.
    if export.format == "sheets":
        if not export.external_url:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export not ready")
        return RedirectResponse(export.external_url)
    if not export.file_path or not os.path.exists(export.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export not ready")
    return FileResponse(export.file_path, filename=os.path.basename(export.file_path))


@router.delete("/{export_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_export(
    export_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> None:
    export = _get_owned_export(db, export_id, user)
    if export.file_path and os.path.exists(export.file_path):
        os.remove(export.file_path)
    db.delete(export)
    db.commit()


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


def _get_owned_export(db: Session, export_id: str, user: User) -> Export:
    try:
        export_uuid = uuid.UUID(export_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid export id"
        ) from exc

    export = db.get(Export, export_uuid)
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export not found")

    job = db.get(Job, export.job_id)
    if job is None or job.created_by != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export not found")
    return export


def _export_dict(export: Export) -> dict:
    data = {
        "id": str(export.id),
        "jobId": str(export.job_id),
        "format": export.format,
        "status": export.status,
        "columns": export.columns.split(",") if export.columns else None,
        "rowScope": export.row_scope,
        "rowCount": export.row_count,
        "sizeBytes": export.size_bytes,
    }
    # A purged file clears file_path but keeps the row (see
    # workers.tasks.purge_expired_exports) -- "not ready" either way, whether
    # that's because it never finished or because it expired. "sheets" has no
    # file_path at all (see Export.external_url), so it gates on that instead.
    has_output = export.external_url if export.format == "sheets" else export.file_path
    if has_output and export.status == "done":
        data["downloadUrl"] = f"/api/exports/{export.id}/download"
    if export.generated_at:
        data["generatedAt"] = export.generated_at.isoformat()
    if export.expires_at:
        data["expiresAt"] = export.expires_at.isoformat()
        data["expired"] = export.expires_at <= datetime.utcnow()
    return data
