"""Search-term handling on the geo cascade endpoints.

These run against ~700k cities once the world is seeded, so what the term is
allowed to become before it reaches Postgres matters: a stray wildcard or a
one-character term turns every keystroke into a full scan.
"""

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.api.routers.locations import MIN_SEARCH_LEN, _clean, _name_search
from app.db.models.geo import City, ZipCode


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def test_short_terms_are_discarded():
    # "a" would rank a hundred thousand cities; the picker shows the head of the
    # list until a second character arrives.
    assert _clean("a") == ""
    assert _clean(" ") == ""
    assert _clean(None) == ""
    assert len("au") == MIN_SEARCH_LEN
    assert _clean("au") == "au"


def test_terms_are_trimmed():
    assert _clean("  austin  ") == "austin"


def test_like_wildcards_in_user_input_are_escaped():
    # Unescaped, a leading "%" makes the prefix half of the search match every
    # row in the table.
    assert _clean("%") == ""  # too short to search at all
    assert _clean("a%b") == r"a\%b"
    assert _clean("a_b") == r"a\_b"
    assert _clean("a\\b") == "a\\\\b"


def test_no_term_orders_by_name_and_adds_no_filter():
    sql = _sql(_name_search(select(City), City.name, ""))

    assert "ORDER BY city.name" in sql
    assert "LIKE" not in sql.upper()


def _clauses(stmt) -> tuple[str, str]:
    where, _, order = _sql(stmt).partition("ORDER BY")
    return where, order


def test_a_term_matches_prefix_or_contains_with_prefix_ranked_first():
    where, order = _clauses(_name_search(select(City), City.name, "aus"))

    assert where.count("geo_norm(city.name) LIKE") == 2  # the prefix half and the contains half
    assert " OR " in where
    # The same prefix test is reused as the sort key, so exact-start hits come
    # out above the ones that merely contain the term.
    assert "geo_norm(city.name) LIKE" in order
    assert "DESC" in order


def test_both_sides_are_folded_in_sql_not_python():
    # The indexes are built on geo_norm(name). Folding the term in Python
    # instead would still return the right rows but stop matching the index
    # expression, which turns every keystroke into a sequential scan.
    where, _ = _clauses(_name_search(select(City), City.name, "sao"))

    assert where.count("geo_norm(city.name)") == 2
    assert where.count("geo_norm(%(geo_norm_") == 2  # the search term, folded server-side too


def test_escape_character_is_passed_through_to_postgres():
    sql = _sql(_name_search(select(City), City.name, r"a\%b"))

    assert "ESCAPE" in sql


def test_region_has_zips_compiles_to_exists_not_a_count():
    # `regionHasZips` decides whether the picker offers postal codes or falls
    # back to areas. Dubai's region alone holds 178k codes, so counting them to
    # answer a yes/no question would scan six figures of rows per keystroke.
    import uuid

    stmt = select(
        select(ZipCode.id)
        .join(City, City.id == ZipCode.city_id)
        .where(City.region_id == uuid.uuid4())
        .exists()
    )
    sql = _sql(stmt)

    assert "EXISTS" in sql
    assert "count" not in sql.lower()
