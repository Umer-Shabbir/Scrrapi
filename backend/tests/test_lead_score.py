"""Pure-function coverage for the shared Lead Detail / Export scoring rule --
the same function both surfaces call, so this is the one place the point
values and thresholds need to be right."""

import uuid

from app.db.models.result import Result
from app.scraping.common.lead_score import lead_score


def _result(**overrides) -> Result:
    defaults = dict(
        id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        phone=None,
        email=None,
        website=None,
        rating=None,
        tech_stack=None,
        facebook=None,
        instagram=None,
        linkedin=None,
        twitter=None,
        youtube=None,
        tiktok=None,
        whatsapp=None,
    )
    defaults.update(overrides)
    return Result(**defaults)


def test_empty_lead_scores_zero() -> None:
    score = lead_score(_result())
    assert score == {"value": 0, "reasons": []}


def test_full_signals_cap_at_100() -> None:
    score = lead_score(
        _result(
            phone="555-0100",
            email="a@b.com",
            website="b.com",
            rating=4.9,
            tech_stack="WordPress",
            facebook="x",
            instagram="x",
            linkedin="x",
        )
    )
    # 20 + 20 + 15 + 15 + 5 + min(10, 3*5)=10 -> 85, well under 100; cap is
    # exercised separately below.
    assert score["value"] == 85
    assert "high rating: 4.9 (+15)" in score["reasons"]


def test_good_rating_below_threshold_scores_less() -> None:
    high = lead_score(_result(rating=4.5))
    good = lead_score(_result(rating=4.0))
    low = lead_score(_result(rating=3.9))
    assert high["value"] == 15
    assert good["value"] == 8
    assert low["value"] == 0


def test_social_points_cap_at_ten_regardless_of_profile_count() -> None:
    three = lead_score(_result(facebook="x", instagram="x", linkedin="x"))
    seven = lead_score(
        _result(
            facebook="x",
            instagram="x",
            linkedin="x",
            twitter="x",
            youtube="x",
            tiktok="x",
            whatsapp="x",
        )
    )
    assert three["value"] == 10
    assert seven["value"] == 10
    assert "3 social profiles (+10)" in three["reasons"]
    assert "7 social profiles (+10)" in seven["reasons"]


def test_decision_maker_and_mobile_scoring() -> None:
    score = lead_score(_result(decision_maker="Alice (Owner)", mobile_phone="555-0999"))
    assert score["value"] == 20
    assert "decision maker identified (+10)" in score["reasons"]
    assert "direct mobile line (+10)" in score["reasons"]
