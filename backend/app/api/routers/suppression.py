"""Suppression List endpoints: global (install-wide, like Settings -- one
scrape fleet, one list) domain/email/place block rules.

GET    /api/suppression                 -> list rules, one kind at a time
GET    /api/suppression/preview         -> row count a proposed rule would remove, before it's added
POST   /api/suppression                 -> add a rule; deletes every currently-matching row
POST   /api/suppression/bulk            -> add many rules of one kind at once (paste/CSV upload)
DELETE /api/suppression/{id}            -> remove a rule (does not restore already-deleted rows)

Every write is real and, for POST /, irreversible -- see docs on
app.scraping.common.suppression and app.db.models.suppression.SuppressionEntry
for why matching is exact rather than substring/subdomain.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_app_db, get_current_user
from app.core.audit import client_ip, log_audit_event
from app.db.models.result import Result, ResultHistory
from app.db.models.suppression import SUPPRESSION_KINDS, SuppressionEntry
from app.db.models.user import User
from app.scraping.common.suppression import (
    normalize_domain,
    normalize_email,
    result_is_suppressed,
)

router = APIRouter()

# How many candidate rows a single preview/delete will inspect in Python
# after the cheap SQL pre-filter narrows the table down. A rule matching more
# than this is almost certainly a mistake (e.g. suppressing a bare TLD) --
# better to surface that as a very large, capped number than to silently scan
# the whole results table on every keystroke of the Add Entry Bar.
MATCH_SCAN_CAP = 50_000


class CreateSuppressionRequest(BaseModel):
    kind: str = Field(pattern="^(domain|email|place)$")
    value: str = Field(min_length=1, max_length=255)
    reason: str | None = Field(default=None, max_length=500)


class BulkSuppressionRequest(BaseModel):
    kind: str = Field(pattern="^(domain|email|place)$")
    values: list[str] = Field(min_length=1, max_length=5000)
    reason: str | None = Field(default=None, max_length=500)


def _normalize(kind: str, value: str) -> str:
    if kind == "domain":
        return normalize_domain(value)
    if kind == "email":
        return normalize_email(value)
    return value.strip()  # place: place_key is already a normalized hash


def _candidate_query(kind: str, value: str):
    """SQL pre-filter only -- narrows the table with a cheap LIKE/equality
    check, never the final word on a match. `result_is_suppressed` (exact,
    tested in tests/test_suppression_matching.py) is what actually decides,
    applied to this bounded candidate set in Python. This two-step shape
    exists because `Result.website` is stored as a full URL (scheme, optional
    `www.`), which a single SQL equality can't reliably normalize without
    duplicating URL-parsing logic in SQL -- see suppression.py's module
    docstring on why blast radius has to be exact, not approximate.
    """
    if kind == "domain":
        return select(Result).where(
            or_(Result.website.ilike(f"%{value}"), Result.website.ilike(f"%{value}/%"))
        )
    if kind == "email":
        return select(Result).where(Result.email.ilike(f"%{value}%"))
    return select(Result).where(Result.place_key == value)


def _matching_results(db: Session, kind: str, value: str) -> list[Result]:
    candidates = db.execute(_candidate_query(kind, value).limit(MATCH_SCAN_CAP)).scalars().all()
    entry = [(kind, value)]
    return [r for r in candidates if result_is_suppressed(r, entry)]


@router.get("/preview")
def preview_suppression(
    kind: str = Query(pattern="^(domain|email|place)$"),
    value: str = Query(min_length=1, max_length=255),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """Row count a rule would remove, computed before the user opens the
    confirm modal (SCREENLIST.md §12 bug: the count must be visible earlier,
    not only inside the modal)."""
    normalized = _normalize(kind, value)
    if not normalized:
        return {"rowCount": 0}
    matches = _matching_results(db, kind, normalized)
    return {"rowCount": len(matches)}


@router.get("/")
def list_suppression(
    kind: str = Query(pattern="^(domain|email|place)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> list[dict]:
    entries = db.execute(
        select(SuppressionEntry)
        .where(SuppressionEntry.kind == kind)
        .order_by(SuppressionEntry.created_at.desc())
    ).scalars().all()
    return [_entry_dict(db, e) for e in entries]


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_suppression(
    request: Request,
    payload: CreateSuppressionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    normalized = _normalize(payload.kind, payload.value)
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="empty value")

    existing = db.execute(
        select(SuppressionEntry).where(
            SuppressionEntry.kind == payload.kind, SuppressionEntry.value == normalized
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already suppressed")

    entry = SuppressionEntry(
        kind=payload.kind, value=normalized, reason=payload.reason, created_by=user.id
    )
    db.add(entry)

    removed = _delete_matches(db, payload.kind, normalized)
    log_audit_event(
        db, actor_email=user.email, action="suppression.created",
        target=f"{payload.kind}:{normalized}", ip_address=client_ip(request),
    )
    db.commit()

    return {**_entry_dict(db, entry), "rowsRemoved": removed}


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def bulk_create_suppression(
    request: Request,
    payload: BulkSuppressionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """Add-one and bulk-paste/upload share this: the Add Entry Bar's single
    field is just a bulk request with one value. Values already suppressed
    are skipped rather than 409ing the whole batch -- a pasted list of 500
    domains that happens to include 3 already on the list shouldn't fail all
    500."""
    created = 0
    skipped = 0
    total_removed = 0

    existing_values = {
        v for (v,) in db.execute(
            select(SuppressionEntry.value).where(SuppressionEntry.kind == payload.kind)
        ).all()
    }

    for raw in payload.values:
        normalized = _normalize(payload.kind, raw)
        if not normalized or normalized in existing_values:
            skipped += 1
            continue
        existing_values.add(normalized)
        entry = SuppressionEntry(
            kind=payload.kind, value=normalized, reason=payload.reason, created_by=user.id
        )
        db.add(entry)
        total_removed += _delete_matches(db, payload.kind, normalized)
        created += 1

    log_audit_event(
        db, actor_email=user.email, action="suppression.bulk_created",
        target=f"{payload.kind} ({created} added, {skipped} skipped)",
        ip_address=client_ip(request),
    )
    db.commit()
    return {"created": created, "skipped": skipped, "rowsRemoved": total_removed}


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_suppression(
    request: Request,
    entry_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> None:
    """Removes the rule going forward. Rows already deleted when the rule was
    added are gone -- this does not restore them, and nothing in this system
    could (the delete didn't soft-delete, per the confirm modal's own
    wording: "This removes ... stored rows")."""
    try:
        entry_uuid = uuid.UUID(entry_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid entry id"
        ) from exc

    entry = db.get(SuppressionEntry, entry_uuid)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="entry not found")

    log_audit_event(
        db, actor_email=user.email, action="suppression.removed",
        target=f"{entry.kind}:{entry.value}", ip_address=client_ip(request),
    )
    db.delete(entry)
    db.commit()


def _delete_matches(db: Session, kind: str, value: str) -> int:
    matches = _matching_results(db, kind, value)
    if not matches:
        return 0
    ids = [m.id for m in matches]
    # result_history FKs onto results.id -- clear it first or this raises
    # ForeignKeyViolation on result_history_result_id_fkey for any matched
    # result that had a tracked-field change recorded against it.
    db.execute(delete(ResultHistory).where(ResultHistory.result_id.in_(ids)))
    db.execute(delete(Result).where(Result.id.in_(ids)))
    return len(ids)


def _entry_dict(db: Session, entry: SuppressionEntry) -> dict:
    # Live count, not stored: a rule's match count can only grow if new data
    # arrives, since matching results are deleted the moment a rule exists --
    # so this is really "how many rows have snuck past enforcement", which
    # should be 0 in steady state and is worth surfacing if it's not.
    current_matches = len(_matching_results(db, entry.kind, entry.value))
    creator = db.get(User, entry.created_by)
    return {
        "id": str(entry.id),
        "kind": entry.kind,
        "value": entry.value,
        "reason": entry.reason,
        "createdBy": creator.email if creator else "unknown",
        "createdAt": entry.created_at.isoformat(),
        "rowCount": current_matches,
    }
