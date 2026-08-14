"""Auth business logic, kept separate from the FastAPI route layer
(api/auth/router.py) so the request/response mechanics don't get tangled
up with the actual rules (uniqueness, session lifetime, etc.)."""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from api.auth.models import User, UserSession
from api.auth.security import generate_session_token, hash_password, verify_password

SESSION_LIFETIME = datetime.timedelta(days=14)


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _aware(dt: datetime.datetime) -> datetime.datetime:
    """SQLite (this project's local-dev default DB) does not actually
    preserve timezone info through a round-trip even with
    `DateTime(timezone=True)` -- it stores an ISO string and reads back a
    naive datetime, unlike PostgreSQL. Comparing that naive value against
    `_utcnow()`'s aware value raises TypeError. Every datetime written
    here is UTC by construction (`_utcnow()`), so a naive value read back
    is safely assumed to already be UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def get_user_by_email(db: DbSession, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def register_user(db: DbSession, *, email: str, password: str, display_name: str) -> User:
    if get_user_by_email(db, email) is not None:
        raise EmailAlreadyRegistered(email)
    user = User(email=email, password_hash=hash_password(password), display_name=display_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: DbSession, *, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        # Same error for "no such user" and "wrong password" -- does not
        # reveal which part was wrong (standard practice, avoids account
        # enumeration via the login endpoint).
        raise InvalidCredentials()
    user.last_login_at = _utcnow()
    db.commit()
    db.refresh(user)
    return user


def create_session(db: DbSession, user: User) -> UserSession:
    session = UserSession(
        token=generate_session_token(),
        user_id=user.id,
        expires_at=_utcnow() + SESSION_LIFETIME,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_user_by_session_token(db: DbSession, token: str) -> User | None:
    session = db.execute(select(UserSession).where(UserSession.token == token)).scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        return None
    if _aware(session.expires_at) < _utcnow():
        return None
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    return user


def revoke_session(db: DbSession, token: str) -> None:
    session = db.execute(select(UserSession).where(UserSession.token == token)).scalar_one_or_none()
    if session is not None and session.revoked_at is None:
        session.revoked_at = _utcnow()
        db.commit()
