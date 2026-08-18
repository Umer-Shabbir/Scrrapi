"""widen results.email/phone and add social profile columns

Revision ID: f1c7d9a3b204
Revises: d4a2f8c15b73
Create Date: 2026-08-09 00:00:00.000000

Backs the deep site crawler. With it on, a result carries every address and
number found across the business's website, not just the one Maps listed, so
`email` and `phone` stop being single values: they hold a ", "-joined list and
are widened to fit it (255 -> 1000 and 50 -> 500). Widening a varchar in Postgres
is a catalog-only change -- no table rewrite, no lock held for long -- and every
existing value still fits, so this is safe to run on a populated table.

The eight social columns are new and nullable: a row scraped with the crawler off
(the default) leaves all of them NULL, which is what the grid renders as a dash.

The downgrade narrows `email`/`phone` back, and *that* one is lossy -- a merged
list longer than the old limit cannot be stored, so the values are truncated
first rather than letting the ALTER fail halfway.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""
import sqlalchemy as sa
from alembic import op

revision = 'f1c7d9a3b204'
down_revision = 'd4a2f8c15b73'
branch_labels = None
depends_on = None

SOCIAL_COLUMNS = (
    'facebook',
    'instagram',
    'linkedin',
    'twitter',
    'youtube',
    'tiktok',
    'whatsapp',
)


def upgrade() -> None:
    op.alter_column(
        'results',
        'email',
        existing_type=sa.String(length=255),
        type_=sa.String(length=1000),
        existing_nullable=True,
    )
    op.alter_column(
        'results',
        'phone',
        existing_type=sa.String(length=50),
        type_=sa.String(length=500),
        existing_nullable=True,
    )

    for column in SOCIAL_COLUMNS:
        op.add_column('results', sa.Column(column, sa.String(length=500), nullable=True))
    op.add_column('results', sa.Column('other_socials', sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column('results', 'other_socials')
    for column in reversed(SOCIAL_COLUMNS):
        op.drop_column('results', column)

    op.execute("UPDATE results SET phone = left(phone, 50) WHERE length(phone) > 50")
    op.execute("UPDATE results SET email = left(email, 255) WHERE length(email) > 255")
    op.alter_column(
        'results',
        'phone',
        existing_type=sa.String(length=500),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        'results',
        'email',
        existing_type=sa.String(length=1000),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
