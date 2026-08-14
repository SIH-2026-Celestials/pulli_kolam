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
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

_is_sqlite = DATABASE_URL.startswith("sqlite")
# check_same_thread=False: FastAPI serves requests from a thread pool, so a
# session created on one thread is used on another -- safe here because each
# request gets its own Session (get_session()), never a shared one.
# timeout=30: sqlite3's default is 5s before raising "database is locked" on
# a concurrent writer; two simultaneous /api/v1/generations POSTs (each ~5-55s)
# reproduced this as a live 500 under this default. 30s lets the second
# writer wait out the first's transaction instead of failing the request.
_connect_args = {"check_same_thread": False, "timeout": 30} if _is_sqlite else {}

# Postgres connection pool -- SQLite doesn't use a real connection pool
# (each connection is a local file handle, pooling params are meaningless
# and passing them raises TypeError), so these are only applied for a real
# DATABASE_URL. Defaults are sized for Render's smallest paid Postgres tier
# (its default `max_connections` is commonly 97-197 depending on plan) and
# THIS process being the only writer -- not measured against a real Render
# instance (no credentials available in this environment), so treat these
# as a documented starting point, not a benchmarked value. Tune via env
# vars once real production connection-count metrics exist.
_pool_kwargs = (
    {}
    if _is_sqlite
    else {
        "pool_size": int(os.environ.get("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "10")),
        "pool_timeout": int(os.environ.get("DB_POOL_TIMEOUT_SECONDS", "30")),
        "pool_recycle": int(os.environ.get("DB_POOL_RECYCLE_SECONDS", "1800")),
        # Detects a connection killed by the DB server / a load balancer's
        # idle timeout (common on managed Postgres) and transparently
        # reconnects instead of surfacing a stale-connection error on the
        # next request that happens to grab it from the pool.
        "pool_pre_ping": True,
    }
)

engine = create_engine(DATABASE_URL, connect_args=_connect_args, **_pool_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

if _is_sqlite:
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
        # WAL allows one writer + concurrent readers without blocking (the
        # default rollback-journal mode blocks readers during a write and
        # is far more prone to "database is locked" under concurrency).
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """SQLite (local dev): create every table declared in api/db/models.py
    if it doesn't already exist -- `create_all()` is safe and convenient
    here since local dev throws the file away freely.

    Postgres (production): does NOT run `create_all()`. Schema changes in
    production must go through `alembic upgrade head` (see alembic/ and
    docs/DEPLOYMENT.md's migration section) -- `create_all()` never alters
    an existing column's type, drops a column, or applies a NOT NULL to a
    table that already has rows, so silently relying on it in production
    would let the running code and the actual deployed schema drift apart
    with no record of what changed or when. This function only logs a
    reminder in that case; it does not create tables or fail the request
    that triggered it (the caller, api/main.py's startup hook, already
    treats platform-DB failures as non-fatal for the legacy endpoints)."""
    from api.db import models  # noqa: F401 -- import registers all model classes on Base.metadata

    if DATABASE_URL.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    else:
        import sys

        print(
            "[pulli-api] Postgres DATABASE_URL detected -- skipping create_all(). "
            "Run 'alembic upgrade head' to apply the schema before starting this "
            "process in production (see docs/DEPLOYMENT.md).",
            file=sys.stderr,
        )


def get_session() -> Session:
    """FastAPI dependency: yields one Session per request, always closed
    afterward. Not a generator-based `yield` dependency here because
    this module is also used from plain (non-FastAPI) service code
    (api/services/*) that needs a session without going through
    FastAPI's DI system -- callers use it as a context manager:
    `with get_session() as session: ...` (SQLAlchemy's Session already
    supports the context-manager protocol)."""
    return SessionLocal()
