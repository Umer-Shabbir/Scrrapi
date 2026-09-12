import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AppBase

# The 6 providers shown as cards on the Integrations screen (SCREENLIST.md
# §14). Only "webhooks" has a real config drill-down today -- Slack/HubSpot/
# Pipedrive/Generic REST need an OAuth handshake or API-key exchange this
# backend doesn't implement yet (no client credentials, no OAuth callback
# route, nothing in MODULES.md/ARCHITECTURE.md describing one), and Google
# Sheets has no writer (SCREENLIST.md §11: "XLSX/KML/JSONL/Sheets writers not
# implemented in backend yet"). Rows for all 6 are seeded so the card grid has
# real (if mostly "not_connected") data instead of hardcoded frontend copy.
INTEGRATION_PROVIDERS = ("webhooks", "slack", "hubspot", "pipedrive", "rest", "sheets", "gohighlevel")

# Providers whose CONNECT/CONFIGURE flow is actually implemented server-side.
# The other 4 stay "not_connected" forever until a real client integration is
# built -- the frontend disables their Connect button rather than pretending
# a click established a connection (CLAUDE.md §9: no fake backend data).
CONFIGURABLE_PROVIDERS = ("webhooks", "hubspot", "pipedrive", "gohighlevel")


class IntegrationConnection(AppBase):
    """One row per provider card on the Integrations screen. `config` holds
    provider-specific settings -- for webhooks: url, events, signing_secret.
    `last_event_at`/`last_event_summary` back the card's "Last delivery ... "
    caption; both stay null until a real delivery/sync happens.
    """

    __tablename__ = "integration_connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(20), unique=True)
    # connected | not_connected
    status: Mapped[str] = mapped_column(String(20), default="not_connected")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_event_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
