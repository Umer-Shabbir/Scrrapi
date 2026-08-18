import io

from fastapi.testclient import TestClient

from app.api.routers.categories import MAX_KEYWORD_LENGTH, parse_keywords
from app.main import app

client = TestClient(app)


def _upload(content: str, filename: str = "categories.csv"):
    return client.post(
        "/api/categories/upload",
        files={"file": (filename, io.BytesIO(content.encode("utf-8")), "text/csv")},
    )


def test_list_categories_returns_suggestions() -> None:
    resp = client.get("/api/categories/")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert "Plumber" in body


def test_list_categories_filters_case_insensitively() -> None:
    resp = client.get("/api/categories/", params={"q": "sal"})
    assert resp.status_code == 200
    assert resp.json() == ["Beauty salon", "Hair salon", "Nail salon"]


def test_list_categories_respects_limit() -> None:
    resp = client.get("/api/categories/", params={"limit": 3})
    assert len(resp.json()) == 3


def test_parse_keywords_dedupes_and_keeps_order() -> None:
    keywords, skipped = parse_keywords("Plumber\nDentist\nplumber\n\n  Bakery  \n")
    assert keywords == ["Plumber", "Dentist", "Bakery"]
    assert skipped == 1


def test_parse_keywords_reads_every_column_and_drops_header() -> None:
    keywords, _ = parse_keywords("category,notes\nPlumber,urgent\nDentist,\n")
    assert keywords == ["notes", "Plumber", "urgent", "Dentist"]


def test_parse_keywords_skips_overlong_values() -> None:
    keywords, skipped = parse_keywords("Plumber\n" + "x" * (MAX_KEYWORD_LENGTH + 1))
    assert keywords == ["Plumber"]
    assert skipped == 1


def test_parse_keywords_handles_semicolon_delimiter() -> None:
    keywords, _ = parse_keywords("Plumber;Dentist;Bakery")
    assert keywords == ["Plumber", "Dentist", "Bakery"]


def test_upload_returns_keyword_list() -> None:
    resp = _upload("category\nPlumber\nDentist\nplumber\n")
    assert resp.status_code == 200
    assert resp.json() == {
        "keywords": ["Plumber", "Dentist"],
        "count": 2,
        "skipped": 1,
        "truncated": False,
    }


def test_upload_strips_excel_bom() -> None:
    resp = client.post(
        "/api/categories/upload",
        files={"file": ("categories.csv", io.BytesIO(b"\xef\xbb\xbfPlumber\n"), "text/csv")},
    )
    assert resp.json()["keywords"] == ["Plumber"]


def test_upload_rejects_unsupported_extension() -> None:
    resp = _upload("Plumber", filename="categories.xlsx")
    assert resp.status_code == 415


def test_upload_rejects_empty_file() -> None:
    resp = _upload("\n\n  \n")
    assert resp.status_code == 422
