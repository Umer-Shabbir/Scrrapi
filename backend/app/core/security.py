"""JWT auth + password hashing + TOTP helpers.

Replaces the legacy title-bar ValidateRegistration check with a real server-side license
gate — see app/api/routers/auth.py and the `licenses` table in app/db/models/license.py.
"""

from datetime import UTC, datetime, timedelta

import bcrypt
import pyotp
from jose import jwt

from app.core.config import get_settings

settings = get_settings()

# Distinguishes a TOTP-pending token from a real access token so /api/auth/me
# can't be reached with one -- it only proves "password was correct".
TOTP_PENDING_SCOPE = "totp_pending"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def create_totp_pending_token(subject: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.totp_pending_token_minutes)
    payload = {"sub": subject, "exp": expire, "scope": TOTP_PENDING_SCOPE}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_totp_pending_token(token: str) -> str:
    """Returns the user id, or raises jose.JWTError for an invalid/expired/wrong-scope token."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("scope") != TOTP_PENDING_SCOPE:
        raise jwt.JWTError("not a totp-pending token")
    return payload["sub"]


def verify_totp_code(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)
