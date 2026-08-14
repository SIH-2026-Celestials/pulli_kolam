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

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables that don't exist yet. Safe to call on every startup."""
    from api.auth import models  # noqa: F401  -- registers models on Base.metadata

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yields a request-scoped session, always closed."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
