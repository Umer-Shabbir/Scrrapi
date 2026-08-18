import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AppBase

# What the last fire produced. "misfired" means the scheduler noticed
# `next_run_at` had passed by more than the misfire grace period before it got
# a chance to run -- e.g. the beat process was down -- so the run was skipped
# rather than silently executed hours late with a stale "next run" estimate.
LAST_RESULT_VALUES = frozenset({"done", "error", "misfired"})


class Schedule(AppBase):
    """A recurring run of a JobTemplate. `cadence` is a standard 5-field cron
    expression (croniter-compatible); the UI's daily/weekly/custom choices all
    compile down to one before it reaches here, so this table and the
    dispatcher only ever deal with one representation."""

    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_templates.id"))
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)

    cadence: Mapped[str] = mapped_column(String(100))
    # IANA zone name (e.g. "America/Chicago"). Cadence fields are evaluated in
    # this zone, then converted to UTC for storage in next_run_at -- so "9am
    # daily" fires at 9am local time year-round, including across DST shifts.
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Always UTC. The one field the dispatcher polls; recomputed after every
    # fire (or skip) so a fresh row and a long-idle one look the same to it.
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
