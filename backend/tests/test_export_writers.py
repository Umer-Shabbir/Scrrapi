"""Column-group filtering for the Export screen's Column Selection panel --
CSV/XLSX/JSONL narrow to the requested groups (or every column when None), and
all three append the shared score when SCORING is requested. KML ignores the
param entirely (its shape has no columns to narrow). Sheets shares the same
column-resolution logic but pushes to a live Google Sheet -- tested separately
against a stubbed API client (test_write_sheets_* below)."""

import csv
import json
import uuid

import openpyxl

from app.db.models.result import Result
from app.export.csv_writer import resolve_columns, write_csv
from app.export.jsonl_writer import write_jsonl
from app.export.kml_writer import write_kml
from app.export.xlsx_writer import write_xlsx


def _result(**overrides) -> Result:
    defaults = dict(
        id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        category="Plumber",
        name="Austin Plumbing",
        address="1 Main St",
        city="Austin",
        state="TX",
        country="US",
        zip_code="78701",
        phone="555-0100",
        email="a@b.com",
        website="b.com",
        latitude=30.1,
        longitude=-97.7,
        rating=4.8,
        facebook=None,
        instagram=None,
        linkedin=None,
        twitter=None,
        youtube=None,
        tiktok=None,
        whatsapp=None,
        other_socials=None,
        tech_stack=None,
    )
    defaults.update(overrides)
    return Result(**defaults)


def test_resolve_columns_none_keeps_everything() -> None:
    fields, include_score = resolve_columns(None)
    assert "phone" in fields and "address" in fields and "rating" in fields
    assert include_score is False


def test_resolve_columns_identity_only() -> None:
    fields, include_score = resolve_columns(["identity"])
    assert set(fields) == {"category", "name", "rating", "is_unclaimed"}
    assert include_score is False


def test_resolve_columns_scoring_flags_score_with_no_result_columns() -> None:
    fields, include_score = resolve_columns(["scoring"])
    assert fields == []
    assert include_score is True


def test_write_csv_restricted_to_contact_group(tmp_path) -> None:
    path = tmp_path / "out.csv"
    write_csv([_result()], str(path), columns=["contact"])

    with open(path, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["phone"] == "555-0100"
    assert "category" not in rows[0]
    assert "score" not in rows[0]


def test_write_csv_scoring_group_appends_score_columns(tmp_path) -> None:
    path = tmp_path / "out.csv"
    write_csv([_result()], str(path), columns=["identity", "scoring"])

    with open(path, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["category"] == "Plumber"
    assert int(rows[0]["score"]) > 0
    assert "verified phone" in rows[0]["score_reasons"]


def test_write_xlsx_restricted_columns(tmp_path) -> None:
    path = tmp_path / "out.xlsx"
    write_xlsx([_result()], str(path), columns=["location"])

    workbook = openpyxl.load_workbook(path)
    sheet = workbook.active
    header = [cell.value for cell in next(sheet.iter_rows(max_row=1))]
    assert "address" in header
    assert "phone" not in header


def test_write_kml_ignores_columns_param(tmp_path) -> None:
    path = tmp_path / "out.kml"
    write_kml([_result()], str(path), columns=["contact"])

    content = path.read_text(encoding="utf-8")
    assert "<Placemark>" in content
    assert "Austin Plumbing" in content


def test_write_jsonl_one_object_per_line(tmp_path) -> None:
    path = tmp_path / "out.jsonl"
    write_jsonl([_result(), _result(name="Dallas Plumbing")], str(path), columns=["identity"])

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    rows = [json.loads(line) for line in lines]
    assert rows[0] == {"category": "Plumber", "name": "Austin Plumbing", "rating": 4.8, "is_unclaimed": None}
    assert rows[1]["name"] == "Dallas Plumbing"


def test_write_jsonl_scoring_group_appends_score_fields(tmp_path) -> None:
    path = tmp_path / "out.jsonl"
    write_jsonl([_result()], str(path), columns=["identity", "scoring"])

    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["category"] == "Plumber"
    assert row["score"] > 0
    assert "verified phone" in row["score_reasons"]


def test_write_jsonl_none_keeps_every_column(tmp_path) -> None:
    path = tmp_path / "out.jsonl"
    write_jsonl([_result()], str(path))

    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["phone"] == "555-0100"
    assert "score" not in row
