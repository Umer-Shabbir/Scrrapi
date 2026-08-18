"""Shared audit-event writer, called from the routers whose mutations the
Audit Log screen (SCREENLIST.md §18) needs to show.

Instrumented this cycle: auth login (success/failure/lockout), team
invite/role-change/disable/enable/remove, api-keys create/revoke, settings
update, suppression create/bulk/delete.

Not instrumented this cycle (genuinely out of scope for one screen -- see
CLAUDE.md rule #5): job/schedule/template/category/location/proxy/
integration/webhook-delivery mutations. Those routers are unchanged; adding
audit calls to every mutating endpoint in the app is a larger, cross-cutting
change than "wire the Audit Log screen to real data" requires. The log will
under-report activity outside the instrumented set until a future cycle
extends coverage -- that's a real, documented gap, not a fabricated "complete"
audit trail.
"""

from sqlalchemy.orm import Session
from starlette.requests import Request

from app.db.models.audit_event import AuditEvent


def client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host


def log_audit_event(
    db: Session,
    *,
    actor_email: str | None,
    action: str,
    target: str | None = None,
    ip_address: str | None = None,
    success: bool = True,
    before_after: dict | None = None,
) -> None:
    """Adds and flushes an AuditEvent on the caller's existing session/
    transaction -- does not commit. Callers already commit their own mutation;
    the audit row rides in the same transaction so a rollback can't leave a
    logged action that didn't actually happen (or vice versa)."""
    db.add(
        AuditEvent(
            actor_email=actor_email,
            action=action,
            target=target,
            ip_address=ip_address,
            success=success,
            before_after=before_after,
        )
    )
