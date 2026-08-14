"""Password hashing and session-cookie signing.

Password hashing: bcrypt directly (the `bcrypt` package, not passlib --
passlib's bcrypt backend has had version-compatibility warnings with
recent bcrypt releases; calling bcrypt's own hashpw/checkpw is simpler
and equally well-established).

Session cookies are server-side-session tokens (opaque random values,
looked up in `user_sessions`), not JWTs -- there is nothing to decode,
so AUTH_SECRET's job is narrower than a JWT signing key: it HMAC-signs
the token so a cookie value can be rejected as tampered/forged BEFORE
it ever reaches a database query, without which AUTH_SECRET would be
declared in .env.example but never actually used anywhere.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets

import bcrypt

MIN_PASSWORD_LENGTH = 8

_AUTH_SECRET_ENV = "AUTH_SECRET"
_DEV_FALLBACK_SECRET = "dev-only-insecure-secret-do-not-use-in-production"


def _auth_secret() -> bytes:
    secret = os.environ.get(_AUTH_SECRET_ENV)
    if not secret:
        # Fails loud in anything that isn't clearly local dev, rather than
        # silently signing every session with a well-known string in prod.
        if os.environ.get("COOKIE_SECURE", "").lower() in ("1", "true", "yes"):
            raise RuntimeError(
                f"{_AUTH_SECRET_ENV} must be set when COOKIE_SECURE is enabled (production mode)."
            )
        secret = _DEV_FALLBACK_SECRET
    return secret.encode("utf-8")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed/foreign hash -- never let a hash-format error propagate
        # as an exception that could turn into a 500 leaking implementation
        # details; treat it as "does not match."
        return False


def validate_password(password: str) -> str | None:
    """Returns an error message, or None if the password is acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    return None


def generate_session_token() -> str:
    """32 bytes of CSPRNG randomness, url-safe -- this is the value stored
    in `user_sessions.token`, never the raw cookie value (see below)."""
    return secrets.token_urlsafe(32)


def sign_session_cookie(token: str) -> str:
    sig = hmac.new(_auth_secret(), token.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{token}.{sig}"


def verify_session_cookie(cookie_value: str) -> str | None:
    """Returns the session token if the signature is valid, else None.
    Constant-time comparison via hmac.compare_digest."""
    if not cookie_value or "." not in cookie_value:
        return None
    token, _, sig = cookie_value.rpartition(".")
    if not token or not sig:
        return None
    expected = hmac.new(_auth_secret(), token.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    return token
