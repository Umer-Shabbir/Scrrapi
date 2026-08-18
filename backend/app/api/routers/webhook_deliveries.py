"""Webhook Delivery Log endpoints (SCREENLIST.md §15, drill-down from
Integrations at /integrations/webhooks/:id).

GET  /api/webhook-deliveries/{connection_id}          -> log + endpoint state
POST /api/webhook-deliveries/{connection_id}/replay/{delivery_id} -> retry one
POST /api/webhook-deliveries/{connection_id}/replay-failed         -> retry every recent failure
POST /api/webhook-deliveries/{connection_id}/re-enable             -> clear auto-disable

Mounted separately from app.api.routers.integrations (that router owns the
provider-card/config-panel screen cycle; this one owns the delivery-history
screen cycle -- see webhook_delivery.py's model docstring for why they're
split). Both read the same `IntegrationConnection` row, neither writes to the
other's tables.
"""

import time
import uuid
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_app_db, get_current_user
from app.db.models.integration import IntegrationConnection
from app.db.models.user import User
from app.db.models.webhook_delivery import (
    BACKOFF_BASE_MINUTES,
    BACKOFF_CAP_MINUTES,
    BACKOFF_THRESHOLD,
    DISABLE_THRESHOLD,
    WebhookDelivery,
    WebhookEndpointState,
)

router = APIRouter()

# How far back "N failed in the last 24h" looks, and how many rows Replay All
# Failed will actually retry in one call -- unbounded would mean one request
# firing thousands of outbound POSTs for a long-dead endpoint.
RECENT_WINDOW = timedelta(hours=24)
REPLAY_ALL_LIMIT = 50


def _get_connection(db: Session, connection_id: str) -> IntegrationConnection:
    """Accepts either the connection's real UUID or the literal provider slug
    "webhooks" -- there is exactly one webhooks connection per install today
    (IntegrationConnection has a unique constraint on `provider`), and the
    frontend's config panel doesn't expose the row's raw id, so its "view
    delivery log" link can only build a URL from what it already has: the
    provider name. Resolving either form here avoids a cross-cutting change
    to that panel's own response shape for one link's sake.
    """
    if connection_id == "webhooks":
        conn = db.execute(
            select(IntegrationConnection).where(IntegrationConnection.provider == "webhooks")
        ).scalar_one_or_none()
    else:
        try:
            conn_uuid = uuid.UUID(connection_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid connection id"
            ) from exc
        conn = db.get(IntegrationConnection, conn_uuid)

    if conn is None or conn.provider != "webhooks":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="webhook not found")
    return conn


def _get_state(db: Session, connection_id) -> WebhookEndpointState | None:
    return db.get(WebhookEndpointState, connection_id)


def _consecutive_failures(db: Session, connection_id) -> int:
    """How many of the most recent deliveries, read newest-first, failed in a
    row. Stops counting at the first success -- a back-off/disable streak is
    about what's happening *now*, not a lifetime failure count."""
    recent = db.execute(
        select(WebhookDelivery.succeeded)
        .where(WebhookDelivery.connection_id == connection_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(DISABLE_THRESHOLD + 1)
    ).scalars().all()
    count = 0
    for succeeded in recent:
        if succeeded:
            break
        count += 1
    return count


def _backoff_seconds(consecutive: int) -> int:
    """Exponential from BACKOFF_THRESHOLD, capped -- matches the model
    docstring's note on why this is a formula, not a stored countdown."""
    exponent = max(0, consecutive - BACKOFF_THRESHOLD)
    minutes = min(BACKOFF_CAP_MINUTES, BACKOFF_BASE_MINUTES * (2**exponent))
    return minutes * 60


def _endpoint_status(db: Session, conn: IntegrationConnection) -> dict:
    state = _get_state(db, conn.id)
    if state and state.disabled_at:
        return {
            "kind": "disabled",
            "disabledAt": state.disabled_at.isoformat(),
            "reason": state.disabled_reason,
        }

    consecutive = _consecutive_failures(db, conn.id)
    if consecutive >= BACKOFF_THRESHOLD:
        return {
            "kind": "backing_off",
            "consecutiveFailures": consecutive,
            "nextRetrySeconds": _backoff_seconds(consecutive),
        }
    return {"kind": "all_delivering"}


def _delivery_dict(d: WebhookDelivery) -> dict:
    return {
        "id": str(d.id),
        "event": d.event,
        "statusCode": d.status_code,
        "succeeded": d.succeeded,
        "attempt": d.attempt,
        "attemptMax": d.attempt_max,
        "durationMs": d.duration_ms,
        "requestHeaders": d.request_headers,
        "requestBody": d.request_body,
        "responseBody": d.response_body,
        "error": d.error,
        "createdAt": d.created_at.isoformat(),
    }


@router.get("/{connection_id}")
def get_delivery_log(
    connection_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    conn = _get_connection(db, connection_id)
    deliveries = db.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.connection_id == conn.id)
        .order_by(WebhookDelivery.created_at.desc())
    ).scalars().all()

    since = datetime.utcnow() - RECENT_WINDOW
    failed_recent = sum(
        1 for d in deliveries if not d.succeeded and d.created_at >= since
    )

    config = conn.config or {}
    return {
        "connectionId": str(conn.id),
        "url": config.get("url"),
        "endpointStatus": _endpoint_status(db, conn),
        "failedLast24h": failed_recent,
        "deliveries": [_delivery_dict(d) for d in deliveries],
    }


