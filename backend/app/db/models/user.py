import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AppBase


class User(AppBase):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Account lockout (login screen error-locked state).
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Base32 TOTP secret. NULL means 2FA isn't enabled for this user -- there's
    # no self-service enrollment yet, so this is seeded directly in the DB.
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Team & Roles screen (SCREENLIST.md §16). This app has no multi-tenancy --
    # every row in this table already IS the one workspace's member list, so
    # "team" needed no new org/workspace concept, just these 3 columns.
    # "owner" is not enforced as unique -- the first-created user is treated
    # as the workspace's de-facto owner by app.api.routers.team, but nothing
    # stops seeding a second one by hand.
    role: Mapped[str] = mapped_column(String(20), default="viewer")  # owner | operator | viewer
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Touched on every successful authenticated request (see
    # app.api.deps.get_current_user) -- backs the member table's "last seen"
    # column ("Online now" within the last 2 minutes, else relative time).
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # First-run / Compliance modal (SCREENLIST.md §22). NULL means the user
    # has never completed the 3-pane compliance flow -- the modal shows on
    # next authenticated load. Set once, on the third pane's confirmation
    # (app.api.routers.auth.acknowledge_compliance); each pane also writes
    # its own audit_events row for the legal record, this column is only the
    # fast per-request gate.
    compliance_ack_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
