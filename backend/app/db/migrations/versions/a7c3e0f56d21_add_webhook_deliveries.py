"""add webhook_deliveries and webhook_endpoint_states

Revision ID: a7c3e0f56d21
Revises: f4b7d2c891a3
Create Date: 2026-08-12 00:00:00.000000

Backs the Webhook Delivery Log screen (SCREENLIST.md §15) -- genuinely
missing before this: the Integrations screen's own router explicitly defers
per-attempt delivery history and back-off/disable state to "a separate
screen" (its docstring's words), and no table existed for either.

`webhook_deliveries`: one row per delivery attempt/retry. `webhook_endpoint_
states`: the one durable bit (auto-disabled-at) that can't be derived from
the delivery log alone, since a disabled endpoint stops producing new rows to
derive "still disabled" from. Back-off itself IS derived on every read from
the tail of `webhook_deliveries` -- no column for it here.

Both FK to `integration_connections.id` (added by f4b7d2c891a3) rather than
duplicating a provider string, so this generalizes if a second provider ever
gets real deliveries without a schema change.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""
import sqlalchemy as sa
from alembic import op

revision = 'a7c3e0f56d21'
down_revision = 'f4b7d2c891a3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'webhook_deliveries',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column(
            'connection_id',
            sa.Uuid(),
            sa.ForeignKey('integration_connections.id'),
            nullable=False,
        ),
        sa.Column('event', sa.String(length=60), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('succeeded', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('attempt', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('attempt_max', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('request_headers', sa.JSON(), nullable=False),
        sa.Column('request_body', sa.JSON(), nullable=False),
        sa.Column('response_body', sa.JSON(), nullable=True),
        sa.Column('error', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index(
        op.f('ix_webhook_deliveries_connection_id'), 'webhook_deliveries', ['connection_id']
    )
    op.create_index(
        op.f('ix_webhook_deliveries_created_at'), 'webhook_deliveries', ['created_at']
    )

    op.create_table(
        'webhook_endpoint_states',
        sa.Column(
            'connection_id',
            sa.Uuid(),
            sa.ForeignKey('integration_connections.id'),
            primary_key=True,
        ),
        sa.Column('disabled_at', sa.DateTime(), nullable=True),
        sa.Column('disabled_reason', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('webhook_endpoint_states')
    op.drop_index(op.f('ix_webhook_deliveries_created_at'), table_name='webhook_deliveries')
    op.drop_index(op.f('ix_webhook_deliveries_connection_id'), table_name='webhook_deliveries')
    op.drop_table('webhook_deliveries')
