"""Google Sheets writer: pushes rows to a live sheet via a service account and
returns the share URL rather than a local path. The Google API client itself
is stubbed here -- these tests cover our own branching (config gate, column
resolution, cell coercion, permission grant), not googleapiclient's HTTP layer.
"""

import uuid

import pytest

from app.core.config import get_settings
from app.db.models.result import Result
from app.export.sheets_writer import SheetsNotConfigured, write_sheets


def _result(**overrides) -> Result:
    defaults = dict(
        id=uuid.uuid4(), job_id=uuid.uuid4(),
        category="Plumber", name="Austin Plumbing", address="1 Main St",
        city="Austin", state="TX", country="US", zip_code="78701",
        phone="555-0100", email="a@b.com", website="b.com",
        latitude=30.1, longitude=-97.7, rating=4.8,
        facebook=None, instagram=None, linkedin=None, twitter=None,
        youtube=None, tiktok=None, whatsapp=None, other_socials=None,
        tech_stack=None,
    )
    defaults.update(overrides)
    return Result(**defaults)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_write_sheets_raises_when_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_SHEETS_CREDENTIALS_PATH", raising=False)
    monkeypatch.delenv("GOOGLE_SHEETS_SHARE_WITH", raising=False)

    with pytest.raises(SheetsNotConfigured):
        write_sheets([_result()], "unused", columns=None)


def test_write_sheets_raises_when_share_target_missing(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "creds.json")
    monkeypatch.delenv("GOOGLE_SHEETS_SHARE_WITH", raising=False)

    with pytest.raises(SheetsNotConfigured):
        write_sheets([_result()], "unused", columns=None)


class _FakeValues:
    def __init__(self, sink: dict) -> None:
        self._sink = sink

    def update(self, *, spreadsheetId, range, valueInputOption, body):
        self._sink["spreadsheet_id"] = spreadsheetId
        self._sink["range"] = range
        self._sink["values"] = body["values"]
        return _FakeRequest(None)


class _FakeSpreadsheets:
    def __init__(self, sink: dict) -> None:
        self._sink = sink

    def create(self, *, body, fields):
        self._sink["title"] = body["properties"]["title"]
        return _FakeRequest({
            "spreadsheetId": "sheet123",
            "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/sheet123",
        })

    def values(self):
        return _FakeValues(self._sink)


class _FakeRequest:
    def __init__(self, result) -> None:
        self._result = result

    def execute(self):
        return self._result


class _FakeSheetsService:
    def __init__(self, sink: dict) -> None:
        self._sink = sink

    def spreadsheets(self):
        return _FakeSpreadsheets(self._sink)


class _FakePermissions:
    def __init__(self, sink: dict) -> None:
        self._sink = sink

    def create(self, *, fileId, body, sendNotificationEmail):
        self._sink["shared_with"] = body["emailAddress"]
        self._sink["file_id"] = fileId
        return _FakeRequest(None)


class _FakeDriveService:
    def __init__(self, sink: dict) -> None:
        self._sink = sink

    def permissions(self):
        return _FakePermissions(self._sink)


def test_write_sheets_pushes_rows_and_shares(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "creds.json")
    monkeypatch.setenv("GOOGLE_SHEETS_SHARE_WITH", "someone@example.com")

    sink: dict = {}
    monkeypatch.setattr(
        "app.export.sheets_writer.service_account.Credentials.from_service_account_file",
        lambda path, scopes: object(),
    )

    def _fake_build(name, version, *, credentials, cache_discovery):
        return _FakeSheetsService(sink) if name == "sheets" else _FakeDriveService(sink)

    monkeypatch.setattr("app.export.sheets_writer.build", _fake_build)

    url = write_sheets([_result()], "unused", columns=["identity"])

    assert url == "https://docs.google.com/spreadsheets/d/sheet123"
    assert sink["values"][0] == ["category", "name", "rating"]
    assert sink["values"][1] == ["Plumber", "Austin Plumbing", 4.8]
    assert sink["shared_with"] == "someone@example.com"
    assert sink["file_id"] == "sheet123"
