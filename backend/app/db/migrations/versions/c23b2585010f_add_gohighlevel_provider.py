"""add_gohighlevel_provider

Revision ID: c23b2585010f
Revises: 26520f75246a
Create Date: 2026-09-12 20:10:07.408581
"""
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = 'c23b2585010f'
down_revision = '26520f75246a'
branch_labels = None
depends_on = None

def upgrade() -> None:
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
                "provider": "gohighlevel",
                "status": "not_connected",
                "config": {},
                "updated_at": now,
            }
        ],
    )

def downgrade() -> None:
    op.execute("DELETE FROM integration_connections WHERE provider = 'gohighlevel'")
