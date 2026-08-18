"""`normalize_locations` — the coercion in front of every job's target list.

The endpoint takes two shapes on the wire (a ZIP spec object from the location
queue, a bare string from the hand-typed path and the README's curl example) and
has to end up with one, deduplicated, before it multiplies by the keyword list.
"""

from app.api.routers.jobs import LocationSpec, normalize_locations


def test_bare_string_becomes_a_labelled_spec_with_no_geo() -> None:
    [spec] = normalize_locations(["Austin, TX"])

    assert spec.label == "Austin, TX"
    assert spec.zip_code is None
    assert spec.city is None


def test_spec_keeps_its_zip_and_parents() -> None:
    [spec] = normalize_locations(
        [
            LocationSpec(
                label="78701, Austin, Texas",
                zip_code="78701",
                city="Austin",
                region="Texas",
                country="United States",
            )
        ]
    )

    assert spec.zip_code == "78701"
    assert spec.city == "Austin"
    assert spec.region == "Texas"
    assert spec.country == "United States"


def test_camel_case_zip_code_from_the_frontend_is_accepted() -> None:
    request = LocationSpec.model_validate({"label": "78701, Austin, Texas", "zipCode": "78701"})

    assert request.zip_code == "78701"


def test_blank_and_whitespace_only_entries_are_dropped() -> None:
    specs = normalize_locations(["   ", "", LocationSpec(label="  "), "78701"])

    assert [s.label for s in specs] == ["78701"]


def test_labels_are_trimmed_and_empty_geo_normalizes_to_none() -> None:
    [spec] = normalize_locations([LocationSpec(label="  78701  ", zip_code="  ", city="")])

    assert spec.label == "78701"
    assert spec.zip_code is None
    assert spec.city is None


def test_duplicate_labels_collapse_case_insensitively() -> None:
    # Appending to an existing queue can re-add a ZIP that is already in it, and
    # each duplicate would otherwise be a second full scrape of the same area.
    specs = normalize_locations(["78701", "78701", LocationSpec(label="78701"), "78702"])

    assert [s.label for s in specs] == ["78701", "78702"]


def test_first_occurrence_wins_so_the_richer_spec_is_not_dropped_silently() -> None:
    specs = normalize_locations(
        [LocationSpec(label="78701", zip_code="78701", city="Austin"), "78701"]
    )

    assert len(specs) == 1
    assert specs[0].city == "Austin"
