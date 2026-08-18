"""API Keys screen (SCREENLIST.md §17). Genuinely missing before this --
no model/router for programmatic access existed at all.

Only the key's SHA-256 hash is stored, never the plaintext -- the same
one-time-reveal shape as Team's invite temp-password. `prefix` is the first
12 chars of the generated key (`msk_live_XXXXXXXX`) and is the only thing
the table view ever shows post-creation, matching the Figma table's PREFIX
column.

`request_count_30d`/`usage_daily` back the USAGE (30D) sparkline. No route in
this app currently authenticates *with* an API key (every router still only
accepts the JWT bearer session token) -- see SCREENLIST.md §17 dev note: until
something actually calls in using one of these keys, real usage is genuinely
zero, so these start and stay at 0 rather than being seeded with fabricated
numbers to make the sparkline look alive.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AppBase

# Matches the role-matrix capability "Manage integrations and API keys" --
# owner-only, enforced in app.api.routers.api_keys the same way Team gates
# invite/remove.
SCOPES = ("read_results", "create_jobs", "export", "admin")


class ApiKey(AppBase):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(String(120))
    # First 12 chars of the plaintext key (e.g. "msk_live_7f2a") -- the only
    # fragment ever shown again after creation.
    prefix: Mapped[str] = mapped_column(String(20))
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Comma-separated CIDR blocks from the create-key form; empty = any IP.
    ip_allowlist: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 30 daily counts, oldest first -- real request counts once API-key auth
    # is wired to any route (not yet); starts as 30 zeros, never backfilled
    # with invented traffic.
    usage_daily: Mapped[list[int]] = mapped_column(JSON, default=lambda: [0] * 30)
