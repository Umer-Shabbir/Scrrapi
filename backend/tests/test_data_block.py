import pytest

from app.scraping.common.data_block import parse_packed_response


def test_parse_packed_response_strips_xssi_prefix() -> None:
    raw = ")]}'\n[[1,2],[3,4]]"

    assert parse_packed_response(raw) == [[1, 2], [3, 4]]


def test_parse_packed_response_without_prefix() -> None:
    raw = '["a", "b", null]'

    assert parse_packed_response(raw) == ["a", "b", None]


def test_parse_packed_response_rejects_non_array_top_level() -> None:
    with pytest.raises(ValueError):
        parse_packed_response('{"not": "an array"}')


def test_parse_packed_response_rejects_invalid_json() -> None:
    with pytest.raises(ValueError):
        parse_packed_response("not json at all")
