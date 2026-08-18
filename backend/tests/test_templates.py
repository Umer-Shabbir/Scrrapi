"""Pure-function coverage for the templates router: the keyword/location shape
that gets stored as JSON and read back has to round-trip exactly, since a
template run rebuilds LocationSpec objects from whatever was persisted."""

import uuid
from datetime import datetime

from app.api.routers.jobs import LocationSpec
from app.api.routers.templates import _location_dict, _template_dict
from app.db.models.template import JobTemplate


def test_location_dict_round_trips_a_zip_backed_spec() -> None:
    spec = LocationSpec(
        label="78701, Austin, Texas",
        zip_code="78701",
        city="Austin",
        region="Texas",
        country="United States",
    )

    stored = _location_dict(spec)
    rebuilt = LocationSpec(**stored)

    assert rebuilt == spec


def test_location_dict_accepts_a_bare_string() -> None:
    stored = _location_dict("Austin, TX")

    assert stored["label"] == "Austin, TX"
    assert stored["zipCode"] is None
    assert LocationSpec(**stored).label == "Austin, TX"


def test_template_dict_reports_the_cross_product_as_target_count() -> None:
    template = JobTemplate(
        id=uuid.uuid4(),
        name="Plumbers & HVAC — TX/OK",
        owner_id=uuid.uuid4(),
        source="google",
        keywords=["plumber", "hvac"],
        locations=[{"label": "78701"}, {"label": "78702"}, {"label": "74103"}],
        created_at=datetime(2026, 8, 7, 9, 12),
        last_run_at=None,
    )

    data = _template_dict(template)

    assert data["keywordCount"] == 2
    assert data["areaCount"] == 3
    assert data["targetCount"] == 6
    assert data["lastRunAt"] is None


def test_template_dict_formats_last_run_as_isoformat() -> None:
    template = JobTemplate(
        id=uuid.uuid4(),
        name="x",
        owner_id=uuid.uuid4(),
        source="google",
        keywords=["a"],
        locations=[{"label": "b"}],
        created_at=datetime(2026, 8, 7),
        last_run_at=datetime(2026, 8, 9, 14, 30),
    )

    assert _template_dict(template)["lastRunAt"] == "2026-08-09T14:30:00"
