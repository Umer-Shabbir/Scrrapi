"""add Lead Detail columns (status/tags/suppressed/rating/provenance/tech
stack/place_key) and the result_history table

Revision ID: b4f9d2e6a813
Revises: a3d6e9b1c847
Create Date: 2026-08-12 00:00:00.000000

Backs the Lead Detail screen end to end:

- `status`/`tags`/`suppressed`: claimed/closed badge, TAG action, SUPPRESS
  action. All three are per-result (job-scoped) -- there is no cross-job place
  identity to key a *global* suppression/tag list against (same limitation
  Schedule & Monitoring's delta-chart note already documents), so SUPPRESS
  here only marks this row; it does not feed the separate, unbuilt
  Suppression List screen or the scrape queue.
- `rating`: both place scrapers (google_maps/place.py, bing_maps/place.py)
  already extract this from the listing -- it was simply never persisted.
  This is the PARTIAL case from the backend gap policy: extend the existing
  pipeline, don't invent a new one.
- `phone_source`/`email_source`: which stage supplied the value ("maps
  listing" vs "site crawl") -- both are already known at write time in
  workers/tasks.py, just not recorded before now.
- `tech_stack`: comma-joined signatures from a new, isolated home-page fetch
  (app.scraping.common.tech_fingerprint) -- decoupled from the deep crawler,
  so it changes nothing about SiteContacts or the crawl hot path.
- `place_key`: a deterministic identity for "this business" derived from
  normalized name+address+zip (Result rows are otherwise insert-only with no
  identity across separate job runs -- there is no Google/Bing place-id
  captured today, and parsing one out of the Maps URL would mean touching the
  untested live-scraper regex surface for a single screen's benefit). Indexed
  so a new result can look up the most recent prior row for the same business
  across any job.
- `result_history`: one row per changed field (phone/email/rating), written
  when a new result's place_key matches a prior one and a tracked field
  differs. This is what the Lead Detail HISTORY block reads.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""

import sqlalchemy as sa
from alembic import op

revision = "b4f9d2e6a813"
down_revision = "a3d6e9b1c847"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "results",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
    )
    op.add_column("results", sa.Column("tags", sa.String(length=500), nullable=True))
    op.add_column(
        "results",
        sa.Column("suppressed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("results", sa.Column("rating", sa.Float(), nullable=True))
    op.add_column("results", sa.Column("phone_source", sa.String(length=40), nullable=True))
    op.add_column("results", sa.Column("email_source", sa.String(length=40), nullable=True))
    op.add_column("results", sa.Column("tech_stack", sa.String(length=255), nullable=True))
    op.add_column("results", sa.Column("place_key", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_results_place_key"), "results", ["place_key"])

    op.create_table(
        "result_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("result_id", sa.Uuid(), sa.ForeignKey("results.id"), nullable=False),
        sa.Column("field", sa.String(length=40), nullable=False),
        sa.Column("old_value", sa.String(length=500), nullable=True),
        sa.Column("new_value", sa.String(length=500), nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_result_history_result_id"), "result_history", ["result_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_result_history_result_id"), table_name="result_history")
    op.drop_table("result_history")

    op.drop_index(op.f("ix_results_place_key"), table_name="results")
    op.drop_column("results", "place_key")
    op.drop_column("results", "tech_stack")
    op.drop_column("results", "email_source")
    op.drop_column("results", "phone_source")
    op.drop_column("results", "rating")
    op.drop_column("results", "suppressed")
    op.drop_column("results", "tags")
    op.drop_column("results", "status")
