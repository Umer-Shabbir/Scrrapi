import pytest

from app.scraping.google_maps.query import build_search_url


def test_build_search_url_joins_keyword_and_location() -> None:
    url = build_search_url("plumbers", "Austin, TX")

    assert url == "https://www.google.com/maps/search/plumbers+in+Austin%2C+TX"


def test_build_search_url_without_location() -> None:
    url = build_search_url("plumbers", "")

    assert url == "https://www.google.com/maps/search/plumbers"


def test_build_search_url_strips_whitespace() -> None:
    url = build_search_url("  coffee shops  ", "  Seattle  ")

    assert url == "https://www.google.com/maps/search/coffee+shops+in+Seattle"


def test_build_search_url_rejects_empty_keyword() -> None:
    with pytest.raises(ValueError):
        build_search_url("   ", "Seattle")
