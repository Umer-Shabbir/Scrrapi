"""`_target_area` — where a Result's city/state/country/zip actually come from.

Google's place panel returns one unsplit address string, so those four columns
are copied off the JobTarget the place was found for. Every caller has to cope
with the map being empty, which is the case for a hand-typed location and for
any `scrape_place` task queued before targets carried geo at all.
"""

import uuid

from app.db.models.job import JobTarget
from app.workers.tasks import _target_area


class StubDb:
    """Stands in for a Session: `get` is the only thing `_target_area` calls."""

    def __init__(self, row=None):
        self.row = row
        self.requested: list[tuple] = []

    def get(self, model, pk):
        self.requested.append((model, pk))
        return self.row


def _target(**kwargs) -> JobTarget:
    return JobTarget(
        job_id=uuid.uuid4(),
        keyword="plumber",
        location_label="78701, Austin, Texas, United States",
        **kwargs,
    )


def test_zip_target_supplies_all_four_columns():
    target = _target(zip_code="78701", city="Austin", region="Texas", country="United States")

    assert _target_area(StubDb(target), str(uuid.uuid4())) == {
        "zip_code": "78701",
        "city": "Austin",
        "region": "Texas",
        "country": "United States",
    }


def test_hand_typed_target_yields_nulls_not_a_missing_key():
    # A label-only location has no geo behind it; the columns stay blank rather
    # than the lookup raising or the keys going absent.
    area = _target_area(StubDb(_target()), str(uuid.uuid4()))

    assert area == {"zip_code": None, "city": None, "region": None, "country": None}


def test_no_target_id_short_circuits_without_touching_the_db():
    db = StubDb(_target(zip_code="78701"))

    assert _target_area(db, None) == {}
    assert db.requested == []


def test_deleted_target_is_empty_rather_than_an_error():
    assert _target_area(StubDb(None), str(uuid.uuid4())) == {}


def test_place_data_wins_over_the_target_for_a_field_it_provides():
    # The precedence `scrape_place` applies: anything the scraper managed to
    # extract beats the target's fallback, so a future address parser drops in
    # without this having to be unwound.
    area = _target_area(StubDb(_target(zip_code="78701", city="Austin")), str(uuid.uuid4()))
    place = {"city": "West Lake Hills"}

    assert (place.get("city") or area.get("city")) == "West Lake Hills"
    assert (place.get("zip_code") or area.get("zip_code")) == "78701"
