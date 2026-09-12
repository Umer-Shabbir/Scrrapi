"""add job_target place counters

Revision ID: 3d5a71b0c9e4
Revises: 1cb2ea535c2e
Create Date: 2026-08-08 00:00:00.000000

`places_found` / `places_done` let a target stay "running" until the places its
feed scrape enqueued have actually been scraped. Before this, a target flipped
to "done" the moment it handed the URLs to the queue, and the job rolled up to
"done" with no results in it.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""

import sqlalchemy as sa
from alembic import op

revision = "3d5a71b0c9e4"
down_revision = "1cb2ea535c2e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_targets",
        sa.Column("places_found", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "job_targets",
        sa.Column("places_done", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("job_targets", "places_done")
    op.drop_column("job_targets", "places_found")
