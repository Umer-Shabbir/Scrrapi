"""add_geo_coordinates

Revision ID: d405646dc2b8
Revises: c93f5a08d1e7
Create Date: 2026-08-29 17:34:43.496632
"""

import sqlalchemy as sa
from alembic import op

revision = "d405646dc2b8"
down_revision = "c93f5a08d1e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add latitude/longitude to country
    op.add_column("country", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("country", sa.Column("longitude", sa.Float(), nullable=True))
    op.create_index(op.f("ix_country_latitude"), "country", ["latitude"], unique=False)
    op.create_index(op.f("ix_country_longitude"), "country", ["longitude"], unique=False)

    # Add latitude/longitude to region
    op.add_column("region", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("region", sa.Column("longitude", sa.Float(), nullable=True))
    op.create_index(op.f("ix_region_latitude"), "region", ["latitude"], unique=False)
    op.create_index(op.f("ix_region_longitude"), "region", ["longitude"], unique=False)

    # Add latitude/longitude to city
    op.add_column("city", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("city", sa.Column("longitude", sa.Float(), nullable=True))
    op.create_index(op.f("ix_city_latitude"), "city", ["latitude"], unique=False)
    op.create_index(op.f("ix_city_longitude"), "city", ["longitude"], unique=False)

    # Add latitude/longitude to zip_code
    op.add_column("zip_code", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("zip_code", sa.Column("longitude", sa.Float(), nullable=True))
    op.create_index(op.f("ix_zip_code_latitude"), "zip_code", ["latitude"], unique=False)
    op.create_index(op.f("ix_zip_code_longitude"), "zip_code", ["longitude"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_zip_code_longitude"), table_name="zip_code")
    op.drop_index(op.f("ix_zip_code_latitude"), table_name="zip_code")
    op.drop_column("zip_code", "longitude")
    op.drop_column("zip_code", "latitude")

    op.drop_index(op.f("ix_city_longitude"), table_name="city")
    op.drop_index(op.f("ix_city_latitude"), table_name="city")
    op.drop_column("city", "longitude")
    op.drop_column("city", "latitude")

    op.drop_index(op.f("ix_region_longitude"), table_name="region")
    op.drop_index(op.f("ix_region_latitude"), table_name="region")
    op.drop_column("region", "longitude")
    op.drop_column("region", "latitude")

    op.drop_index(op.f("ix_country_longitude"), table_name="country")
    op.drop_index(op.f("ix_country_latitude"), table_name="country")
    op.drop_column("country", "longitude")
    op.drop_column("country", "latitude")
