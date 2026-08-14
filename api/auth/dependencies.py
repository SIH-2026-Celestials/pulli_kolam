"""FastAPI dependencies for auth. `get_current_user` is the only piece
any OTHER router in this project should ever need to import -- and per
this task's Phase 6, nothing does yet: the detector/analyze/reconstruct
endpoints have no user-owned persistent resource, so they stay public.
This dependency exists for when that changes, not to gate anything today."""

from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from api.auth.db import get_db
from api.auth.models import User
from api.auth.security import verify_session_cookie
from api.auth.service import get_user_by_session_token

SESSION_COOKIE_NAME = "pulli_session"


def get_current_user(
    db: DbSession = Depends(get_db),
    pulli_session: str | None = Cookie(default=None),
) -> User:
    token = verify_session_cookie(pulli_session) if pulli_session else None
    user = get_user_by_session_token(db, token) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def get_optional_user(
    db: DbSession = Depends(get_db),
    pulli_session: str | None = Cookie(default=None),
) -> User | None:
    token = verify_session_cookie(pulli_session) if pulli_session else None
    return get_user_by_session_token(db, token) if token else None
