"""add suppression_entries

Revision ID: d5b8f3a072e9
Revises: c2a7e5f91d36
Create Date: 2026-08-12 00:00:00.000000

Backs the Suppression List screen -- genuinely missing before this: the only
prior suppression concept was `Result.suppressed`, a job-scoped per-row flag
with no global reach (see that column's own comment). This table is the real,
global, cross-job list the Figma header copy describes ("never scraped, never
stored, and stripped from exports").

One row per rule. `kind` + `value` is the match key:
- domain: exact hostname match (apex or `www.` prefix only -- NOT subdomains
  or substrings, to keep the blast radius of a single rule bounded and
  auditable before the user confirms a delete).
- email: exact address match, checked against each comma-split value on
  `results.email` (which can hold several).
- place: exact match against `results.place_key`.

Unique on (kind, value) so the same rule can't be added twice with a
different reason silently shadowing the first.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""
import sqlalchemy as sa
from alembic import op

revision = 'd5b8f3a072e9'
down_revision = 'c2a7e5f91d36'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'suppression_entries',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('kind', sa.String(length=10), nullable=False),  # domain | email | place
        sa.Column('value', sa.String(length=255), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.Column('created_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index(op.f('ix_suppression_entries_kind'), 'suppression_entries', ['kind'])
    op.create_unique_constraint(
        'uq_suppression_entries_kind_value', 'suppression_entries', ['kind', 'value']
    )


def downgrade() -> None:
    op.drop_constraint('uq_suppression_entries_kind_value', 'suppression_entries', type_='unique')
    op.drop_index(op.f('ix_suppression_entries_kind'), table_name='suppression_entries')
    op.drop_table('suppression_entries')
