import pyotp
import pytest
from jose import JWTError

from app.core.security import (
    create_totp_pending_token,
    decode_totp_pending_token,
    hash_password,
    verify_password,
    verify_totp_code,
)


def test_hash_password_produces_verifiable_hash() -> None:
    hashed = hash_password("correct-horse-battery-staple")

    assert hashed != "correct-horse-battery-staple"
    assert verify_password("correct-horse-battery-staple", hashed)


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("correct-horse-battery-staple")

    assert not verify_password("wrong-password", hashed)


def test_hash_password_is_salted() -> None:
    # Same input, two calls -> different hashes (bcrypt salt), both still verify.
    first = hash_password("same-password")
    second = hash_password("same-password")

    assert first != second
    assert verify_password("same-password", first)
    assert verify_password("same-password", second)


def test_verify_totp_code_accepts_the_current_code() -> None:
    secret = pyotp.random_base32()
    assert verify_totp_code(secret, pyotp.TOTP(secret).now())


def test_verify_totp_code_rejects_a_wrong_code() -> None:
    secret = pyotp.random_base32()
    wrong = str((int(pyotp.TOTP(secret).now()) + 1) % 1_000_000).zfill(6)
    assert not verify_totp_code(secret, wrong)


def test_totp_pending_token_round_trips_the_subject() -> None:
    token = create_totp_pending_token(subject="user-123")
    assert decode_totp_pending_token(token) == "user-123"


def test_totp_pending_token_is_not_a_bearer_token() -> None:
    """A normal access token has no `scope` claim, so it must not decode as pending --
    otherwise a stolen session token could skip the 2FA step entirely."""
    from app.core.security import create_access_token

    token = create_access_token(subject="user-123")
    with pytest.raises(JWTError):
        decode_totp_pending_token(token)
