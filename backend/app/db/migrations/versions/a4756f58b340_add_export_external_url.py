"""add exports.external_url

Revision ID: a4756f58b340
Revises: 881f9cbe6b82
Create Date: 2026-08-14 00:00:00.000000

Backs the Google Sheets export format: unlike csv/xlsx/kml/jsonl, a Sheets
"export" isn't a local file at all -- `write_sheets` pushes rows to a live
Google Sheet via a service account and hands back the spreadsheet's share URL.
`file_path` stays NULL for these rows (nothing on disk to purge/download-stream),
`external_url` carries the link instead; `_export_dict`/`download_export`
branch on which one is set (see app/api/routers/exports.py).

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""
import sqlalchemy as sa
from alembic import op

revision = 'a4756f58b340'
down_revision = '881f9cbe6b82'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('exports', sa.Column('external_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('exports', 'external_url')
