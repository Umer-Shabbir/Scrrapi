"""add jobs.name

Revision ID: d7b3f5e91a68
Revises: c1d8e4a7f302
Create Date: 2026-08-11 00:00:00.000002

Backs the New Job Wizard's review step, which lets a job be given a human
label ("Plumbers — Austin Metro") instead of being identified only by id.
Nullable: existing jobs and anything created directly through the API without
a name keep displaying the id, same as before.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""

import sqlalchemy as sa
from alembic import op

revision = "d7b3f5e91a68"
down_revision = "c1d8e4a7f302"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "name")
