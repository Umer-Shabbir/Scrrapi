"""Team & Roles endpoints (SCREENLIST.md §16).

GET    /api/team                    -> role matrix (static reference) + member list + seat usage
POST   /api/team/invite             -> provisions a real user (this app has no email/self-signup --
                                        see docstring below) and returns a one-time temp password
PATCH  /api/team/{userId}/role      -> change role
POST   /api/team/{userId}/disable   -> disable (blocks login, doesn't delete)
POST   /api/team/{userId}/enable    -> re-enable
DELETE /api/team/{userId}           -> remove permanently

There is no multi-tenancy in this app -- every row in `users` already IS the
one workspace's member list (app/db/models/user.py). The earliest-created
user is the de-facto owner and the seat ceiling comes from *their* License
row, since licenses are per-user in this schema and there's no separate
workspace/org table to hang a shared one off of.
"""

import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_app_db, get_current_user
from app.core.audit import client_ip, log_audit_event
from app.core.security import hash_password
from app.db.models.license import License
from app.db.models.user import User

router = APIRouter()

ROLES = ("owner", "operator", "viewer")

# Role matrix is a static reference, not data-bound -- Figma's own frame
# renders the identical ✓/— pattern regardless of any backend state
# (SCREENLIST.md §16: no per-workspace capability customization exists).
ROLE_MATRIX = [
    {"capability": "Run and view jobs", "owner": True, "operator": True, "viewer": True},
    {
        "capability": "Create and edit jobs, schedules, templates",
        "owner": True, "operator": True, "viewer": False,
    },
    {
        "capability": "Manage proxies and suppression rules",
        "owner": True, "operator": True, "viewer": False,
    },
    {
        "capability": "Manage integrations and API keys",
        "owner": True, "operator": False, "viewer": False,
    },
    {
        "capability": "Invite, remove and change team roles",
        "owner": True, "operator": False, "viewer": False,
    },
    {"capability": "View billing and audit log", "owner": True, "operator": False, "viewer": False},
]

# "Online now" threshold for the member table's LAST SEEN column.
ONLINE_WITHIN = timedelta(minutes=2)


class InviteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role: str = Field(pattern="^(owner|operator|viewer)$")


class RoleChangeRequest(BaseModel):
    role: str = Field(pattern="^(owner|operator|viewer)$")


def _owner(db: Session) -> User:
    """The earliest-created user -- see module docstring."""
    return db.execute(select(User).order_by(User.created_at.asc()).limit(1)).scalar_one()


def _require_team_admin(user: User = Depends(get_current_user)) -> User:
    """Only Owner may invite/remove/change roles (role matrix: 'Invite,
    remove and change team roles' is Owner-only)."""
    if user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the workspace owner can manage team members",
        )
    return user


def _member_dict(u: User) -> dict:
    if u.disabled_at is not None:
        status_ = "disabled"
    else:
        status_ = "active"
    # "Online now" is the one label that genuinely needs the server clock (the
    # 2-minute freshness window); every other case ("3h ago", "9d ago") is
    # plain relative-time math the frontend already does elsewhere (e.g.
    # Integrations.tsx), so it's computed there from the raw lastSeenAt
    # instead of duplicating a date-formatting library's worth of logic here.
    online_now = u.last_seen_at is not None and datetime.utcnow() - u.last_seen_at < ONLINE_WITHIN
    return {
        "id": str(u.id),
        "email": u.email,
        "role": u.role,
        "status": status_,
        "lastSeenAt": u.last_seen_at.isoformat() if u.last_seen_at else None,
        "onlineNow": online_now,
    }


