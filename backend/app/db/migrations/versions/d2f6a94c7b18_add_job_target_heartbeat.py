"""add job_targets.heartbeat_at

Revision ID: d2f6a94c7b18
Revises: b6e29f4c0a17
Create Date: 2026-08-12 17:15:00.000000

A "running" target had no signal short of job status that told a worker who
died mid-scrape (or a broker that lost the in-flight task on restart) apart
from one legitimately still working a multi-hour feed. Without it, a target
orphaned that way sat at "running" forever, permanently holding one of the
`concurrent_targets` slots and blocking every job queued behind it -- which
is exactly the "job stays queued and never runs" failure this backs the fix
for (see `app.workers.dispatch._reclaim_stuck_running`).

Backfilled to `dispatched_at` for existing running/queued rows so the reclaim
sweep has something to compare against immediately rather than treating
every in-flight row as stale on first deploy.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""
import sqlalchemy as sa
from alembic import op

revision = 'd2f6a94c7b18'
down_revision = 'b6e29f4c0a17'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('job_targets', sa.Column('heartbeat_at', sa.DateTime(), nullable=True))
    op.create_index(
        op.f('ix_job_targets_heartbeat_at'), 'job_targets', ['heartbeat_at'], unique=False
    )
    op.execute("UPDATE job_targets SET heartbeat_at = dispatched_at WHERE dispatched_at IS NOT NULL")


def downgrade() -> None:
    op.drop_index(op.f('ix_job_targets_heartbeat_at'), table_name='job_targets')
    op.drop_column('job_targets', 'heartbeat_at')
