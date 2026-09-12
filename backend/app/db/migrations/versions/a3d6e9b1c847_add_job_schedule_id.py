"""add jobs.schedule_id

Revision ID: a3d6e9b1c847
Revises: f8a1c3e70b56
Create Date: 2026-08-11 00:00:00.000005

Backs the Schedule & Monitoring screen's run history: a job fired by the
scheduler (app.workers.tasks.dispatch_due_schedules) is now linked back to the
schedule that created it, so "every run of this schedule" is a plain filter
on jobs.schedule_id rather than something reconstructed after the fact.
Nullable -- every job started by a person has no schedule behind it.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""

import sqlalchemy as sa
from alembic import op

revision = "a3d6e9b1c847"
down_revision = "f8a1c3e70b56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("schedule_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_jobs_schedule_id_schedules", "jobs", "schedules", ["schedule_id"], ["id"]
    )
    op.create_index(op.f("ix_jobs_schedule_id"), "jobs", ["schedule_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_jobs_schedule_id"), table_name="jobs")
    op.drop_constraint("fk_jobs_schedule_id_schedules", "jobs", type_="foreignkey")
    op.drop_column("jobs", "schedule_id")
