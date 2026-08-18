"""add job_templates

Revision ID: e4f2a8c6d915
Revises: d7b3f5e91a68
Create Date: 2026-08-11 00:00:00.000003

Backs the Job Templates screen: a saved keyword/area/source combination that
can be run again (POST /api/templates/{id}/run) without re-filling the wizard.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""
import sqlalchemy as sa
from alembic import op

revision = 'e4f2a8c6d915'
down_revision = 'd7b3f5e91a68'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'job_templates',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('owner_id', sa.Uuid(), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('keywords', sa.JSON(), nullable=False),
        sa.Column('locations', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_job_templates_owner_id'), 'job_templates', ['owner_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_job_templates_owner_id'), table_name='job_templates')
    op.drop_table('job_templates')
