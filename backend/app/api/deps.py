"""Shared FastAPI dependencies: DB sessions, current-user/license auth guard."""

import uuid
from collections.abc import Generator
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models.license import License
from app.db.models.user import User
from app.db.session import AppSessionLocal, GeoSessionLocal

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_app_db() -> Generator[Session, None, None]:
    db = AppSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_geo_db() -> Generator[Session, None, None]:
    db = GeoSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_app_db)
) -> User:
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise CREDENTIALS_EXCEPTION from exc

    subject = payload.get("sub")
    if subject is None:
        raise CREDENTIALS_EXCEPTION

    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise CREDENTIALS_EXCEPTION from exc

    user = db.get(User, user_id)
    if user is None:
        raise CREDENTIALS_EXCEPTION
    if user.disabled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "account_disabled", "message": "This account has been disabled"},
        )
    # Backs the Team & Roles member table's LAST SEEN column -- touched on
    # authenticated requests (not just login) so "Online now" reflects someone
    # actively using the app right now. Throttled to once per 30s per user so
    # this doesn't add a write to every single request.
    now = datetime.utcnow()
    if user.last_seen_at is None or now - user.last_seen_at > timedelta(seconds=30):
        user.last_seen_at = now
        db.commit()
    return user


def require_active_license(
    user: User = Depends(get_current_user), db: Session = Depends(get_app_db)
) -> User:
    """Gate route on an active license. Replaces the legacy title-bar
    ValidateRegistration check with a real server-side license lookup."""
    license_ = (
        db.query(License)
        .filter(License.user_id == user.id)
        .order_by(License.expires_at.desc())
        .first()
    )
    if license_ is None or license_.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": "no_license", "message": "No active license"},
        )
    return user


def authenticate_ws_token(db: Session, token: str) -> User:
    """`get_current_user`'s check, for a WebSocket handshake instead of a normal
    request. Browsers can't set an Authorization header while opening a socket,
    so the caller pulls the token out of a query param and hands it here rather
    than through `Depends(oauth2_scheme)`. Shared by every `WS /api/.../stream`
    endpoint (jobs, system) rather than each keeping its own copy.
    """
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload.get("sub") or "")
    except (JWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        ) from exc

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    return user
