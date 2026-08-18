"""add exports.columns/row_scope/row_count/size_bytes/expires_at

Revision ID: c2a7e5f91d36
Revises: b4f9d2e6a813
Create Date: 2026-08-12 00:00:00.000000

Backs the Export screen's Column Selection panel, Row Scope panel, and Export
History table (rows/size/expires columns) -- none of which the `exports` table
carried before this; `export_job` always wrote every column for every result
with no record of what was written or for how long.

- `columns`: comma-joined group keys (identity,contact,location,scoring) the
  writers restrict output to. NULL means "every column" -- the pre-existing
  behavior, so old rows and any caller that omits the field keep working
  unchanged.
- `row_scope`: only ever `'all'` today. The Figma design's "Current filter"/
  "Current selection" scopes need frontend-side filter/selection state the
  backend has no way to reconstruct (same limitation noted on
  `Result.suppressed`), so the column exists for a future cycle but nothing
  writes anything else into it yet.
- `row_count`/`size_bytes`: stamped by `export_job` once the file is written,
  for the History table's ROWS/SIZE columns. NULL on rows exported before this
  migration -- never backfilled from a file that may no longer exist.
- `expires_at`: stamped at creation as `generated_at + settings.export_retention_days`.
  A new Celery Beat task (`purge_expired_exports`) deletes the file and clears
  `file_path`/`expires_at` once this passes -- see `app.workers.tasks`.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""
import sqlalchemy as sa
from alembic import op

revision = 'c2a7e5f91d36'
down_revision = 'b4f9d2e6a813'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('exports', sa.Column('columns', sa.String(length=200), nullable=True))
    op.add_column('exports', sa.Column('row_scope', sa.String(length=20), nullable=True))
    op.add_column('exports', sa.Column('row_count', sa.Integer(), nullable=True))
    op.add_column('exports', sa.Column('size_bytes', sa.Integer(), nullable=True))
    op.add_column('exports', sa.Column('expires_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('exports', 'expires_at')
    op.drop_column('exports', 'size_bytes')
    op.drop_column('exports', 'row_count')
    op.drop_column('exports', 'row_scope')
    op.drop_column('exports', 'columns')
