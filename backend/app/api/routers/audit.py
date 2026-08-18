"""Audit Log endpoints (SCREENLIST.md §18).

GET /api/audit                    -> filtered/paginated event list
GET /api/audit/actors             -> distinct actor emails (backs the ACTOR filter)
GET /api/audit/action-types       -> distinct action values (backs the ACTION TYPE filter)
GET /api/audit/export.csv         -> same filters, as a CSV download

Read-only for every role -- the role matrix (Team & Roles) lists "View
billing and audit log" as Owner-only, same gate as api_keys/team.
"""

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_app_db, get_current_user
from app.db.models.audit_event import AuditEvent
from app.db.models.user import User

router = APIRouter()

PAGE_SIZE = 100


def _require_owner(user: User = Depends(get_current_user)) -> User:
    if user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the workspace owner can view the audit log",
        )
    return user


def _apply_filters(
    query, actor: str | None, action: str | None, date_from: str | None, date_to: str | None
):
    if actor:
        query = query.where(AuditEvent.actor_email == actor)
    if action:
        query = query.where(AuditEvent.action == action)
    if date_from:
        query = query.where(AuditEvent.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        # Inclusive of the whole "to" day, matching the date-only inputs the
        # Figma filter row shows (no time component).
        end = datetime.fromisoformat(date_to)
        query = query.where(AuditEvent.created_at < end.replace(hour=23, minute=59, second=59))
    return query


def _event_dict(e: AuditEvent) -> dict:
    return {
        "id": str(e.id),
        "timestamp": e.created_at.isoformat(),
        "actor": e.actor_email,
        "action": e.action,
        "target": e.target,
        "ip": e.ip_address,
        "success": e.success,
        "beforeAfter": e.before_after,
    }


@router.get("/")
def list_events(
    actor: str | None = Query(default=None),
    action: str | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    _user: User = Depends(_require_owner),
    db: Session = Depends(get_app_db),
) -> dict:
    query = _apply_filters(select(AuditEvent), actor, action, date_from, date_to)
    rows = db.execute(query.order_by(AuditEvent.created_at.desc()).limit(PAGE_SIZE)).scalars().all()
    return {"events": [_event_dict(e) for e in rows]}


@router.get("/actors")
def list_actors(
    _user: User = Depends(_require_owner),
    db: Session = Depends(get_app_db),
) -> dict:
    rows = db.execute(
        select(AuditEvent.actor_email).where(AuditEvent.actor_email.is_not(None)).distinct()
    ).scalars().all()
    return {"actors": sorted(rows)}


@router.get("/action-types")
def list_action_types(
    _user: User = Depends(_require_owner),
    db: Session = Depends(get_app_db),
) -> dict:
    rows = db.execute(select(AuditEvent.action).distinct()).scalars().all()
    return {"actionTypes": sorted(rows)}


@router.get("/export.csv")
def export_csv(
    actor: str | None = Query(default=None),
    action: str | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    _user: User = Depends(_require_owner),
    db: Session = Depends(get_app_db),
) -> StreamingResponse:
    query = _apply_filters(select(AuditEvent), actor, action, date_from, date_to)
    rows = db.execute(query.order_by(AuditEvent.created_at.desc())).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["timestamp", "actor", "action", "target", "ip", "result"])
    for e in rows:
        writer.writerow([
            e.created_at.isoformat(),
            e.actor_email or "",
            e.action,
            e.target or "",
            e.ip_address or "",
            "SUCCESS" if e.success else "FAILED",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit-log.csv"},
    )
