"""add integration_connections

Revision ID: f4b7d2c891a3
Revises: e91c4a6d0f57
Create Date: 2026-08-12 00:00:00.000000

Backs the Integrations screen (SCREENLIST.md §14) -- genuinely missing
before this, there was no model/router for third-party integrations at all.

One row per provider card (webhooks/slack/hubspot/pipedrive/rest/sheets),
seeded here so the card grid always has real rows instead of the frontend
hardcoding provider names. Only "webhooks" has a working CONNECT/CONFIGURE
flow server-side today -- see app.db.models.integration for why the other 4
stay `not_connected` until a real OAuth/API-key integration is built.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "f4b7d2c891a3"
down_revision = "e91c4a6d0f57"
branch_labels = None
depends_on = None

PROVIDERS = ("webhooks", "slack", "hubspot", "pipedrive", "rest", "sheets")


def upgrade() -> None:
    op.create_table(
        "integration_connections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="not_connected"),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("last_event_at", sa.DateTime(), nullable=True),
        sa.Column("last_event_summary", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_integration_connections_provider", "integration_connections", ["provider"]
    )

    connections = sa.table(
        "integration_connections",
        sa.column("id", sa.Uuid()),
        sa.column("provider", sa.String()),
        sa.column("status", sa.String()),
        sa.column("config", sa.JSON()),
        sa.column("updated_at", sa.DateTime()),
    )
    now = datetime.utcnow()
    op.bulk_insert(
        connections,
        [
            {
                "id": uuid.uuid4(),
                "provider": provider,
                "status": "not_connected",
                "config": {},
                "updated_at": now,
            }
            for provider in PROVIDERS
        ],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_integration_connections_provider", "integration_connections", type_="unique"
    )
    op.drop_table("integration_connections")
