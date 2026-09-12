"""Auth endpoints: login, TOTP verification, license status, account/usage."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_app_db, get_current_user
from app.core.audit import client_ip, log_audit_event
from app.core.config import get_settings
from app.core.plans import quota_for_plan
from app.core.security import (
    create_access_token,
    create_totp_pending_token,
    decode_totp_pending_token,
    verify_password,
    verify_totp_code,
)
from app.db.models.export import Export
from app.db.models.license import License
from app.db.models.result import Result
from app.db.models.user import User

router = APIRouter()
settings = get_settings()

# Mirrors FastAPI(version=...) in app.main and app.api.routers.system's own
# _API_VERSION -- duplicated as a literal rather than imported from main to
# avoid a circular import (main imports this router). Keep all three in sync.
_API_VERSION = "0.1.0"

# How many past calendar months USAGE HISTORY looks back for -- a ceiling on
# the query range, not a promise that data exists that far back. Real months
# with zero jobs (including every month before this install's first job) are
# simply absent from the response rather than shown as fabricated zero bars;
# see `read_account`'s docstring.
USAGE_HISTORY_MONTHS = 12


@router.post("/login")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_app_db),
) -> dict:
    ip = client_ip(request)
    user = db.query(User).filter(User.email == form_data.username).first()

    if user is not None and user.locked_until is not None:
        if user.locked_until > datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={
                    "code": "account_locked",
                    "message": (
                        f"Account locked — {settings.login_max_failed_attempts} failed attempts"
                    ),
                    "locked_until": user.locked_until.isoformat(),
                },
            )
        # Cooldown elapsed -- clear the lock so this attempt is judged normally.
        user.locked_until = None
        user.failed_login_attempts = 0

    if user is None or not verify_password(form_data.password, user.password_hash):
        if user is not None:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.login_max_failed_attempts:
                user.locked_until = datetime.utcnow() + timedelta(
                    minutes=settings.login_lockout_minutes
                )
        log_audit_event(
            db,
            actor_email=form_data.username,
            action="auth.login_failed",
            ip_address=ip,
            success=False,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Incorrect email or password"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.failed_login_attempts = 0
    log_audit_event(db, actor_email=user.email, action="auth.login_succeeded", ip_address=ip)
    db.commit()

    if user.totp_secret:
        return {
            "totp_required": True,
            "login_token": create_totp_pending_token(subject=str(user.id)),
        }

    access_token = create_access_token(subject=str(user.id))
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login/totp")
def verify_totp(
    login_token: str = Body(embed=True),
    code: str = Body(embed=True),
    db: Session = Depends(get_app_db),
) -> dict:
    try:
        user_id = decode_totp_pending_token(login_token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_login_token", "message": "Sign in again"},
        ) from exc

    user = db.get(User, user_id)
    if user is None or not user.totp_secret or not verify_totp_code(user.totp_secret, code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_totp_code", "message": "Incorrect code"},
        )

    access_token = create_access_token(subject=str(user.id))
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "complianceAckAt": user.compliance_ack_at.isoformat() if user.compliance_ack_at else None,
    }


# Dotted verb.noun action per pane, matching every other audit action's
# convention (settings.updated, team.member_invited, ...). Three distinct
# actions rather than one "compliance.acknowledged" with a pane number in
# before_after -- each pane's own copy says "confirming writes a timestamped
# row," so a reviewer reading the Audit Log should see three separate rows,
# not one row with buried detail.
_COMPLIANCE_PANE_ACTIONS = {
    1: "compliance.data_collection_acknowledged",
    2: "compliance.robots_txt_acknowledged",
    3: "compliance.obligations_acknowledged",
}


@router.post("/compliance/ack")
def acknowledge_compliance(
    request: Request,
    pane: int = Body(embed=True, ge=1, le=3),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """One call per compliance pane (SCREENLIST.md §22's "I UNDERSTAND" /
    "START TOUR" buttons). `compliance_ack_at` is only set on pane 3 -- panes
    1-2 write their own audit row but don't yet mark the flow complete, so a
    user who closes the tab between pane 1 and 3 sees the modal again from
    pane 1 next time rather than being treated as done.
    """
    log_audit_event(
        db,
        actor_email=user.email,
        action=_COMPLIANCE_PANE_ACTIONS[pane],
        ip_address=client_ip(request),
    )
    if pane == 3:
        user.compliance_ack_at = datetime.utcnow()
    db.commit()
    ack_at = user.compliance_ack_at
    return {"complianceAckAt": ack_at.isoformat() if ack_at else None}


@router.get("/license")
def license_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """Replaces legacy ValidateRegistration title-bar check."""
    license_ = (
        db.query(License)
        .filter(License.user_id == user.id)
        .order_by(License.expires_at.desc())
        .first()
    )
    if license_ is None:
        return {"plan": None, "seats": 0, "expiresAt": None, "active": False}

    return {
        "plan": license_.plan,
        "seats": license_.seats,
        "expiresAt": license_.expires_at.isoformat(),
        "active": license_.expires_at > datetime.utcnow(),
    }


def _month_start(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_month(dt: datetime) -> datetime:
    return (dt.replace(day=28) + timedelta(days=4)).replace(day=1)


@router.get("/account")
def read_account(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_app_db),
) -> dict:
    """Backs the Account & Billing screen (SCREENLIST.md §21) -- one fetch for
    signed-in info, license, quota, and usage history, same shape as the
    screen's four panels.

    QUOTA and USAGE HISTORY are genuinely new this cycle (no prior endpoint
    computed either). Installation-wide, not per-user, like every other
    cross-cutting count in this app (concurrency, retention) -- this is a
    single-tenant app (see app/db/models/user.py's "no multi-tenancy" note),
    so "this account's usage" and "this installation's usage" are the same
    thing, and Result/Export rows have no user_id to scope by even if they
    weren't.

    USAGE HISTORY intentionally does not pad to a fixed 12 bars: it reports
    real per-month counts for whichever of the last `USAGE_HISTORY_MONTHS`
    calendar months actually have at least one scraped result, oldest first.
    A freshly-installed instance returns a short list (or an empty one), not
    11 fabricated zero-months -- there is no organic way for a new install to
    have real history further back than its own first job.
    """
    license_ = (
        db.query(License)
        .filter(License.user_id == user.id)
        .order_by(License.expires_at.desc())
        .first()
    )
    plan = license_.plan if license_ else None
    quota = quota_for_plan(plan)

    now = datetime.utcnow()
    month_start = _month_start(now)
    next_month_start = _add_month(month_start)

    places_this_month = (
        db.scalar(select(func.count()).select_from(Result).where(Result.scraped_at >= month_start))
        or 0
    )
    exports_this_month = (
        db.scalar(
            select(func.count())
            .select_from(Export)
            .where(Export.generated_at.is_not(None), Export.generated_at >= month_start)
        )
        or 0
    )

    history_floor = month_start
    for _ in range(USAGE_HISTORY_MONTHS - 1):
        history_floor = _month_start(history_floor - timedelta(days=1))

    rows = (
        db.execute(select(Result.scraped_at).where(Result.scraped_at >= history_floor))
        .scalars()
        .all()
    )
    counts: dict[str, int] = {}
    cursor = history_floor
    while cursor < next_month_start:
        counts[cursor.strftime("%Y-%m")] = 0
        cursor = _add_month(cursor)
    for scraped_at in rows:
        key = scraped_at.strftime("%Y-%m")
        if key in counts:
            counts[key] += 1
    usage_history = [
        {"month": month, "places": count} for month, count in counts.items() if count > 0
    ]

    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "twoFactorEnrolled": user.totp_secret is not None,
        },
        "apiVersion": _API_VERSION,
        "license": {
            "plan": plan,
            "seats": license_.seats if license_ else 0,
            "expiresAt": license_.expires_at.isoformat() if license_ else None,
            "active": bool(license_ and license_.expires_at > now),
        },
        "quota": {
            "placesThisMonth": places_this_month,
            "placesLimit": quota.places_per_month,
            "exportsThisMonth": exports_this_month,
            "exportsLimit": quota.exports_per_month,
            "resetsAt": next_month_start.isoformat(),
        },
        "usageHistory": usage_history,
    }
