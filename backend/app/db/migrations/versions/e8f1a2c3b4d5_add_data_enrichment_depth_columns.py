"""add data enrichment depth columns (decision_maker, mobile_phone, reviews, sentiment, pain_points)

Revision ID: e8f1a2c3b4d5
Revises: a4756f58b340
Create Date: 2026-09-12 00:00:00.000000

Adds Data Enrichment Depth capabilities to the results table:
- `decision_maker`: Owner, Founder, CEO and executive names/titles.
- `mobile_phone`: Direct personal mobile phone numbers.
- `reviews_count`: Total number of customer reviews.
- `sentiment_score`: Sentiment score from customer reviews (0.0 to 1.0).
- `sentiment_label`: Sentiment label ("Positive", "Neutral", "Mixed", "Negative").
- `pain_points`: Extracted pain points / complaints summary from customer reviews.

Run against the app DB only: `alembic -x target=app upgrade app@head`.
"""

import sqlalchemy as sa
from alembic import op

revision = "e8f1a2c3b4d5"
down_revision = "a4756f58b340"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("results", sa.Column("decision_maker", sa.String(length=500), nullable=True))
    op.add_column("results", sa.Column("mobile_phone", sa.String(length=500), nullable=True))
    op.add_column("results", sa.Column("reviews_count", sa.Integer(), nullable=True))
    op.add_column("results", sa.Column("sentiment_score", sa.Float(), nullable=True))
    op.add_column("results", sa.Column("sentiment_label", sa.String(length=50), nullable=True))
    op.add_column("results", sa.Column("pain_points", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("results", "pain_points")
    op.drop_column("results", "sentiment_label")
    op.drop_column("results", "sentiment_score")
    op.drop_column("results", "reviews_count")
    op.drop_column("results", "mobile_phone")
    op.drop_column("results", "decision_maker")
