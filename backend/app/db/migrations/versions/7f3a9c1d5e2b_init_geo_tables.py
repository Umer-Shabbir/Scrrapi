"""init geo tables

Revision ID: 7f3a9c1d5e2b
Revises:
Create Date: 2026-08-07 00:00:00.000000

Run against the geo DB only: `alembic -x target=geo upgrade geo@head`.
Separate revision chain from the app DB migrations (see env.py) — each
target DB gets its own alembic_version table. Two root migrations
(down_revision=None) share this versions/ dir, so `branch_labels` splits
them into distinct heads ('app'/'geo') — use `<label>@head`, plain `head`
is ambiguous with two roots present.
"""

import sqlalchemy as sa
from alembic import op

revision = "7f3a9c1d5e2b"
down_revision = None
branch_labels = ("geo",)
depends_on = None


def upgrade() -> None:
    op.create_table(
        "country",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=2), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_country_code"), "country", ["code"], unique=True)
    op.create_index(op.f("ix_country_name"), "country", ["name"], unique=False)

    op.create_table(
        "region",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("country_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["country_id"],
            ["country.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_region_country_id"), "region", ["country_id"], unique=False)
    op.create_index(op.f("ix_region_name"), "region", ["name"], unique=False)

    op.create_table(
        "city",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("region_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["region_id"],
            ["region.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_city_region_id"), "city", ["region_id"], unique=False)
    op.create_index(op.f("ix_city_name"), "city", ["name"], unique=False)

    op.create_table(
        "zip_code",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(
            ["city_id"],
            ["city.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_zip_code_city_id"), "zip_code", ["city_id"], unique=False)
    op.create_index(op.f("ix_zip_code_code"), "zip_code", ["code"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_zip_code_code"), table_name="zip_code")
    op.drop_index(op.f("ix_zip_code_city_id"), table_name="zip_code")
    op.drop_table("zip_code")

    op.drop_index(op.f("ix_city_name"), table_name="city")
    op.drop_index(op.f("ix_city_region_id"), table_name="city")
    op.drop_table("city")

    op.drop_index(op.f("ix_region_name"), table_name="region")
    op.drop_index(op.f("ix_region_country_id"), table_name="region")
    op.drop_table("region")

    op.drop_index(op.f("ix_country_name"), table_name="country")
    op.drop_index(op.f("ix_country_code"), table_name="country")
    op.drop_table("country")
