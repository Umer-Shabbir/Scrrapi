"""Unit tests for 11.2: JSON envelope + context that follows the call stack."""

import json
import logging

import pytest

from app.core.logging import ContextFilter, JsonFormatter, TextFormatter, log_context


@pytest.fixture
def record_factory():
    def make(msg: str = "hello", **extra):
        record = logging.LogRecord(
            name="app.workers.tasks",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg=msg,
            args=None,
            exc_info=None,
        )
        for key, value in extra.items():
            setattr(record, key, value)
        ContextFilter().filter(record)
        return record

    return make


def _emit(record) -> dict:
    return json.loads(JsonFormatter().format(record))


def test_envelope_fields(record_factory):
    payload = _emit(record_factory())
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.workers.tasks"
    assert payload["msg"] == "hello"
    assert payload["ts"]


def test_bound_context_lands_on_every_line(record_factory):
    with log_context(job_id="job-1", target_id="t-1", place_url="https://x/place"):
        payload = _emit(record_factory())
    assert payload["job_id"] == "job-1"
    assert payload["target_id"] == "t-1"
    assert payload["place_url"] == "https://x/place"


def test_context_does_not_leak_out_of_the_block(record_factory):
    with log_context(job_id="job-1"):
        pass
    assert "job_id" not in _emit(record_factory())


def test_nested_context_merges_then_restores(record_factory):
    with log_context(job_id="job-1"):
        with log_context(place_url="https://x/place"):
            inner = _emit(record_factory())
        outer = _emit(record_factory())

    assert inner["job_id"] == "job-1"
    assert inner["place_url"] == "https://x/place"
    assert outer["job_id"] == "job-1"
    assert "place_url" not in outer


def test_none_values_are_dropped(record_factory):
    with log_context(job_id="job-1", target_id=None):
        payload = _emit(record_factory())
    assert "target_id" not in payload


def test_extra_kwargs_are_serialized(record_factory):
    payload = _emit(record_factory(places_enqueued=12))
    assert payload["places_enqueued"] == 12


def test_exception_is_captured(record_factory):
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = record_factory("task failed")
        record.exc_info = sys.exc_info()
        payload = _emit(record)
    assert "ValueError: boom" in payload["exc"]


def test_text_formatter_appends_context(record_factory):
    with log_context(job_id="job-1"):
        line = TextFormatter().format(record_factory())
    assert "[job_id=job-1]" in line
