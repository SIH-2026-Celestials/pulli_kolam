"""Tests for /api/v1/auth/*. Uses an isolated in-memory SQLite database
per test (via FastAPI dependency_override on get_db) -- never touches
the real dev DB file (./pulli_auth.db) or requires PostgreSQL."""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from api.auth.db import Base, get_db  # noqa: E402
from api.auth import models  # noqa: E402,F401 -- registers tables on Base.metadata
from api.main import app  # noqa: E402


@pytest.fixture()
def client():
    # StaticPool: a single shared connection for this engine's lifetime --
    # without it, SQLite's `:memory:` gives every new connection (i.e.
    # every request's session) its own empty database, and `users` would
    # only "exist" on the connection create_all() happened to use.
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


VALID_USER = {"email": "test@example.com", "password": "correct-horse-battery", "display_name": "Test User"}


def test_register_success(client):
    r = client.post("/api/v1/auth/register", json=VALID_USER)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "test@example.com"
    assert body["display_name"] == "Test User"
    assert "password" not in body
    assert "password_hash" not in body
    # Session cookie must be set, HttpOnly (not inspectable from JS -- the
    # TestClient's cookie jar doesn't expose HttpOnly-ness directly, but we
    # can confirm the cookie itself was issued).
    assert "pulli_session" in r.cookies


def test_register_duplicate_email_rejected(client):
    client.post("/api/v1/auth/register", json=VALID_USER)
    r = client.post("/api/v1/auth/register", json=VALID_USER)
    assert r.status_code == 409
    assert "password" not in r.text.lower() or "password" in r.json()["error"].lower()  # error message only, no data leak


def test_register_weak_password_rejected(client):
    r = client.post("/api/v1/auth/register", json={**VALID_USER, "password": "short"})
    assert r.status_code == 400


def test_register_invalid_email_rejected(client):
    r = client.post("/api/v1/auth/register", json={**VALID_USER, "email": "not-an-email"})
    assert r.status_code == 422  # pydantic validation error


def test_login_success(client):
    client.post("/api/v1/auth/register", json=VALID_USER)
    client.cookies.clear()
    r = client.post("/api/v1/auth/login", json={"email": VALID_USER["email"], "password": VALID_USER["password"]})
    assert r.status_code == 200
    assert r.json()["email"] == VALID_USER["email"]
    assert "pulli_session" in r.cookies


def test_login_wrong_password_rejected(client):
    client.post("/api/v1/auth/register", json=VALID_USER)
    client.cookies.clear()
    r = client.post("/api/v1/auth/login", json={"email": VALID_USER["email"], "password": "wrong-password-entirely"})
    assert r.status_code == 401
    assert "pulli_session" not in r.cookies


def test_login_unknown_email_rejected_same_as_wrong_password(client):
    r = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever12345"})
    assert r.status_code == 401


def test_me_unauthenticated_returns_401(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_authenticated_returns_user(client):
    client.post("/api/v1/auth/register", json=VALID_USER)
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == VALID_USER["email"]
    assert "password" not in body
    assert "password_hash" not in body


def test_logout_clears_session(client):
    client.post("/api/v1/auth/register", json=VALID_USER)
    assert client.get("/api/v1/auth/me").status_code == 200

    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 204

    # The revoked session must not authenticate a subsequent request even
    # if the (now-stale) cookie is somehow still sent.
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_without_session_does_not_error(client):
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 204


def test_tampered_session_cookie_rejected(client):
    client.post("/api/v1/auth/register", json=VALID_USER)
    real_cookie = client.cookies.get("pulli_session")
    assert real_cookie is not None

    client.cookies.set("pulli_session", real_cookie[:-1] + ("0" if real_cookie[-1] != "0" else "1"))
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_password_hash_never_serialized_anywhere(client):
    r = client.post("/api/v1/auth/register", json=VALID_USER)
    assert "password_hash" not in r.text
    r2 = client.get("/api/v1/auth/me")
    assert "password_hash" not in r2.text


def test_health_and_model_remain_public_no_auth_required(client):
    """Regression guard for Phase 6's rule: public endpoints must not
    accidentally start requiring authentication."""
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/model").status_code == 200


def test_cors_credentials_allowed_for_auth_cookie(client):
    """allow_credentials=True is required for the session cookie to work
    cross-origin at all -- confirm it's actually on, not just declared."""
    r = client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.headers.get("access-control-allow-credentials") == "true"
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
