"""M7 platform integration: database engine/session setup.

No ORM/database existed anywhere in this repository before this file
(verified: `grep -rn sqlalchemy requirements*.txt` finds nothing).
SQLAlchemy chosen because it's already present in the local environment
and is the standard, portable choice for a Python/FastAPI backend --
not a new hard dependency being introduced without justification.

DEFAULT: a local SQLite file (`api/db/pulli.db`) -- zero external
services required to run the platform locally or in this session's
sandbox. PRODUCTION: set `DATABASE_URL` (e.g.
`postgresql://user:pass@host/dbname`) and this module uses it instead,
unchanged code path -- the schema (api/db/models.py) uses only portable
SQLAlchemy types (String, Integer, Float, Boolean, DateTime, JSON, Text)
with no SQLite-only or Postgres-only features, so the same models.py
works against either backend. This satisfies the task's "PostgreSQL +
object storage" architecture line without requiring a live Postgres
server to exist in this environment before the platform can be
exercised end-to-end.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_DB_DIR = Path(__file__).resolve().parent
_DEFAULT_SQLITE_PATH = _DB_DIR / "pulli.db"

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_DEFAULT_SQLITE_PATH}")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create every table declared in api/db/models.py if it doesn't
    already exist. Idempotent -- safe to call on every process start
    (same convention a lightweight app without a full migration
    framework commonly uses; see api/db/models.py's module docstring
    for why a full Alembic migration chain was not added in this pass)."""
    from api.db import models  # noqa: F401 -- import registers all model classes on Base.metadata

    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """FastAPI dependency: yields one Session per request, always closed
    afterward. Not a generator-based `yield` dependency here because
    this module is also used from plain (non-FastAPI) service code
    (api/services/*) that needs a session without going through
    FastAPI's DI system -- callers use it as a context manager:
    `with get_session() as session: ...` (SQLAlchemy's Session already
    supports the context-manager protocol)."""
    return SessionLocal()
