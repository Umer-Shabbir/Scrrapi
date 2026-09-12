"""add compliance_ack_at to users

Revision ID: 881f9cbe6b82
Revises: b7e94a1c53d8
Create Date: 2026-08-13 00:00:00.000000

Backs the First-run / Compliance (Onboarding) screen (SCREENLIST.md §22) --
genuinely missing before this, nothing tracked whether a user had completed
the 3-pane compliance flow. Nullable timestamp rather than a boolean: NULL
means "never acknowledged" (shows the modal), a real value is both the fact
and the "when" for free, and needs no separate audit-table lookup on every
authenticated page load (the audit log still gets its own row per step for
the legal record -- this column is the fast read path, not a replacement).

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""

import sqlalchemy as sa
from alembic import op

revision = "881f9cbe6b82"
down_revision = "b7e94a1c53d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("compliance_ack_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "compliance_ack_at")
