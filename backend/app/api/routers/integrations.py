"""Integrations screen endpoints (SCREENLIST.md §14).

GET    /api/integrations                    -> 6 provider cards (state + last activity)
GET    /api/integrations/webhooks           -> webhook config panel (SCREENLIST.md §14 drill-down)
PUT    /api/integrations/webhooks           -> save endpoint URL + subscribed events
POST   /api/integrations/webhooks/rotate    -> rotate signing secret (shown once in full after)
POST   /api/integrations/webhooks/test      -> send a test event, records it as the "last delivery"

Only "webhooks" has a real config flow -- see app.db.models.integration for
why Slack/HubSpot/Pipedrive/Generic REST/Google Sheets don't (no OAuth
client, no API credentials, no writer for Sheets). Their cards are real rows
(always `not_connected`) rather than hardcoded frontend copy; their CONNECT
button has nothing to call yet, so the frontend disables it instead of
pretending a click connects something.
"""

import secrets
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_app_db, get_current_user
from app.db.models.integration import CONFIGURABLE_PROVIDERS, IntegrationConnection
from app.db.models.user import User

router = APIRouter()

WEBHOOK_EVENTS = (
    "job.started",
    "job.completed",
    "job.failed",
    "lead.found",
    "suppression.triggered",
)


class WebhookConfigRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    events: list[str] = Field(default_factory=list)


def _get_connection(db: Session, provider: str) -> IntegrationConnection:
    conn = db.execute(
        select(IntegrationConnection).where(IntegrationConnection.provider == provider)
    ).scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown provider")
    return conn


def _require_https(url: str) -> None:
    if not url.lower().startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Endpoint URL must be HTTPS",
        )


def _card_dict(conn: IntegrationConnection) -> dict:
    return {
        "provider": conn.provider,
        "status": conn.status,
        "configurable": conn.provider in CONFIGURABLE_PROVIDERS,
        "lastEventAt": conn.last_event_at.isoformat() if conn.last_event_at else None,
        "lastEventSummary": conn.last_event_summary,
    }


def _webhook_dict(conn: IntegrationConnection) -> dict:
    config = conn.config or {}
    secret = config.get("signing_secret")
    return {
        "provider": conn.provider,
        "status": conn.status,
        "url": config.get("url"),
        "events": config.get("events", []),
        "availableEvents": list(WEBHOOK_EVENTS),
        # Never re-send the full secret after creation/rotation -- only a
        # masked tail, matching the "shown in full only once" panel copy.
        "signingSecretMasked": f"whsec_{'•' * 16}{secret[-4:]}" if secret else None,
        "lastEventAt": conn.last_event_at.isoformat() if conn.last_event_at else None,
        "lastEventSummary": conn.last_event_summary,
    }


@router.get("/")
def list_integrations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> list[dict]:
    conns = (
        db.execute(select(IntegrationConnection).order_by(IntegrationConnection.provider))
        .scalars()
        .all()
    )
    return [_card_dict(c) for c in conns]


@router.get("/webhooks")
def get_webhook_config(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    return _webhook_dict(_get_connection(db, "webhooks"))


@router.put("/webhooks")
def save_webhook_config(
    payload: WebhookConfigRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    _require_https(payload.url)
    unknown = set(payload.events) - set(WEBHOOK_EVENTS)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown event(s): {', '.join(sorted(unknown))}",
        )

    conn = _get_connection(db, "webhooks")
    config = dict(conn.config or {})
    config["url"] = payload.url
    config["events"] = payload.events
    if not config.get("signing_secret"):
        config["signing_secret"] = secrets.token_hex(20)
    conn.config = config
    conn.status = "connected"
    conn.updated_at = datetime.utcnow()
    db.commit()
    return _webhook_dict(conn)


@router.post("/webhooks/rotate")
def rotate_webhook_secret(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    conn = _get_connection(db, "webhooks")
    config = dict(conn.config or {})
    config["signing_secret"] = secrets.token_hex(20)
    conn.config = config
    conn.updated_at = datetime.utcnow()
    db.commit()
    # Full secret returned once, here only -- never included in GET responses.
    return {**_webhook_dict(conn), "signingSecret": config["signing_secret"]}


@router.post("/webhooks/test")
def send_webhook_test_event(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    conn = _get_connection(db, "webhooks")
    config = conn.config or {}
    if not config.get("url"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Set an endpoint URL before sending a test event",
        )
    # "Send test event" promises one real delivery attempt, not a queue/retry
    # pipeline (that belongs to Webhook Delivery Log, a separate screen --
    # CLAUDE.md §5: build only what this screen genuinely needs). So this
    # performs one synchronous POST and records the real outcome.
    try:
        response = httpx.post(
            config["url"],
            json={"event": "test", "sent_at": datetime.utcnow().isoformat()},
            timeout=5.0,
        )
        summary = f"test event · {response.status_code}"
    except httpx.HTTPError as exc:
        summary = f"test event failed · {exc.__class__.__name__}"

    conn.last_event_at = datetime.utcnow()
    conn.last_event_summary = summary
    db.commit()
    return _webhook_dict(conn)
