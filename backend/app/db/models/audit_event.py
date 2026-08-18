"""Audit Log screen (SCREENLIST.md §18). Genuinely missing before this --
no audit/event table existed anywhere in the app.

One row per mutating action across the app. `actor_email` is denormalized
(not a FK-only join) so a row still reads correctly after its actor is
removed/disabled (Team & Roles' `remove_member` only soft-deletes via
`disabled_at`, but a login-failed row from an email that was never a real
member -- see `auth.login` -- has no user row at all to join against).

Written via `app.core.audit.log_audit_event`, called from the routers that
already perform the mutations this backs (auth login/lockout, team
invite/role-change/disable/enable/remove, api-keys create/revoke, settings
update, suppression create/bulk/delete) -- see that module's docstring for
the full list and why some existing mutations were left uninstrumented this
cycle.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AppBase


class AuditEvent(AppBase):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    # Denormalized -- see module docstring. Null only for the handful of
    # pre-auth events (e.g. a login attempt for an email with no user row).
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    # Dotted verb.noun, e.g. "settings.updated", "apikey.revoked" -- matches
    # the Figma table's ACTION column verbatim, and is also the ACTION TYPE
    # filter's value space.
    action: Mapped[str] = mapped_column(String(60), index=True)
    # Human-readable target label (e.g. 'API key "Old CI Key"'); null when an
    # action has no single target (e.g. a failed login before a user is known).
    target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    # {"before": {...}, "after": {...}} -- only populated for actions that
    # change a record's fields (e.g. settings.updated); null otherwise, which
    # is what tells the table row not to render an expandable diff at all.
    before_after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
