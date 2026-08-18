"""Category/keyword list endpoints (free text entry + CSV upload).

GET  /api/categories         -> suggested business categories, optionally filtered by ?q=
POST /api/categories/upload  -> parse an uploaded CSV/TXT file into a keyword list

Categories are not persisted server-side: the frontend keeps the working list in
component state and hands it to job creation as `keywords` (see
`jobs.py::create_job`, which materialises one `JobTarget` per keyword x location).
This endpoint pair only supplies suggestions and turns a file into a clean list.
Legacy equivalent: UploadCategoriesForm.
"""

import csv
import io

from fastapi import APIRouter, HTTPException, Query, UploadFile, status

router = APIRouter()

# Upper bounds for an uploaded file. Keeps a stray multi-megabyte export from
# being read into memory and from turning into tens of thousands of scrape targets.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_KEYWORDS = 5000
# Matches JobTarget.keyword's String(255).
MAX_KEYWORD_LENGTH = 255

ALLOWED_EXTENSIONS = (".csv", ".txt", ".tsv")

# Cell values that are almost certainly a header rather than a keyword.
HEADER_CELLS = frozenset({"category", "categories", "keyword", "keywords", "name", "query"})

# Common Google/Bing Maps business categories, used to populate the
# free-text field's autocomplete. Not exhaustive by design — the field
# accepts anything the user types.
SUGGESTED_CATEGORIES: tuple[str, ...] = (
    "Accountant",
    "Advertising agency",
    "Architect",
    "Auto repair shop",
    "Bakery",
    "Bar",
    "Barber shop",
    "Beauty salon",
    "Car dealer",
    "Car wash",
    "Chiropractor",
    "Cleaning service",
    "Coffee shop",
    "Construction company",
    "Dentist",
    "Doctor",
    "Electrician",
    "Estate agent",
    "Event planner",
    "Financial advisor",
    "Fitness centre",
    "Florist",
    "Furniture store",
    "Garden centre",
    "General contractor",
    "Grocery store",
    "Hair salon",
    "Hardware store",
    "Hotel",
    "Insurance agency",
    "Interior designer",
    "IT services",
    "Jeweller",
    "Landscaper",
    "Laundry service",
    "Lawyer",
    "Locksmith",
    "Marketing agency",
    "Massage therapist",
    "Mechanic",
    "Moving company",
    "Nail salon",
    "Optician",
    "Painter",
    "Pest control service",
    "Pet groomer",
    "Pharmacy",
    "Photographer",
    "Physiotherapist",
    "Plumber",
    "Printing shop",
    "Private investigator",
    "Real estate agency",
    "Restaurant",
    "Roofing contractor",
    "Security service",
    "Solar panel installer",
    "Spa",
    "Tattoo studio",
    "Tax consultant",
    "Travel agency",
    "Tutoring service",
    "Veterinarian",
    "Web designer",
    "Wedding planner",
)


@router.get("/")
def list_categories(
    q: str | None = Query(default=None, description="Case-insensitive substring filter"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[str]:
    """Suggested categories for the keyword autocomplete."""
    if q:
        needle = q.strip().casefold()
        matches = [c for c in SUGGESTED_CATEGORIES if needle in c.casefold()]
    else:
        matches = list(SUGGESTED_CATEGORIES)
    return matches[:limit]


@router.post("/upload")
async def upload_categories(file: UploadFile) -> dict:
    """Parse an uploaded CSV/TXT file into a deduplicated keyword list.

    Every cell of every row is treated as a candidate keyword, so both
    one-keyword-per-line text files and multi-column CSV exports work.
    """
    _check_extension(file.filename)

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"file larger than {MAX_UPLOAD_BYTES // 1024}KB",
        )

    keywords, skipped = parse_keywords(_decode(raw))
    if not keywords:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="no keywords found in file",
        )

    truncated = len(keywords) > MAX_KEYWORDS
    if truncated:
        keywords = keywords[:MAX_KEYWORDS]

    return {
        "keywords": keywords,
        "count": len(keywords),
        "skipped": skipped,
        "truncated": truncated,
    }


def parse_keywords(text: str) -> tuple[list[str], int]:
    """Split CSV/TSV/plain text into an ordered, deduplicated keyword list.

    Returns `(keywords, skipped)` where `skipped` counts cells dropped for being
    too long or for being a duplicate of an earlier one.
    """
    keywords: list[str] = []
    seen: set[str] = set()
    skipped = 0

    reader = csv.reader(io.StringIO(text), delimiter=_sniff_delimiter(text))
    for row_index, row in enumerate(reader):
        for cell in row:
            value = cell.strip().strip('"').strip()
            if not value:
                continue
            if row_index == 0 and value.casefold() in HEADER_CELLS:
                continue
            if len(value) > MAX_KEYWORD_LENGTH:
                skipped += 1
                continue
            key = value.casefold()
            if key in seen:
                skipped += 1
                continue
            seen.add(key)
            keywords.append(value)

    return keywords, skipped


def _sniff_delimiter(text: str) -> str:
    """Pick a delimiter without csv.Sniffer, which raises on single-column files."""
    sample = text[:8192]
    if "\t" in sample:
        return "\t"
    if ";" in sample and sample.count(";") > sample.count(","):
        return ";"
    return ","


def _decode(raw: bytes) -> str:
    # utf-8-sig strips the BOM Excel writes on "CSV UTF-8" export.
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _check_extension(filename: str | None) -> None:
    if not filename or not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"expected one of {', '.join(ALLOWED_EXTENSIONS)}",
        )