def _send(url: str, event: str, payload: dict) -> tuple[int | None, dict | None, str | None, int]:
    """One synchronous delivery attempt. Same shape as integrations.py's
    send_webhook_test_event -- a real POST, real outcome, no simulated result."""
    started = time.monotonic()
    try:
        response = httpx.post(url, json=payload, timeout=5.0)
        duration_ms = round((time.monotonic() - started) * 1000)
        body: dict | None
        try:
            body = response.json()
        except ValueError:
            body = None
        return response.status_code, body, None, duration_ms
    except httpx.HTTPError as exc:
        duration_ms = round((time.monotonic() - started) * 1000)
        return None, None, exc.__class__.__name__, duration_ms


def _replay_one(
    db: Session, conn: IntegrationConnection, original: WebhookDelivery
) -> WebhookDelivery:
    config = conn.config or {}
    url = config.get("url")
    if not url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This webhook has no endpoint URL configured",
        )

    status_code, response_body, error, duration_ms = _send(
        url, original.event, original.request_body
    )
    succeeded = status_code is not None and 200 <= status_code < 300

    retry = WebhookDelivery(
        connection_id=conn.id,
        event=original.event,
        status_code=status_code,
        succeeded=succeeded,
        attempt=original.attempt_max + 1,
        attempt_max=original.attempt_max + 1,
        duration_ms=duration_ms,
        request_headers=original.request_headers,
        request_body=original.request_body,
        response_body=response_body,
        error=error,
        created_at=datetime.utcnow(),
    )
    db.add(retry)
    db.flush()  # retry needs an id + committed created_at ordering before recounting the tail

    if succeeded:
        # A successful replay is the one thing that clears both back-off
        # (derived, clears itself once this row is the new tail) and a
        # standing disable.
        state = _get_state(db, conn.id)
        if state and state.disabled_at:
            state.disabled_at = None
            state.disabled_reason = None
    else:
        consecutive = _consecutive_failures(db, conn.id)
        if consecutive >= DISABLE_THRESHOLD:
            state = _get_state(db, conn.id)
            if state is None:
                state = WebhookEndpointState(connection_id=conn.id)
                db.add(state)
            if not state.disabled_at:
                state.disabled_at = datetime.utcnow()
                state.disabled_reason = f"{consecutive} consecutive delivery failures"

    db.commit()
    return retry


@router.post("/{connection_id}/replay/{delivery_id}")
def replay_delivery(
    connection_id: str,
    delivery_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    conn = _get_connection(db, connection_id)
    try:
        delivery_uuid = uuid.UUID(delivery_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid delivery id"
        ) from exc

    original = db.get(WebhookDelivery, delivery_uuid)
    if original is None or original.connection_id != conn.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="delivery not found")

    # Bug fix (SCREENLIST §15): the Figma disabled frame leaves individual row
    # REPLAY links active while only the toolbar action greys out --
    # inconsistent disabled treatment for the same action in two places.
    # Blocking it here, not just in the frontend, means the rule holds even
    # if something calls this endpoint directly.
    state = _get_state(db, conn.id)
    if state and state.disabled_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This webhook is disabled -- re-enable it before replaying",
        )

    retry = _replay_one(db, conn, original)
    return _delivery_dict(retry)


@router.post("/{connection_id}/replay-failed")
def replay_all_failed(
    connection_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    conn = _get_connection(db, connection_id)
    state = _get_state(db, conn.id)
    if state and state.disabled_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This webhook is disabled -- re-enable it before replaying",
        )

    since = datetime.utcnow() - RECENT_WINDOW
    failed = db.execute(
        select(WebhookDelivery)
        .where(
            WebhookDelivery.connection_id == conn.id,
            WebhookDelivery.succeeded.is_(False),
            WebhookDelivery.created_at >= since,
        )
        .order_by(WebhookDelivery.created_at.desc())
        .limit(REPLAY_ALL_LIMIT)
    ).scalars().all()

    retried = [_replay_one(db, conn, d) for d in failed]
    return {
        "replayed": len(retried),
        "succeeded": sum(1 for r in retried if r.succeeded),
        "deliveries": [_delivery_dict(r) for r in retried],
    }


@router.post("/{connection_id}/re-enable")
def re_enable_webhook(
    connection_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    conn = _get_connection(db, connection_id)
    state = _get_state(db, conn.id)
    if state is None or not state.disabled_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This webhook is not disabled"
        )
    state.disabled_at = None
    state.disabled_reason = None
    db.commit()
    return _endpoint_status(db, conn)
