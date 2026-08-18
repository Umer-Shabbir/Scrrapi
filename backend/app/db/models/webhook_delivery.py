"""Webhook Delivery Log screen (SCREENLIST.md §15, drill-down from
Integrations at /integrations/webhooks/:id). Separate table from
`IntegrationConnection` (app.db.models.integration) on purpose: that model is
one row per provider card and owned by the Integrations screen cycle; this is
the per-attempt history and back-off/disable state that screen's own docstring
explicitly defers to "a separate screen" (Webhook Delivery Log).

Only the "webhooks" provider has deliveries -- every other provider card on
Integrations has no working config flow yet (no OAuth client, no Sheets
writer), so nothing sends them events to log.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AppBase

# Consecutive-failure thresholds from the Figma copy ("backing off" banner
# names the retry countdown; "auto-disabled" banner names the sustained-
# failure count). Both are evaluated off the same counter -- back-off is the
# warning state, disable is what happens if it keeps not recovering.
BACKOFF_THRESHOLD = 3
DISABLE_THRESHOLD = 12

# Exponential backoff base, minutes -- doubles per consecutive failure past
# BACKOFF_THRESHOLD, capped so "next retry in" never reads as absurd.
BACKOFF_BASE_MINUTES = 1
BACKOFF_CAP_MINUTES = 60


class WebhookDelivery(AppBase):
    """One delivery attempt (or retry of one) for the webhooks integration.

    `attempt`/`attempt_max` back the "3/3" ATTEMPT column -- a delivery that
    exhausted retries shows its final attempt number over the cap; one that
    succeeded on try 1 shows "1/1", not "1/3", since retries beyond a success
    never happened. Request/response snapshots are stored verbatim (not
    reconstructed) so the expandable row shows exactly what was sent/received,
    not a re-derived approximation.
    """

    __tablename__ = "webhook_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # FK to IntegrationConnection.id, not a hardcoded provider string -- lets
    # this table generalize if a second provider ever gets real deliveries,
    # without a schema change here.
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_connections.id"), index=True
    )
    event: Mapped[str] = mapped_column(String(60))
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # True only once this event's retries are exhausted or it succeeded --
    # what "2 failed in the last 24h" / REPLAY ALL FAILED actually counts.
    succeeded: Mapped[bool] = mapped_column(default=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    attempt_max: Mapped[int] = mapped_column(Integer, default=1)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_headers: Mapped[dict] = mapped_column(JSON, default=dict)
    request_body: Mapped[dict] = mapped_column(JSON, default=dict)
    # Null on a request that never got a response (timeout/connection error)
    # -- the expandable row shows "no response" rather than a fabricated body.
    response_body: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class WebhookEndpointState(AppBase):
    """Durable auto-disable flag, one row per connection.

    Back-off ("failed N consecutive, next retry in ...") is derived from the
    tail of `WebhookDelivery` on every read -- no state to go stale. Disable
    can't be: once disabled, deliveries stop happening at all, so there would
    be no new failing rows left to keep re-deriving "still disabled" from.
    This table exists for exactly that one bit, not as a duplicate of
    anything IntegrationConnection already owns.
    """

    __tablename__ = "webhook_endpoint_states"

    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_connections.id"), primary_key=True
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    disabled_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
