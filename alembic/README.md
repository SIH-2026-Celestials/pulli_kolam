# Migrations

Manages the 9 platform tables declared in `api/db/models.py`
(`api.db.database.Base.metadata`) — patterns, pattern versions, analysis,
verification results, artifacts, generation requests/runs/results, and the
model registry. Does **not** manage `api/auth/`'s `users`/`user_sessions`
tables — see `api/auth/db.py`'s `init_db()` docstring for why that's a
deliberate, separate, documented scope decision.

## Commands

Run from the repository root (`alembic.ini` lives there). `DATABASE_URL` is
the same env var `api/db/database.py` reads — point it at the target
database before running any command below.

```bash
# Apply every pending migration
DATABASE_URL=postgresql+psycopg2://... alembic upgrade head

# Roll back the most recent migration
DATABASE_URL=postgresql+psycopg2://... alembic downgrade -1

# Roll back everything (drops all 9 tables -- destructive, dev/test only)
DATABASE_URL=postgresql+psycopg2://... alembic downgrade base

# After changing api/db/models.py, generate the next migration
DATABASE_URL=postgresql+psycopg2://... alembic revision --autogenerate -m "describe the change"
# then READ the generated file before committing it -- autogenerate is a
# starting point, not a guarantee (it cannot detect every kind of change,
# e.g. a column rename shows up as a drop+add; fix those by hand).
```

Local development (SQLite) does **not** need Alembic — `api/db/database.py`'s
`init_db()` still calls `create_all()` automatically on startup when
`DATABASE_URL` is unset/points at SQLite. Alembic only takes over once
`DATABASE_URL` points at Postgres (see that function's docstring).

## Verified this session

- `alembic revision --autogenerate` against an empty SQLite database
  correctly detected all 9 tables and their indexes from `api/db/models.py`
  with zero manual edits needed.
- `alembic upgrade head` on a fresh database created all 9 tables +
  indexes; `alembic downgrade base` cleanly dropped them back to zero
  (only Alembic's own `alembic_version` bookkeeping table remained).

## Not verified

- This migration has **not** been run against a real PostgreSQL instance
  (no credentials available in this environment). SQLite and Postgres
  render `JSON`/`Boolean`/`DateTime(timezone=True)` slightly differently
  at the storage-engine level even though the SQLAlchemy-level types are
  portable — run `alembic upgrade head` against a real (even a free-tier
  or local Docker) Postgres instance once before trusting it in
  production, per this task's "verified vs. implemented" distinction.
