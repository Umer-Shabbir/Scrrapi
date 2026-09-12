"""add result is_unclaimed column

Revision ID: 26520f75246a
Revises: e8f1a2c3b4d5
Create Date: 2026-09-12 18:49:26.709395

Adds `is_unclaimed` (Boolean, nullable=True) to results table to track whether Google/Bing
Maps listing has the "Claim this business" prompt.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""

import sqlalchemy as sa
from alembic import op

revision = "26520f75246a"
down_revision = "e8f1a2c3b4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("results", sa.Column("is_unclaimed", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("results", "is_unclaimed")
