"""XLSX export via openpyxl. Legacy equivalent: ExportManager's Excel COM interop
(ExcelDocument) -- no Excel/COM dependency needed here."""

from openpyxl import Workbook

from app.db.models.result import Result
from app.export.csv_writer import resolve_columns
from app.scraping.common.lead_score import lead_score


def write_xlsx(results: list[Result], output_path: str, *, columns: list[str] | None = None) -> str:
    fields, include_score = resolve_columns(columns)
    header = [*fields, "score", "score_reasons"] if include_score else fields

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Results"

    sheet.append(header)
    for result in results:
        row = [getattr(result, column) for column in fields]
        if include_score:
            score = lead_score(result)
            row.append(score["value"])
            row.append("; ".join(score["reasons"]))
        sheet.append(row)

    workbook.save(output_path)
    return output_path
