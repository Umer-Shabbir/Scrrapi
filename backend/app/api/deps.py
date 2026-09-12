"""Shared FastAPI dependencies: DB sessions, current-user/license auth guard."""

import hashlib
import ipaddress
import uuid
from collections.abc import Generator
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.api_key import APIKeyHeader
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models.api_key import ApiKey
from app.db.models.license import License
from app.db.models.user import User
from app.db.session import AppSessionLocal, GeoSessionLocal

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

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


def get_api_key(
    request: Request,
    key_str: str | None = Depends(api_key_header),
    db: Session = Depends(get_app_db),
) -> ApiKey:
    """Verifies the X-API-Key header against the api_keys table."""
    if not key_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    key_hash = hashlib.sha256(key_str.encode()).hexdigest()
    api_key_obj = (
        db.query(ApiKey).filter(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None)).first()
    )

    if not api_key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    now = datetime.utcnow()
    if api_key_obj.expires_at and api_key_obj.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
        )

    if api_key_obj.ip_allowlist:
        client_ip = request.client.host if request.client else None
        if client_ip:
            allowed = False
            try:
                client_ip_obj = ipaddress.ip_address(client_ip)
                for block in api_key_obj.ip_allowlist.split(","):
                    block = block.strip()
                    if not block:
                        continue
                    try:
                        if client_ip_obj in ipaddress.ip_network(block):
                            allowed = True
                            break
                    except ValueError:
                        continue
            except ValueError:
                pass
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="IP address not allowed for this API key",
                )

    api_key_obj.last_used_at = now
    # Handle usage string -> json -> string if necessary, but assuming JSON type
    usage = list(api_key_obj.usage_daily or [])
    if usage:
        usage[-1] += 1
    api_key_obj.usage_daily = usage

    db.commit()
    return api_key_obj


def get_current_user_or_api_key(
    request: Request,
    token: str | None = Depends(OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)),
    api_key_str: str | None = Depends(api_key_header),
    db: Session = Depends(get_app_db),
) -> User:
    """Authenticates via JWT token OR X-API-Key header, returning the User object for either."""
    if token:
        return get_current_user(token, db)
    elif api_key_str:
        api_key_obj = get_api_key(request=request, key_str=api_key_str, db=db)
        user = db.get(User, api_key_obj.owner_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key owner",
            )
        if user.disabled_at is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "account_disabled", "message": "This account has been disabled"},
            )
        return user
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
