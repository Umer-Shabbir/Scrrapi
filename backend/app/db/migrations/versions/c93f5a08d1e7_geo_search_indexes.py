"""geo search indexes for type-ahead

Revision ID: c93f5a08d1e7
Revises: 7f3a9c1d5e2b
Create Date: 2026-08-08 00:00:00.000000

Seeding the whole world puts ~1M cities and ~1.8M postal codes behind the
location pickers, which can no longer render every option — they search the
server as you type. Three things have to be true for that to work.

**Accent folding.** Place names outside English are full of diacritics and
nobody types them: `sao` has to find "São Paulo", `munchen` has to find
"München". `geo_norm()` lowercases and strips accents, and both the stored
names and the search term go through it, so the comparison is ASCII on both
sides. It wraps the two-argument `unaccent(regdictionary, text)` rather than
the one-argument form — the latter depends on the default text-search config
and so is only STABLE, which Postgres will not allow in an index.

**Prefix matching that uses an index.** This database collates as en_US.utf8,
under which a plain btree is unusable for `LIKE 'aus%'` — it plans as a
sequential scan over every city on earth. `text_pattern_ops` on the normalized
name fixes that.

**Contains matching that uses an index.** The endpoints rank prefix hits first
but still answer "york" with "New York", and an unindexed `LIKE '%york%'` is
another full scan. pg_trgm GIN covers it.

Run against the geo DB only: `alembic -x target=geo upgrade geo@head`.
"""

from alembic import op

revision = "c93f5a08d1e7"
down_revision = "7f3a9c1d5e2b"
branch_labels = None
depends_on = None

NORMALIZER = """
CREATE OR REPLACE FUNCTION geo_norm(text) RETURNS text AS
$$ SELECT unaccent('unaccent', lower($1)) $$
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
"""

# Prefix search. The parent id leads each composite so the index still applies
# once the cascade has narrowed to one country/region/city.
PREFIX_INDEXES = [
    ("ix_country_name_prefix", "country (geo_norm(name) text_pattern_ops)"),
    ("ix_region_country_name_prefix", "region (country_id, geo_norm(name) text_pattern_ops)"),
    ("ix_city_region_name_prefix", "city (region_id, geo_norm(name) text_pattern_ops)"),
    ("ix_zip_city_code_prefix", "zip_code (city_id, code text_pattern_ops)"),
]

CONTAINS_INDEXES = [
    ("ix_city_name_trgm", "city USING gin (geo_norm(name) gin_trgm_ops)"),
    ("ix_region_name_trgm", "region USING gin (geo_norm(name) gin_trgm_ops)"),
]

# The region-wide ZIP listing joins city on region_id and orders by city name;
# without this it sorts tens of thousands of cities on every request.
SUPPORT_INDEXES = [("ix_city_region_name", "city (region_id, name)")]

ALL_INDEXES = PREFIX_INDEXES + CONTAINS_INDEXES + SUPPORT_INDEXES


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute(NORMALIZER)

    for name, definition in ALL_INDEXES:
        op.execute(f"CREATE INDEX {name} ON {definition}")


def downgrade() -> None:
    for name, _ in reversed(ALL_INDEXES):
        op.execute(f"DROP INDEX IF EXISTS {name}")
    op.execute("DROP FUNCTION IF EXISTS geo_norm(text)")
    # The extensions are left installed — other objects may depend on them.
