"""POST /register, POST /login, POST /logout, GET /me -- mounted at
/api/v1/auth by api/main.py. Sessions are server-side (api/auth/service.py
+ the user_sessions table); the cookie only carries a signed opaque
token, never user data, and is never readable from JavaScript (HttpOnly)."""

from __future__ import annotations

import os

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session as DbSession

from api.auth.db import get_db
from api.auth.dependencies import SESSION_COOKIE_NAME, get_current_user
from api.auth.models import User
from api.auth.schemas import LoginRequest, RegisterRequest, UserPublic
from api.auth.security import sign_session_cookie, validate_password, verify_session_cookie
from api.auth.service import (
    SESSION_LIFETIME,
    EmailAlreadyRegistered,
    InvalidCredentials,
    _aware,
    authenticate_user,
    create_session,
    register_user,
    revoke_session,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "").lower() in ("1", "true", "yes")
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN") or None
COOKIE_SAMESITE = "lax"


def _to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=_aware(user.created_at).isoformat(),
        last_login_at=_aware(user.last_login_at).isoformat() if user.last_login_at else None,
    )


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=sign_session_cookie(token),
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path="/",
    )


@router.post("/register", response_model=UserPublic, status_code=201)
def register(body: RegisterRequest, response: Response, db: DbSession = Depends(get_db)):
    password_error = validate_password(body.password)
    if password_error:
        raise HTTPException(status_code=400, detail=password_error)

    try:
        user = register_user(db, email=body.email, password=body.password, display_name=body.display_name)
    except EmailAlreadyRegistered:
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from None

    session = create_session(db, user)
    _set_session_cookie(response, session.token)
    return _to_public(user)


@router.post("/login", response_model=UserPublic)
def login(body: LoginRequest, response: Response, db: DbSession = Depends(get_db)):
    try:
        user = authenticate_user(db, email=body.email, password=body.password)
    except InvalidCredentials:
        raise HTTPException(status_code=401, detail="Incorrect email or password.") from None

    session = create_session(db, user)
    _set_session_cookie(response, session.token)
    return _to_public(user)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: DbSession = Depends(get_db),
    pulli_session: str | None = Cookie(default=None),
):
    # Cookie is read directly (not via get_current_user) so logging out
    # with an already-expired/invalid cookie still clears it client-side
    # instead of 401ing on the one request whose entire job is to clean up.
    token = verify_session_cookie(pulli_session) if pulli_session else None
    if token:
        revoke_session(db, token)
    response.delete_cookie(key=SESSION_COOKIE_NAME, domain=COOKIE_DOMAIN, path="/")
    return Response(status_code=204)


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)):
    return _to_public(current_user)
