"""add schedules

Revision ID: f8a1c3e70b56
Revises: e4f2a8c6d915
Create Date: 2026-08-11 00:00:00.000004

Backs the Schedules screen: a recurring run of a JobTemplate. `next_run_at` is
the one field the dispatcher polls (app.workers.tasks.dispatch_due_schedules,
registered on Celery Beat's minute tick in app.core.celery_app) -- indexed for
that scan.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""

import sqlalchemy as sa
from alembic import op

revision = "f8a1c3e70b56"
down_revision = "e4f2a8c6d915"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("cadence", sa.String(length=100), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_result", sa.String(length=20), nullable=True),
        sa.Column("last_job_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["job_templates.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_schedules_owner_id"), "schedules", ["owner_id"])
    op.create_index(op.f("ix_schedules_next_run_at"), "schedules", ["next_run_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_schedules_next_run_at"), table_name="schedules")
    op.drop_index(op.f("ix_schedules_owner_id"), table_name="schedules")
    op.drop_table("schedules")
