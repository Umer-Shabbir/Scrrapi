"""add user login security columns (lockout + totp)

Revision ID: a2e6c9f0b1d4
Revises: f1c7d9a3b204
Create Date: 2026-08-11 00:00:00.000000

Backs the login screen's error-locked and totp states: `failed_login_attempts`
and `locked_until` implement the lockout, `totp_secret` (NULL unless enrolled)
gates the 2FA step. All three are nullable/defaulted so existing rows need no
backfill.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""
import sqlalchemy as sa
from alembic import op

revision = 'a2e6c9f0b1d4'
down_revision = 'f1c7d9a3b204'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column('users', sa.Column('locked_until', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('totp_secret', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'totp_secret')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
