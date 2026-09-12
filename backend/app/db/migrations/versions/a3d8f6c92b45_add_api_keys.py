"""add api_keys

Revision ID: a3d8f6c92b45
Revises: d2f6a94c7b18
Create Date: 2026-08-13 00:00:00.000000

Backs the API Keys screen (SCREENLIST.md §17) -- genuinely missing before
this, there was no model/router for programmatic access at all.

`usage_daily` starts as 30 zeros for every key: no route in this app
authenticates with an API key yet (every router still only checks the JWT
session token), so there is no real traffic to backfill -- see the model's
docstring. The sparkline will start reflecting real numbers only once that
auth path is wired up, which is out of scope for this screen.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""

import sqlalchemy as sa
from alembic import op

revision = "a3d8f6c92b45"
down_revision = "d2f6a94c7b18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("prefix", sa.String(length=20), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("ip_allowlist", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("usage_daily", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_api_keys_owner_id"), "api_keys", ["owner_id"], unique=False)
    op.create_index(op.f("ix_api_keys_key_hash"), "api_keys", ["key_hash"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_api_keys_key_hash"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_owner_id"), table_name="api_keys")
    op.drop_table("api_keys")
