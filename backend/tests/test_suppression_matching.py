"""Suppression matching is exact-match by design (see suppression.py's module
docstring) -- these tests exist specifically to pin the blast radius, since a
false-positive match here means real rows get deleted that shouldn't be."""

import uuid

from app.db.models.result import Result
from app.scraping.common.suppression import (
    email_field_matches,
    normalize_domain,
    normalize_email,
    result_is_suppressed,
    website_matches_domain,
)


def _result(**overrides) -> Result:
    defaults = dict(
        id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        website=None,
        email=None,
        place_key=None,
    )
    defaults.update(overrides)
    return Result(**defaults)


def test_normalize_domain_strips_www_and_scheme() -> None:
    assert normalize_domain("competitor-crm.io") == "competitor-crm.io"
    assert normalize_domain("WWW.Competitor-CRM.io") == "competitor-crm.io"
    assert normalize_domain("https://www.competitor-crm.io/path") == "competitor-crm.io"


def test_website_matches_domain_exact_and_www() -> None:
    assert website_matches_domain("competitor-crm.io", "competitor-crm.io")
    assert website_matches_domain("www.competitor-crm.io", "competitor-crm.io")
    assert website_matches_domain("https://www.competitor-crm.io", "competitor-crm.io")


def test_website_matches_domain_rejects_subdomain() -> None:
    assert not website_matches_domain("sub.competitor-crm.io", "competitor-crm.io")


def test_website_matches_domain_rejects_substring() -> None:
    assert not website_matches_domain("notcompetitor-crm.io", "competitor-crm.io")
    assert not website_matches_domain("competitor-crm.io.evil.com", "competitor-crm.io")


def test_website_matches_domain_none_website_is_false() -> None:
    assert not website_matches_domain(None, "competitor-crm.io")


def test_email_field_matches_one_of_several_joined_addresses() -> None:
    field = "a@example.com, b@example.com"
    assert email_field_matches(field, "b@example.com")
    assert not email_field_matches(field, "c@example.com")


def test_normalize_email_lowercases() -> None:
    assert normalize_email("  Info@Example.COM ") == "info@example.com"


def test_result_is_suppressed_checks_every_entry_kind() -> None:
    entries = [("domain", "bad.com"), ("email", "spam@x.com"), ("place", "abc123")]

    assert result_is_suppressed(_result(website="bad.com"), entries)
    assert result_is_suppressed(_result(email="spam@x.com"), entries)
    assert result_is_suppressed(_result(place_key="abc123"), entries)
    assert not result_is_suppressed(_result(website="fine.com"), entries)
