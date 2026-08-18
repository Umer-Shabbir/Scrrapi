import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AppBase


class JobTemplate(AppBase):
    """A saved job definition -- keywords, areas, and source -- that can be run
    again without re-filling the wizard. `keywords`/`locations` mirror the same
    shapes `POST /api/jobs` accepts (a flat keyword list, a list of LocationSpec
    dicts), stored as JSON since neither has a fixed column shape and both are
    always read/written whole, never queried into."""

    __tablename__ = "job_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    source: Mapped[str] = mapped_column(String(20))
    keywords: Mapped[list] = mapped_column(JSON)
    locations: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
