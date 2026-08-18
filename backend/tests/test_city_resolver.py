"""`CityResolver` — folding postal localities onto the city people actually name.

The postal export's `place_name` is whatever the national post office calls a
delivery area. In the US that is the city ("Austin"); in Pakistan it is the
individual post office ("Lahore Gpo", "Lahore Alflah", "Lahore Model Town"), and
taking it literally turned Lahore into dozens of one-ZIP "cities" in the picker
instead of one city with dozens of ZIPs.

Coordinates and accuracy flags below are the real GeoNames values.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from seed_geo import CityResolver  # noqa: E402

LAHORE = (31.558, 74.35071)
# Every Lahore post office carries accuracy 1 and a position that is nowhere
# near Lahore — "Lahore Model Town" is plotted 516km away in the desert.
ESTIMATED = "1"
REAL = "4"


@pytest.fixture
def pk() -> CityResolver:
    r = CityResolver()
    r.add_place("PK", "04", "Lahore", *LAHORE)
    return r


def test_post_offices_fold_into_their_city(pk):
    assert pk.resolve("PK", "04", "Lahore Gpo", "31.5822", "74.3292", ESTIMATED) == "Lahore"
    assert pk.resolve("PK", "04", "Lahore Alflah", "31.5822", "74.3292", ESTIMATED) == "Lahore"


def test_estimated_coordinates_do_not_veto_the_name(pk):
    # The bug this exists for: accuracy 1 puts "Lahore Model Town" 516km out, so
    # an unconditional distance check rejected exactly the rows to be fixed.
    assert (
        pk.resolve("PK", "04", "Lahore Model Town", "28.1598", "70.6959", ESTIMATED) == "Lahore"
    )
    assert (
        pk.resolve("PK", "04", "Lahore Johar Town", "28.1598", "70.6959", ESTIMATED) == "Lahore"
    )


def test_a_place_that_merely_contains_the_city_name_is_left_alone(pk):
    # Separate towns, not Lahore post offices — the match must be a *prefix*.
    assert (
        pk.resolve("PK", "04", "Nawan Lahore", "31.3245", "72.7282", REAL) == "Nawan Lahore"
    )
    assert pk.resolve("PK", "04", "Wagha Lahore", "31.6", "74.55", REAL) == "Wagha Lahore"
    assert (
        pk.resolve("PK", "04", "River View, Lahore", "28.16", "70.69", ESTIMATED)
        == "River View, Lahore"
    )


def test_the_city_itself_resolves_to_itself(pk):
    assert pk.resolve("PK", "04", "Lahore", "31.558", "74.35071", REAL) == "Lahore"


def test_word_boundary_is_required(pk):
    assert pk.resolve("PK", "04", "Lahorewala", "31.56", "74.35", ESTIMATED) == "Lahorewala"


def test_us_cities_are_untouched_because_the_longest_match_wins():
    # place_name already *is* the city in the US, and an exact self-match is the
    # longest possible prefix, so no shorter one can steal the row. Without that
    # rule "Kansas City" could collapse to "Kansas".
    r = CityResolver()
    r.add_place("US", "NY", "Springfield", 42.83, -74.85)
    r.add_place("US", "NY", "Springfield Gardens", 40.6715, -73.7573)
    r.add_place("US", "KS", "Kansas", 39.1, -94.6)
    r.add_place("US", "KS", "Kansas City", 39.1141, -94.6275)

    assert (
        r.resolve("US", "NY", "Springfield Gardens", "40.6715", "-73.7573", REAL)
        == "Springfield Gardens"
    )
    assert r.resolve("US", "KS", "Kansas City", "39.1141", "-94.6275", REAL) == "Kansas City"


def test_real_coordinates_still_veto_a_far_away_namesake():
    # Same state, same name, 250km apart. With accuracy 4 the position is
    # trustworthy, so it overrules the name match.
    r = CityResolver()
    r.add_place("US", "NY", "Springfield", 42.83, -74.85)

    assert (
        r.resolve("US", "NY", "Springfield Heights", "40.6715", "-73.7573", REAL)
        == "Springfield Heights"
    )
    # ...and with only an estimated position, the name is the best evidence there is.
    assert (
        r.resolve("US", "NY", "Springfield Heights", "40.6715", "-73.7573", ESTIMATED)
        == "Springfield"
    )


def test_blank_accuracy_is_not_a_basis_for_a_veto(pk):
    assert pk.resolve("PK", "04", "Lahore Gpo", "28.1598", "70.6959", "") == "Lahore"


def test_region_scoping_stops_cross_state_matches():
    # "New York Mills" is in Minnesota; "New York" is a place in NY state. The
    # anchor table is keyed by region, so they never meet.
    r = CityResolver()
    r.add_place("US", "NY", "New York", 40.7143, -74.006)

    assert (
        r.resolve("US", "MN", "New York Mills", "46.5183", "-95.3761", REAL)
        == "New York Mills"
    )


def test_unknown_region_passes_through(pk):
    assert pk.resolve("PK", "99", "Lahore Gpo", "31.5822", "74.3292", ESTIMATED) == "Lahore Gpo"


def test_first_place_wins_so_the_anchor_is_stable(pk):
    # A duplicate name in the same region must not move the anchor between the
    # two seed passes — they compute city_id from this and have to agree.
    pk.add_place("PK", "04", "Lahore", 31.9, 74.9)

    assert pk.resolve("PK", "04", "Lahore Gpo", "31.5822", "74.3292", ESTIMATED) == "Lahore"
