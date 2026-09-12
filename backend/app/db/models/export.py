import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AppBase

# Column groups the Export screen's Column Selection panel offers, matching
# the Figma groupings exactly. "reviews" (Identity group's fourth field in the
# design) is deliberately absent from IDENTITY_FIELDS below: there is no
# review-count column on Result and nothing scrapes one, so including it would
# mean exporting a fabricated blank -- see COLUMN_GROUPS' docstring.
COLUMN_GROUPS: dict[str, tuple[str, ...]] = {
    "identity": ("category", "name", "rating"),
    "contact": (
        "phone",
        "mobile_phone",
        "email",
        "website",
        "decision_maker",
        "facebook",
        "instagram",
        "linkedin",
        "twitter",
        "youtube",
        "tiktok",
        "whatsapp",
        "other_socials",
    ),
    "location": ("address", "city", "state", "country", "zip_code", "latitude", "longitude"),
    "sentiment": ("sentiment_score", "sentiment_label", "pain_points", "reviews_count"),
    # Not a Result column -- computed via app.scraping.common.lead_score and
    # appended as two extra fields (score, score_reasons) by the writers.
    "scoring": (),
}

# Only "all" is wired today -- see the migration docstring on why "filter"/
# "selection" can't be reconstructed server-side yet.
ROW_SCOPES = ("all",)


class Export(AppBase):
    __tablename__ = "exports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"))
    format: Mapped[str] = mapped_column(String(10))  # csv | xlsx | kml | jsonl | sheets
    status: Mapped[str] = mapped_column(String(20), default="pending")
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # "sheets" format only: the pushed spreadsheet's share URL. Nothing on disk
    # for that format (see app.export.sheets_writer), so file_path stays NULL
    # and download_export redirects here instead of streaming a file.
    external_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Export screen only (below). NULL on every field means "every column,
    # kept forever" -- the behavior every export had before this screen existed.
    columns: Mapped[str | None] = mapped_column(String(200), nullable=True)
    row_scope: Mapped[str | None] = mapped_column(String(20), nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
