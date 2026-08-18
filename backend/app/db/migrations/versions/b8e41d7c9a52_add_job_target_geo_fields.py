"""add job_target geo fields

Revision ID: b8e41d7c9a52
Revises: 3d5a71b0c9e4
Create Date: 2026-08-08 00:00:00.000000

The search is per-ZIP now, so a target knows which postal code (and which
city/region/country it sat under) it was queued for. That is also the only
place those four columns can come from on the way out: `get_place_data`
returns Google's address as one string and nothing splits it, so `scrape_place`
copies the target's geo onto every `Result` it writes.

Nullable throughout -- a hand-typed location has a label and nothing else, and
every row that existed before this migration is exactly that.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""
import sqlalchemy as sa
from alembic import op

revision = 'b8e41d7c9a52'
down_revision = '3d5a71b0c9e4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('job_targets', sa.Column('zip_code', sa.String(length=20), nullable=True))
    op.add_column('job_targets', sa.Column('city', sa.String(length=255), nullable=True))
    op.add_column('job_targets', sa.Column('region', sa.String(length=255), nullable=True))
    op.add_column('job_targets', sa.Column('country', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_job_targets_zip_code'), 'job_targets', ['zip_code'])


def downgrade() -> None:
    op.drop_index(op.f('ix_job_targets_zip_code'), table_name='job_targets')
    op.drop_column('job_targets', 'country')
    op.drop_column('job_targets', 'region')
    op.drop_column('job_targets', 'city')
    op.drop_column('job_targets', 'zip_code')
