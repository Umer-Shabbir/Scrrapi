"""add proxies

Revision ID: e91c4a6d0f57
Revises: d5b8f3a072e9
Create Date: 2026-08-12 00:00:00.000000

Backs the Proxies screen with a real, queryable pool: `app.scraping.proxy.pool`
was file/config-driven with no per-proxy identity or stats before this ("list"
mode read a flat text file; "single"/"free" modes are untouched by this
migration and stay as they are).

Status values:
- active: eligible for rotation.
- disabled: user-excluded, real (Proxies screen's DISABLE action).
- retired: user-excluded via DRAIN. Behaviorally identical to disabled today
  -- there is no in-flight-lease tracking to make DRAIN wait for anything, so
  it retires immediately rather than pretending to wait. Kept as a distinct
  status (not just an alias for disabled) so the screen's RETIRED tile and
  the all-retired state have something real to filter on, and so a retired
  proxy's UI reads honestly as "drained", not "disabled".
- cooling: auto-set after repeated blocks (see runtime cooldown logic in
  app.scraping.proxy.pool), auto-clears back to active after the cooldown
  window -- mirrors the per-host cooldown app.scraping.common.rate_limit
  already does, applied per-proxy instead.

Stats (success_count/failure_count/block_count/latency_ms_total/latency_samples)
are running counters updated after every scrape request that used the proxy --
see app.scraping.proxy.pool.ProxyPool.record_outcome. Average latency and
success rate are computed at read time from these, not stored redundantly.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""

import sqlalchemy as sa
from alembic import op

revision = "e91c4a6d0f57"
down_revision = "d5b8f3a072e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proxies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(length=10), nullable=False, server_default="http"),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("password", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("block_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms_total", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("latency_samples", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cooling_until", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_proxies_status"), "proxies", ["status"])
    op.create_unique_constraint("uq_proxies_host_port", "proxies", ["host", "port"])


def downgrade() -> None:
    op.drop_constraint("uq_proxies_host_port", "proxies", type_="unique")
    op.drop_index(op.f("ix_proxies_status"), table_name="proxies")
    op.drop_table("proxies")
