"""API Keys endpoints (SCREENLIST.md §17).

GET    /api/api-keys              -> list keys (prefix only, never the real key)
POST   /api/api-keys              -> create a key, returns the plaintext ONCE
DELETE /api/api-keys/{keyId}      -> revoke (soft -- keeps history, blocks auth)

Owner-only, same gate as Team & Roles' admin actions -- the role matrix
("Manage integrations and API keys") lists this as an Owner-only capability.

There is no route in this app that currently authenticates *with* one of
these keys (every router still only accepts the JWT session bearer token),
so `usage_daily`/`last_used_at` stay at their real starting values (zeros /
null) rather than being seeded with invented traffic. See app.db.models.api_key.
"""

import hashlib
import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_app_db, get_current_user
from app.core.audit import client_ip, log_audit_event
from app.db.models.api_key import SCOPES, ApiKey
from app.db.models.user import User

router = APIRouter()

KEY_PREFIX = "msk_live_"


class CreateKeyRequest(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(default_factory=list)
    ip_allowlist: str | None = Field(default=None, max_length=500)

    def validated_scopes(self) -> list[str]:
        bad = [s for s in self.scopes if s not in SCOPES]
        if bad:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"unknown scope(s): {', '.join(bad)}",
            )
        return self.scopes


def _require_owner(user: User = Depends(get_current_user)) -> User:
    """Only Owner may manage API keys (role matrix: 'Manage integrations and
    API keys' is Owner-only) -- same gate shape as app.api.routers.team."""
    if user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the workspace owner can manage API keys",
        )
    return user


def _key_dict(k: ApiKey) -> dict:
    return {
        "id": str(k.id),
        "label": k.label,
        "prefix": k.prefix,
        "scopes": k.scopes,
        "createdAt": k.created_at.isoformat(),
        "lastUsedAt": k.last_used_at.isoformat() if k.last_used_at else None,
        "expiresAt": k.expires_at.isoformat() if k.expires_at else None,
        "usageDaily": k.usage_daily,
    }


@router.get("/")
def list_keys(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    keys = (
        db.execute(
            select(ApiKey)
            .where(ApiKey.owner_id == user.id, ApiKey.revoked_at.is_(None))
            .order_by(ApiKey.created_at.desc())
        )
        .scalars()
        .all()
    )
    return {"keys": [_key_dict(k) for k in keys]}


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_key(
    request: Request,
    payload: CreateKeyRequest,
    user: User = Depends(_require_owner),
    db: Session = Depends(get_app_db),
) -> dict:
    scopes = payload.validated_scopes()
    raw_key = KEY_PREFIX + secrets.token_hex(16)
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    key = ApiKey(
        owner_id=user.id,
        label=payload.label,
        prefix=raw_key[: len(KEY_PREFIX) + 4],
        key_hash=key_hash,
        scopes=scopes,
        ip_allowlist=payload.ip_allowlist or None,
    )
    db.add(key)
    log_audit_event(
        db,
        actor_email=user.email,
        action="apikey.created",
        target=f'API key "{key.label}"',
        ip_address=client_ip(request),
    )
    db.commit()

    # The only place the plaintext key is ever returned -- never again after this.
    return {**_key_dict(key), "key": raw_key}


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_key(
    request: Request,
    key_id: str,
    user: User = Depends(_require_owner),
    db: Session = Depends(get_app_db),
) -> None:
    try:
        key_uuid = uuid.UUID(key_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid key id"
        ) from exc

    key = db.get(ApiKey, key_uuid)
    if key is None or key.owner_id != user.id or key.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="key not found")

    key.revoked_at = datetime.utcnow()
    log_audit_event(
        db,
        actor_email=user.email,
        action="apikey.revoked",
        target=f'API key "{key.label}"',
        ip_address=client_ip(request),
    )
    db.commit()
