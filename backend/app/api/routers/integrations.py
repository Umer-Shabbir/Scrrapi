"""Integrations screen endpoints (SCREENLIST.md §14).

GET    /api/integrations                    -> Provider cards (state + last activity)
GET    /api/integrations/webhooks           -> Webhook config panel
PUT    /api/integrations/webhooks           -> Save webhook config
POST   /api/integrations/webhooks/rotate    -> Rotate signing secret
POST   /api/integrations/webhooks/test      -> Send a test webhook event

CRM OAuth2 and Sync Endpoints (HubSpot, GoHighLevel, Pipedrive):
GET    /api/integrations/{provider}/auth-url -> Get OAuth2 authorize URL
POST   /api/integrations/{provider}/callback -> Exchange OAuth2 authorization code
POST   /api/integrations/{provider}/sync     -> Direct contact sync with deduplication
DELETE /api/integrations/{provider}          -> Disconnect integration
"""

import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_app_db, get_current_user
from app.db.models.integration import CONFIGURABLE_PROVIDERS, INTEGRATION_PROVIDERS, IntegrationConnection
from app.db.models.user import User
from app.export.crm import CRMSyncError, get_crm_client

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


class OAuthCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None


class CRMSyncRequest(BaseModel):
    lead: Dict[str, Any]


def _get_connection(db: Session, provider: str) -> IntegrationConnection:
    conn = db.execute(
        select(IntegrationConnection).where(IntegrationConnection.provider == provider)
    ).scalar_one_or_none()
    if conn is None:
        if provider in INTEGRATION_PROVIDERS:
            # Auto-seed row if missing dynamically
            conn = IntegrationConnection(
                provider=provider,
                status="not_connected",
                config={},
                updated_at=datetime.utcnow(),
            )
            db.add(conn)
            db.commit()
            db.refresh(conn)
            return conn
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
        "signingSecretMasked": f"whsec_{'•' * 16}{secret[-4:]}" if secret else None,
        "lastEventAt": conn.last_event_at.isoformat() if conn.last_event_at else None,
        "lastEventSummary": conn.last_event_summary,
    }


@router.get("/")
def list_integrations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> list[dict]:
    # Ensure all registered providers have a connection record
    existing_conns = {
        c.provider: c
        for c in db.execute(select(IntegrationConnection)).scalars().all()
    }

    for prov in INTEGRATION_PROVIDERS:
        if prov not in existing_conns:
            new_conn = IntegrationConnection(
                provider=prov,
                status="not_connected",
                config={},
                updated_at=datetime.utcnow(),
            )
            db.add(new_conn)
            db.commit()
            db.refresh(new_conn)
            existing_conns[prov] = new_conn

    # Order properly
    ordered_conns = sorted(existing_conns.values(), key=lambda c: c.provider)
    return [_card_dict(c) for c in ordered_conns]


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


# =========================================================================
# CRM OAuth2 & Direct Sync endpoints (HubSpot, GoHighLevel, Pipedrive)
# =========================================================================

@router.get("/{provider}/auth-url")
def get_oauth_auth_url(
    provider: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """Generate the OAuth authorization URL for the provider."""
    if provider not in ("hubspot", "gohighlevel", "pipedrive"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"OAuth not supported for {provider}")

    state = secrets.token_urlsafe(16)

    # In mock/offline mode, return a client-side mock callback trigger
    auth_urls = {
        "hubspot": f"https://app.hubspot.com/oauth/authorize?client_id=mock_hs_client&scope=crm.objects.contacts.write&state={state}",
        "gohighlevel": f"https://marketplace.gohighlevel.com/oauth/chooselocation?client_id=mock_ghl_client&scope=contacts.write&state={state}",
        "pipedrive": f"https://oauth.pipedrive.com/oauth/authorize?client_id=mock_pd_client&state={state}",
    }

    return {
        "provider": provider,
        "authUrl": auth_urls.get(provider),
        "state": state,
        "isMock": True,
    }


@router.post("/{provider}/callback")
def handle_oauth_callback(
    provider: str,
    payload: OAuthCallbackRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """Exchange authorization code for access and refresh tokens."""
    if provider not in ("hubspot", "gohighlevel", "pipedrive"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"OAuth not supported for {provider}")

    conn = _get_connection(db, provider)

    # Mock token exchange
    mock_token = f"mock_{provider}_token_{secrets.token_hex(8)}"
    mock_refresh = f"mock_{provider}_refresh_{secrets.token_hex(16)}"

    config = dict(conn.config or {})
    config["access_token"] = mock_token
    config["refresh_token"] = mock_refresh
    config["connected_at"] = datetime.utcnow().isoformat()

    conn.config = config
    conn.status = "connected"
    conn.last_event_at = datetime.utcnow()
    conn.last_event_summary = f"OAuth connected ({provider})"
    conn.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(conn)
    return _card_dict(conn)


@router.delete("/{provider}")
def disconnect_integration(
    provider: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """Disconnect an integration and wipe its stored credentials."""
    conn = _get_connection(db, provider)
    conn.config = {}
    conn.status = "not_connected"
    conn.last_event_at = datetime.utcnow()
    conn.last_event_summary = f"Disconnected {provider}"
    conn.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conn)
    return _card_dict(conn)


@router.post("/{provider}/sync")
def sync_contact_to_crm(
    provider: str,
    payload: CRMSyncRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """Perform a direct contact sync to the specified CRM with automatic deduplication."""
    if provider not in ("hubspot", "gohighlevel", "pipedrive"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Sync not supported for {provider}")

    conn = _get_connection(db, provider)
    if conn.status != "connected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider.capitalize()} is not connected. Connect it first in Integrations.",
        )

    config = conn.config or {}
    token = config.get("access_token", "mock_default_token")

    try:
        client = get_crm_client(provider, token)
        result = client.sync_contact(payload.lead)

        # Record summary on connection card
        action_desc = "Deduplicated & Updated" if result.get("deduplicated") else "Created"
        conn.last_event_at = datetime.utcnow()
        conn.last_event_summary = f"Synced lead ({action_desc})"
        db.commit()

        return result
    except CRMSyncError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