@router.get("/")
def get_team(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    members = db.execute(select(User).order_by(User.created_at.asc())).scalars().all()
    owner = _owner(db)
    license_ = db.execute(
        select(License).where(License.user_id == owner.id).order_by(License.expires_at.desc())
    ).scalars().first()
    seats = license_.seats if license_ else 0
    # A disabled/removed member frees their seat -- Figma's own seat-limit
    # banner says "remove a member ... to invite more", which only holds if
    # seat usage counts active members, not every row that's ever existed.
    active_count = sum(1 for m in members if m.disabled_at is None)
    return {
        "roleMatrix": ROLE_MATRIX,
        "seats": {"used": active_count, "total": seats},
        "members": [_member_dict(m) for m in members],
    }


@router.post("/invite", status_code=status.HTTP_201_CREATED)
def invite_member(
    request: Request,
    payload: InviteRequest,
    admin: User = Depends(_require_team_admin),
    db: Session = Depends(get_app_db),
) -> dict:
    owner = _owner(db)
    license_ = db.execute(
        select(License).where(License.user_id == owner.id).order_by(License.expires_at.desc())
    ).scalars().first()
    seats = license_.seats if license_ else 0
    active_count = sum(1 for u in db.execute(select(User)).scalars().all() if u.disabled_at is None)
    if active_count >= seats:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seats are full — remove a member or upgrade your license to invite more",
        )

    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already a member")

    # No mailer/self-signup exists anywhere in this app (see login screen spec:
    # "no signup, accounts via CLI") -- so "Send Invite" provisions the account
    # directly and hands back a one-time temp password, the same shape as the
    # API Keys screen's one-time-reveal (never returned again after this call).
    temp_password = secrets.token_urlsafe(9)
    new_user = User(
        email=payload.email,
        password_hash=hash_password(temp_password),
        role=payload.role,
    )
    db.add(new_user)
    db.flush()

    if license_ is not None:
        db.add(License(
            user_id=new_user.id,
            plan=license_.plan,
            seats=license_.seats,
            expires_at=license_.expires_at,
        ))
    log_audit_event(
        db, actor_email=admin.email, action="team.member_invited",
        target=f"{new_user.email} ({new_user.role})", ip_address=client_ip(request),
    )
    db.commit()

    return {**_member_dict(new_user), "tempPassword": temp_password}


@router.patch("/{user_id}/role")
def change_role(
    request: Request,
    user_id: str,
    payload: RoleChangeRequest,
    admin: User = Depends(_require_team_admin),
    db: Session = Depends(get_app_db),
) -> dict:
    target = _get_member(db, user_id)
    if target.id == admin.id and payload.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot demote yourself away from Owner",
        )
    before_role = target.role
    target.role = payload.role
    log_audit_event(
        db, actor_email=admin.email, action="team.role_changed", target=target.email,
        ip_address=client_ip(request),
        before_after={"before": {"role": before_role}, "after": {"role": target.role}},
    )
    db.commit()
    return _member_dict(target)


@router.post("/{user_id}/disable")
def disable_member(
    request: Request,
    user_id: str,
    admin: User = Depends(_require_team_admin),
    db: Session = Depends(get_app_db),
) -> dict:
    target = _get_member(db, user_id)
    if target.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot disable your own account",
        )
    target.disabled_at = datetime.utcnow()
    log_audit_event(
        db, actor_email=admin.email, action="team.member_disabled", target=target.email,
        ip_address=client_ip(request),
    )
    db.commit()
    return _member_dict(target)


@router.post("/{user_id}/enable")
def enable_member(
    request: Request,
    user_id: str,
    admin: User = Depends(_require_team_admin),
    db: Session = Depends(get_app_db),
) -> dict:
    target = _get_member(db, user_id)
    target.disabled_at = None
    log_audit_event(
        db, actor_email=admin.email, action="team.member_enabled", target=target.email,
        ip_address=client_ip(request),
    )
    db.commit()
    return _member_dict(target)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    request: Request,
    user_id: str,
    admin: User = Depends(_require_team_admin),
    db: Session = Depends(get_app_db),
) -> None:
    """Revokes access permanently rather than deleting the row: users.id is
    referenced by jobs/schedules/templates/suppression_entries/licenses
    (created_by / owner_id FKs), so a hard delete would either 500 on the FK
    constraint or cascade-erase that member's real work history. Same
    end-state as disable (blocks login), but the intent is permanent --
    unlike disable, there is no `enable` path back for a removed member."""
    target = _get_member(db, user_id)
    if target.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot remove your own account",
        )
    target.disabled_at = datetime.utcnow()
    log_audit_event(
        db, actor_email=admin.email, action="team.member_removed", target=target.email,
        ip_address=client_ip(request),
    )
    db.commit()


def _get_member(db: Session, user_id: str) -> User:
    try:
        target_uuid = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid user id",
        ) from exc
    target = db.get(User, target_uuid)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member not found")
    return target
