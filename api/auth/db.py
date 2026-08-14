"""Identity/session database layer -- isolated from the image-processing
pipeline entirely. Nothing in engine/ or api/detectors.py touches this
module, and this module never touches an uploaded image.

DATABASE_URL controls the target: unset defaults to a local SQLite file
(./pulli_auth.db) so local development needs zero setup -- no Postgres
install required to run `pytest` or the dev server. Point DATABASE_URL
at a real PostgreSQL instance in production (see docs/DEPLOYMENT.md);
the code path is identical either way since it's plain SQLAlchemy Core/ORM,
not SQLite-specific.

No migration tool (Alembic) is wired up -- `Base.metadata.create_all()`
at startup is sufficient for this stage's two small tables and keeps the
dependency surface minimal, per this task's explicit "do not introduce
unnecessary infrastructure" instruction. Worth adding Alembic before the
schema grows past what create_all can safely handle (it never alters
existing tables, only creates missing ones).
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./pulli_auth.db")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

_is_sqlite = DATABASE_URL.startswith("sqlite")
# See api/db/database.py's matching comment: sqlite3's 5s default lock
# timeout produced real 500s under concurrent writers in testing.
_connect_args = {"check_same_thread": False, "timeout": 30} if _is_sqlite else {}

# NOTE: in production this module and api/db/database.py read the SAME
# DATABASE_URL and each open their OWN SQLAlchemy engine/pool against it
# (two logically separate table sets -- users/user_sessions here,
# patterns/generations/etc. there -- sharing one physical Postgres
# instance is a normal, supported pattern, not a bug). It means the
# TOTAL connection budget this process can open is the sum of both
# pools, not just this one -- see docs/DEPLOYMENT.md's connection-count
# note before sizing DB_POOL_SIZE/DB_MAX_OVERFLOW against a managed
# Postgres plan's max_connections limit. Smaller default pool here since
# auth traffic (login/register/session-check) is far lighter than
# generation traffic.
_pool_kwargs = (
    {}
    if _is_sqlite
    else {
        "pool_size": int(os.environ.get("AUTH_DB_POOL_SIZE", "3")),
        "max_overflow": int(os.environ.get("AUTH_DB_MAX_OVERFLOW", "5")),
        "pool_timeout": int(os.environ.get("DB_POOL_TIMEOUT_SECONDS", "30")),
        "pool_recycle": int(os.environ.get("DB_POOL_RECYCLE_SECONDS", "1800")),
        "pool_pre_ping": True,
    }
)

engine = create_engine(DATABASE_URL, connect_args=_connect_args, **_pool_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

if _is_sqlite:
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """SQLite (local dev): create tables that don't exist yet, every
    startup -- safe and convenient for a throwaway local file.

    Postgres (production): does NOT run `create_all()`, for the same
    reason api/db/database.py's init_db() doesn't (see its docstring).
    The `users`/`user_sessions` schema is NOT currently under Alembic
    (alembic/env.py only manages api.db.database.Base's tables -- a
    deliberate, documented scope decision, not an oversight: this is a
    2-table schema that has not needed a real ALTER since it was
    introduced). Before the first production deploy, create these two
    tables once with:
        DATABASE_URL=<prod url> python -c "from api.auth.db import init_db; init_db()"
    and track any future change to this schema as a real migration (fold
    it into the Alembic setup at that point) rather than hand-editing
    the production table."""
    from api.auth import models  # noqa: F401  -- registers models on Base.metadata

    if DATABASE_URL.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    else:
        import sys

        print(
            "[pulli-api] Postgres DATABASE_URL detected for auth DB -- skipping "
            "create_all(). See api/auth/db.py's init_db() docstring for the "
            "one-time production setup command.",
            file=sys.stderr,
        )


def get_db():
    """FastAPI dependency: yields a request-scoped session, always closed."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
