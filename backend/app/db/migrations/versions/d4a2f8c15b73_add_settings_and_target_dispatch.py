"""add app_settings and job_target dispatch bookkeeping

Revision ID: d4a2f8c15b73
Revises: b8e41d7c9a52
Create Date: 2026-08-09 00:00:00.000000

Backs the scrape concurrency limit. `app_settings` is the key/value table the
Settings page writes and every worker reads, and `job_targets.dispatched_at` /
`dispatch_id` are what let a target be "queued" without being on the broker --
the dispatcher hands over only as many as the limit allows.

Existing rows get `dispatched_at = NULL`, which reads as "waiting for a slot".
Correct for a finished job and for a target already `running` (that one holds
its slot by status alone). The one rough edge is upgrading with a job mid-flight:
a target that the old code had put on the broker but no worker has started yet
looks un-dispatched here and can be sent a second time, since there is no
`dispatch_id` on it for the original copy to notice it has been superseded.
Drain the queue before upgrading if that matters.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""
import sqlalchemy as sa
from alembic import op

revision = 'd4a2f8c15b73'
down_revision = 'b8e41d7c9a52'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(length=64), primary_key=True),
        sa.Column('value', sa.String(length=255), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.add_column('job_targets', sa.Column('dispatched_at', sa.DateTime(), nullable=True))
    op.add_column('job_targets', sa.Column('dispatch_id', sa.String(length=64), nullable=True))
    # The dispatcher's hot path counts targets by (status, dispatched_at) on
    # every pass, and job_targets is the table that grows fastest here -- one row
    # per keyword x ZIP, thousands per job.
    op.create_index(
        'ix_job_targets_dispatched_at', 'job_targets', ['dispatched_at']
    )


def downgrade() -> None:
    op.drop_index('ix_job_targets_dispatched_at', table_name='job_targets')
    op.drop_column('job_targets', 'dispatch_id')
    op.drop_column('job_targets', 'dispatched_at')
    op.drop_table('app_settings')
