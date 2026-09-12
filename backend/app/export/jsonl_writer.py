"""JSONL export -- one JSON object per result, same column-group filtering as
CSV/XLSX (see `app.export.csv_writer.resolve_columns`). Newline-delimited JSON
so a consumer can stream-parse without loading the whole file, unlike a single
JSON array.
"""

import json

from app.db.models.result import Result
from app.export.csv_writer import resolve_columns
from app.scraping.common.lead_score import lead_score


def write_jsonl(
    results: list[Result], output_path: str, *, columns: list[str] | None = None
) -> str:
    fields, include_score = resolve_columns(columns)

    with open(output_path, "w", encoding="utf-8") as fh:
        for result in results:
            row = {column: getattr(result, column) for column in fields}
            if include_score:
                score = lead_score(result)
                row["score"] = score["value"]
                row["score_reasons"] = "; ".join(score["reasons"])
            fh.write(json.dumps(row, default=str, ensure_ascii=False))
            fh.write("\n")
    return output_path
