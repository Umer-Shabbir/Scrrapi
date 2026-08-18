"""Google Sheets export. Unlike csv/xlsx/kml/jsonl this writes nothing to
disk -- it pushes rows straight to a newly-created Google Sheet via a service
account and returns the spreadsheet's share URL, not a file path.

Service-account only: there's no OAuth callback route in this backend (see
app.db.models.integration's comment on why Slack/HubSpot/Pipedrive/Sheets
cards all stay "not_connected"), so this can't act as a given user's own
Google account. Instead it uses one fixed service account (creds JSON at
`settings.google_sheets_credentials_path`) and shares every sheet it creates
with `settings.google_sheets_share_with` -- otherwise the file would sit in
the service account's own Drive with nobody able to open it.

Raises `SheetsNotConfigured` if either setting is missing, and lets any
Google API error propagate -- `export_job` already retries/fails an export on
an unhandled exception (see workers.tasks.export_job), and a silently-empty
"success" would be worse than a visible failed export.
"""

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.core.config import get_settings
from app.db.models.export import COLUMN_GROUPS  # noqa: F401  (re-exported for callers' convenience)
from app.db.models.result import Result
from app.export.csv_writer import resolve_columns
from app.scraping.common.lead_score import lead_score

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


class SheetsNotConfigured(RuntimeError):
    """Raised when GOOGLE_SHEETS_CREDENTIALS_PATH / GOOGLE_SHEETS_SHARE_WITH
    aren't set -- the export was requested but this backend has no service
    account to push it with."""


def write_sheets(results: list[Result], output_path: str, *, columns: list[str] | None = None) -> str:
    """Signature matches every other writer in `_EXPORT_WRITERS`
    (results, output_path, columns=...) so `export_job` doesn't need a
    format-specific branch -- `output_path` is unused here (nothing local is
    written); the return value is the sheet's URL, stored in
    `Export.external_url` by `export_job` rather than `file_path`.
    """
    del output_path
    settings = get_settings()
    if not settings.google_sheets_credentials_path or not settings.google_sheets_share_with:
        raise SheetsNotConfigured(
            "GOOGLE_SHEETS_CREDENTIALS_PATH and GOOGLE_SHEETS_SHARE_WITH must both be set "
            "to use the Google Sheets export format"
        )

    fields, include_score = resolve_columns(columns)
    header = [*fields, "score", "score_reasons"] if include_score else fields

    rows = [header]
    for result in results:
        row = [_cell(getattr(result, column)) for column in fields]
        if include_score:
            score = lead_score(result)
            row.append(score["value"])
            row.append("; ".join(score["reasons"]))
        rows.append(row)

    creds = service_account.Credentials.from_service_account_file(
        settings.google_sheets_credentials_path, scopes=_SCOPES
    )
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    spreadsheet = (
        sheets.spreadsheets()
        .create(body={"properties": {"title": "Leadgen export"}}, fields="spreadsheetId,spreadsheetUrl")
        .execute()
    )
    spreadsheet_id = spreadsheet["spreadsheetId"]

    sheets.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="A1",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()

    # Grant the one human inbox this service account can reach -- without
    # this the sheet is created but invisible to anyone (service accounts
    # have no Drive UI of their own).
    drive.permissions().create(
        fileId=spreadsheet_id,
        body={"type": "user", "role": "writer", "emailAddress": settings.google_sheets_share_with},
        sendNotificationEmail=False,
    ).execute()

    return spreadsheet["spreadsheetUrl"]


def _cell(value: object) -> object:
    # Sheets' API rejects non-JSON-primitive values outright (UUIDs, etc.);
    # every Result column is already str/float/int/None except id/job_id,
    # which resolve_columns' COLUMNS never includes.
    return value if value is None or isinstance(value, (str, int, float, bool)) else str(value)
