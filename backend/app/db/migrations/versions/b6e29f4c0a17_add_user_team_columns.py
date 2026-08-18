"""add user team columns

Revision ID: b6e29f4c0a17
Revises: a7c3e0f56d21
Create Date: 2026-08-12 00:00:00.000000

Backs the Team & Roles screen (SCREENLIST.md §16). No multi-tenancy exists in
this app -- every row in `users` already IS the one workspace's member list --
so this only adds role/disabled/last-seen to the existing table rather than
a new org/workspace model.

The earliest-created user (lowest created_at) is treated as the workspace
owner by app.api.routers.team; existing rows are backfilled `role='owner'`
for that one user and `role='viewer'` for everyone else, which is the safest
default (viewer is the least-privileged role) until an admin explicitly
promotes someone via the screen this migration backs.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""
import sqlalchemy as sa
from alembic import op

revision = 'b6e29f4c0a17'
down_revision = 'a7c3e0f56d21'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('role', sa.String(length=20), nullable=False, server_default='viewer'))
    op.add_column('users', sa.Column('disabled_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('last_seen_at', sa.DateTime(), nullable=True))

    users = sa.table('users', sa.column('id', sa.Uuid()), sa.column('created_at', sa.DateTime()), sa.column('role', sa.String()))
    connection = op.get_bind()
    owner_id = connection.execute(
        sa.select(users.c.id).order_by(users.c.created_at.asc()).limit(1)
    ).scalar()
    if owner_id is not None:
        connection.execute(users.update().where(users.c.id == owner_id).values(role='owner'))


def downgrade() -> None:
    op.drop_column('users', 'last_seen_at')
    op.drop_column('users', 'disabled_at')
    op.drop_column('users', 'role')
