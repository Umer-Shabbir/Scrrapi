"""CSV export. Legacy equivalent: ExportManager.BuildCSVLine / SaveToCSV.

Default column order: Category, Name, Rating, Address, City, State, Country, ZIP,
Phone, Email, Website, Latitude, Longitude, then the social profile columns the
deep crawler fills in. `columns` (Export screen's Column Selection panel)
narrows this to one or more of `app.db.models.export.COLUMN_GROUPS`; omitting
it keeps every column, same as every export had before that screen existed.
`rating` joined this list alongside the Lead Detail cycle that first persisted
it -- both scraper's place data included it long before either screen wired it
through.

`phone` and `email` may each hold several values joined with ", " (Maps' own
first, then whatever the site crawl added). Left as one column on purpose: the
spreadsheet this ends up in is a call list, and splitting into email_1..email_15
would make it unreadable for the 90% of rows with exactly one.
"""

import csv

from app.db.models.export import COLUMN_GROUPS
from app.db.models.result import SOCIAL_COLUMNS, Result
from app.scraping.common.lead_score import lead_score

COLUMNS = [
    "category", "name", "rating", "address", "city", "state", "country", "zip_code",
    "phone", "email", "website", "latitude", "longitude",
    *SOCIAL_COLUMNS, "other_socials",
]


def resolve_columns(groups: list[str] | None) -> tuple[list[str], bool]:
    """Result columns to write, plus whether the SCORING group was requested.

    `groups=None` (or empty) means every column, unfiltered -- the behavior
    every export had before the Column Selection panel existed.
    """
    if not groups:
        return COLUMNS, False
    wanted: list[str] = []
    for group in groups:
        wanted.extend(COLUMN_GROUPS.get(group, ()))
    # Preserve COLUMNS' order rather than the group iteration order, so a
    # selection of {location, identity} still reads left-to-right sensibly.
    ordered = [c for c in COLUMNS if c in wanted]
    return ordered, "scoring" in groups


def write_csv(results: list[Result], output_path: str, *, columns: list[str] | None = None) -> str:
    fields, include_score = resolve_columns(columns)
    header = [*fields, "score", "score_reasons"] if include_score else fields

    # utf-8-sig (BOM) so Excel auto-detects UTF-8 instead of mangling accented
    # chars -- Sheets/plain csv readers ignore the BOM fine either way.
    with open(output_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        for result in results:
            row = {column: getattr(result, column) for column in fields}
            if include_score:
                score = lead_score(result)
                row["score"] = score["value"]
                row["score_reasons"] = "; ".join(score["reasons"])
            writer.writerow(row)
    return output_path
