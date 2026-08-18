import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AppBase

SUPPRESSION_KINDS = ("domain", "email", "place")


class SuppressionEntry(AppBase):
    """One global suppression rule (Suppression List screen).

    Unlike `Result.suppressed` (job-scoped, set from the Lead Detail drawer),
    this is the real cross-job block list: matching results are deleted the
    moment a rule is added, matching places are skipped before a scrape ever
    writes a row (app.workers.tasks.scrape_place), and matching rows are
    excluded from every export (app.export.*_writer). See
    app.scraping.common.suppression for the matching logic all three share.
    """

    __tablename__ = "suppression_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(10))  # domain | email | place
    value: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
