"""add audit_events

Revision ID: b7e94a1c53d8
Revises: a3d8f6c92b45
Create Date: 2026-08-13 00:00:00.000000

Backs the Audit Log screen (SCREENLIST.md §18) -- genuinely missing before
this, there was no event/audit table at all.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""
import sqlalchemy as sa
from alembic import op

revision = 'b7e94a1c53d8'
down_revision = 'a3d8f6c92b45'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'audit_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('actor_email', sa.String(length=255), nullable=True),
        sa.Column('action', sa.String(length=60), nullable=False),
        sa.Column('target', sa.String(length=255), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('before_after', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_events_created_at'), 'audit_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_events_actor_email'), 'audit_events', ['actor_email'], unique=False)
    op.create_index(op.f('ix_audit_events_action'), 'audit_events', ['action'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_events_action'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_actor_email'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_created_at'), table_name='audit_events')
    op.drop_table('audit_events')
