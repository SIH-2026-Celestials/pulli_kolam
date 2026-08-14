# Deployment

Covers the two things this project actually has running processes for:
the FastAPI backend (`api/`, including `api/auth/`) and the Vite/React
frontend (`frontend/frontend/`). There is no Docker setup in this repo
as of this document — nothing here assumes one.

## Environment variables

Copy `.env.example` to `.env` in the repo root for local development
(`api/main.py` loads it automatically via `python-dotenv`; production
deployments should set these through the hosting platform's env config
instead of shipping a `.env` file).

| Variable | Local dev | Production |
|---|---|---|
| `DATABASE_URL` | unset → local SQLite file `./pulli_auth.db`, zero setup | `postgresql+psycopg2://user:pass@host:5432/dbname` — install `psycopg2-binary` |
| `AUTH_SECRET` | unset → an insecure hardcoded dev fallback is used (logged nowhere, but not a secret) | **required** — the app refuses to start signing sessions with the dev fallback once `COOKIE_SECURE=true`. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `COOKIE_SECURE` | `false` (or unset) | `true` — **requires HTTPS**; browsers silently drop `Secure` cookies sent over plain HTTP, which would make login appear to "not work" |
| `COOKIE_DOMAIN` | unset | only set if the API and frontend share a parent domain (e.g. `.pulli.example`) |
| `CORS_ORIGINS` | unset → permissive `http://localhost:<any port>` / `http://127.0.0.1:<any port>` regex | comma-separated exact origins, e.g. `https://app.pulli.example` |

## Local development

```bash
pip install -r requirements.txt
cp .env.example .env          # optional locally; defaults work without it
KMP_DUPLICATE_LIB_OK=TRUE uvicorn api.main:app --reload --port 8000

cd frontend/frontend
npm install
npm run dev
```

The frontend's API client (`frontend/frontend/src/lib/api/client.js`)
defaults to `http://localhost:8000`; override with `VITE_API_BASE_URL`
if the backend runs elsewhere.

On startup, `api/main.py` calls `api/auth/db.py:init_db()`, which creates
the `users`/`user_sessions` tables if they don't already exist (plain
`Base.metadata.create_all()` — there is no migration tool wired up yet;
see `api/auth/db.py`'s module docstring for why that's an intentional,
minimal choice for this stage, and add Alembic before altering an
existing table's shape, since `create_all()` only ever creates missing
tables and never migrates existing ones).

## Database migration

There is no migration tool in this project yet. The two auth tables are
created via `create_all()` on startup, which is safe as long as you only
ever *add* new tables or columns with server-side defaults — it will not
alter an existing column's type or add a `NOT NULL` column to a table
that already has rows. If you need an actual schema migration (renaming
a column, adding a required field to `users`, etc.), introduce Alembic
at that point rather than hand-editing production tables.

## Cookies in production

The session cookie (`pulli_session`, set by `api/auth/router.py`) is
`HttpOnly` always, and `Secure` + `SameSite=Lax` when `COOKIE_SECURE=true`.
Concretely:

- Serve the frontend and backend over HTTPS in production. A `Secure`
  cookie set over HTTP is silently dropped by the browser — this is the
  most common way "login works locally but not in prod" happens.
- If the frontend and API are on different subdomains of the same parent
  domain, set `COOKIE_DOMAIN` to the shared parent (e.g. `.pulli.example`)
  so the cookie is sent to both. Leave it unset for a single-domain
  deployment or for local development.
- `CORS_ORIGINS` must list the frontend's exact production origin(s) —
  `allow_credentials=True` (required for the cookie to work cross-origin
  at all) means the CORS spec forbids a wildcard `*` origin, so an unset
  `CORS_ORIGINS` in a non-localhost deployment will simply not work; the
  regex fallback in `api/main.py` only matches `localhost`/`127.0.0.1`.

## Secret generation

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use a different value per environment. Rotating `AUTH_SECRET` invalidates
every existing session cookie's signature (all logged-in users are signed
out) but does not affect stored password hashes.

## Rollback

- **Backend code rollback**: standard — redeploy the previous revision.
  The auth tables' shape hasn't changed across this feature's commits, so
  no data migration is needed to roll back.
- **Database rollback**: since there's no migration tool, "rollback" for
  the auth tables means restoring a database backup if you need to undo
  data changes (not schema changes — nothing here alters existing
  columns). Take a backup before any manual schema change.
- **If `AUTH_SECRET` is rotated by mistake**: not reversible from the old
  value alone (it isn't stored anywhere but the env config) — restore the
  previous secret from wherever it was originally generated/stored (e.g.
  your secrets manager's history) rather than regenerating a new one, or
  accept that all users need to log in again.

## What this deployment note does NOT cover

There is no Docker/container setup, no CI/CD pipeline, and no managed
database provisioning script in this repository. Those would need to be
built separately; this document only covers the environment variables
and cookie/CORS behavior the existing code actually depends on.
