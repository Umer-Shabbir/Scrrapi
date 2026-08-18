"""add jobs.updated_at

Revision ID: c1d8e4a7f302
Revises: a2e6c9f0b1d4
Create Date: 2026-08-11 00:00:00.000001

Backs the dashboard activity feed's "started"/"finished" timestamps, derived
from job status transitions since there is no separate event-log table.
Backfilled to `created_at` so existing rows get a sane (if approximate) value
instead of NULL.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""
import sqlalchemy as sa
from alembic import op

revision = 'c1d8e4a7f302'
down_revision = 'a2e6c9f0b1d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.execute("UPDATE jobs SET updated_at = created_at")
    op.alter_column('jobs', 'updated_at', nullable=False)


def downgrade() -> None:
    op.drop_column('jobs', 'updated_at')
