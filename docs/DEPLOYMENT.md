# PULLI Deployment

This document covers local development, Docker, and production deployment
of the deployable pieces of PULLI today: the React/Vite frontend and the
FastAPI backend (`api/main.py`, including `api/auth/`). See
`docs/DEPLOYMENT_AUDIT.md` for the full architecture audit this document
implements.

There is no queue, object storage, GPU, or background worker anywhere in
this system. Uploaded images are ephemeral: written to a temp file for the
duration of one request and deleted immediately after (`api/main.py`). The
one piece of persistent state is the identity/session database
(`api/auth/`) — by default a local SQLite file, zero setup required; see
section H. Do not deploy infrastructure beyond that unless a real feature
needs it.

---

## A. Local development

### Backend

```bash
pip install -r requirements.txt
cp .env.example .env          # optional locally; defaults work without it
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

`--reload` is for local development only — never use it in production
(see section E). `api/main.py` loads `.env` automatically via
`python-dotenv` (production deployments should set these through the
hosting platform's env config instead of shipping a `.env` file).

On startup, `api/main.py` also calls `api/auth/db.py:init_db()`, which
creates the `users`/`user_sessions` tables if they don't already exist
(plain `Base.metadata.create_all()` — there is no migration tool wired up
yet; see section H).

### Frontend

```bash
cd frontend/frontend
npm ci
npm run dev
```

The frontend reads `VITE_API_BASE_URL` (see `.env.example`) at **build
time** via Vite's `import.meta.env`. If unset, it defaults to
`http://localhost:8000` (`frontend/frontend/src/lib/api/client.js`), which
matches the default `uvicorn` command above — no configuration needed for
local development.

### CORS in local development

`api/main.py` reads `CORS_ORIGINS` (comma-separated exact origins) at
startup. If unset, it falls back to a permissive
`http://localhost:<any port>` / `http://127.0.0.1:<any port>` regex, so
`npm run dev` talks to `uvicorn --reload` on whatever port Vite picks,
with no extra setup. This fallback does **not** apply outside of local
development — see section G.

---

## B. Docker build

```bash
docker build -t pulli-api .
```

The image contains only the API runtime: `engine/`, `api/`, and the
runtime-required subset of `experiments/m4_1`/`experiments/m4_2` (model
definition modules + the one checkpoint the ML detector loads —
`experiments/m4_2/results/dot_heatmap_net_v2.pt`). Datasets,
training/evaluation data, the frontend, and `.git` are excluded — see the
`Dockerfile` header comment and `.dockerignore` for the exact list and why
each exclusion is safe.

The image is CPU-only. `torch` is installed from PyPI's dedicated CPU
wheel index (`https://download.pytorch.org/whl/cpu`) specifically so no
CUDA/`nvidia-*` packages are pulled in — this project has no GPU code.

---

## C. Docker run

```bash
docker run --rm -p 8000:8000 \
  -e CORS_ORIGINS=http://localhost:5173 \
  -e AUTH_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(48))") \
  pulli-api
```

`CORS_ORIGINS` and `AUTH_SECRET` are the environment variables that matter
for a real deployment (see section G for the full list, including
`DATABASE_URL`/`COOKIE_SECURE`/`COOKIE_DOMAIN` for the auth system).
`KMP_DUPLICATE_LIB_OK` is set internally by `api/main.py` — do not set it
yourself.

---

## D. Health check

```
GET /api/v1/health
```

Returns whether the process is up and whether the ML checkpoint file is
present on disk:

```json
{"status": "ok", "classical_detector_available": true, "ml_detector_available": true}
```

This is an existence check, not a full dependency health check
(`docs/DEPLOYMENT_AUDIT.md` section 9) — it does not currently verify the
auth database is reachable. The `Dockerfile` also declares a `HEALTHCHECK`
that polls this same endpoint from inside the container — no new health
logic was added.

---

## E. Production deployment

```
Browser
   |
   v
Vercel / Cloudflare Pages (static frontend, frontend/frontend/dist)
   |
   | HTTPS
   v
FastAPI container (this Dockerfile), e.g. Render / Fly.io / Railway
   |
   +-- classical detector   (engine/image_io.py, CPU, no ML)
   +-- ML detector          (experiments/m4_2, CPU-only PyTorch)
   +-- reconstruction       (engine/reconstruction.py)
   +-- generation engine    (engine/generation.py, engine/learned_generation.py)
   +-- identity/session DB  (api/auth/ -- SQLite by default, see section H
                              for pointing this at a managed Postgres instance)
```

There is no queue, object storage, or worker in this architecture, and
none should be added speculatively — see `docs/DEPLOYMENT_AUDIT.md`
sections 6-7 for the reasoning (the detect/analyze/reconstruct/generate
endpoints are synchronous, sub-second, and stateless; only the auth system
touches a database).

Never run `uvicorn --reload` in production — use the exact command the
`Dockerfile` runs:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

## F. Frontend deployment

Set `VITE_API_BASE_URL` to the deployed backend's URL **at build time**:

```bash
VITE_API_BASE_URL=https://<backend-domain> npm run build
```

or configure it as a build-time environment variable in your static host
(Vercel/Cloudflare Pages project settings). It cannot be changed after the
build without rebuilding — it is baked into the static JS bundle by Vite,
not read at runtime in the browser.

---

## G. Backend deployment — environment variables

Copy `.env.example` to `.env` for local development, or set these through
your hosting platform's env config in production:

| Variable | Local dev | Production |
|---|---|---|
| `CORS_ORIGINS` | unset → permissive `http://localhost:<any port>` / `http://127.0.0.1:<any port>` regex | **required** — comma-separated exact origins, e.g. `https://app.pulli.example`. Never set to `*`: `allow_credentials=True` (required for the auth session cookie to work cross-origin at all) means the CORS spec forbids a wildcard origin. |
| `DATABASE_URL` | unset → local SQLite file `./pulli_auth.db`, zero setup | `postgresql+psycopg2://user:pass@host:5432/dbname` — Supabase PostgreSQL connection string. |
| `AUTH_SECRET` | unset → an insecure hardcoded dev fallback is used | **required** — the app refuses to start signing sessions with the dev fallback once `COOKIE_SECURE=true`. Generate with the command in section H. |
| `COOKIE_SECURE` | `false` (or unset) | `true` — **requires HTTPS**; browsers silently drop `Secure` cookies sent over plain HTTP. |
| `COOKIE_DOMAIN` | unset | only set if the API and frontend share a parent domain. |
| `STORAGE_PROVIDER` | `local` | `r2` — switches the artifact store backend from local disk to Cloudflare R2. |
| `R2_ENDPOINT` | unset | Cloudflare R2 S3-compatible API endpoint url. |
| `R2_ACCESS_KEY_ID` | unset | Cloudflare R2 Access Key ID. |
| `R2_SECRET_ACCESS_KEY` | unset | Cloudflare R2 Secret Access Key. |
| `R2_BUCKET` | unset | Cloudflare R2 Bucket name. |
| `R2_PUBLIC_BASE_URL` | unset | Public base URL serving objects directly (e.g. `https://pub-<hash>.r2.dev`). |

Use the exact deployed frontend origin for `CORS_ORIGINS` (scheme + host,
no path, no trailing slash), comma-separated if there is more than one
(e.g. a preview deployment origin alongside the production one).

---

## H. Database & migrations

Alembic manages database migrations for both domain and authentication schemas.

To run migrations in staging/production:

```bash
alembic upgrade head
```

This applies all database schema tables deterministically. Never run `create_all()` in production.

### Cookies in production

The session cookie (`pulli_session`, set by `api/auth/router.py`) is
`HttpOnly` always, and `Secure` + `SameSite=Lax` when `COOKIE_SECURE=true`.
Concretely:

- Serve the frontend and backend over HTTPS in production — a `Secure`
  cookie set over HTTP is silently dropped by the browser.
- If the frontend and API are on different subdomains of the same parent
  domain, set `COOKIE_DOMAIN` to the shared parent. Leave it unset for a
  single-domain deployment or for local development.
- `CORS_ORIGINS` must list the frontend's exact production origin(s).

### Secret generation

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use a different value per environment. Rotating `AUTH_SECRET` invalidates
every existing session cookie's signature (all logged-in users are signed
out) but does not affect stored password hashes.

---

## I. Production upload limits

`api/main.py` validates upload **content type** only
(`ALLOWED_CONTENT_TYPES` — jpeg/png/webp/bmp); there is currently **no
application-level upload size limit**. This is a known gap, documented in
`docs/DEPLOYMENT_AUDIT.md` section 9.

**Any public deployment must enforce a request body size limit at the
platform or reverse-proxy layer** (e.g. your hosting platform's own
request size cap, or a reverse proxy in front of the container) before
being exposed to untrusted traffic. This document does not specify a
provider-specific number — check the limit your chosen platform already
enforces by default and confirm it's reasonable for a single kolam photo
upload; do not assume one is in place without checking.

Adding an explicit application-level size check (reject oversized uploads
before they're written to a temp file) is a reasonable future hardening
item if the platform-level limit turns out to be absent or too permissive.

---

## Troubleshooting

- **`OMP: Error #15` / process crashes on first request** — `KMP_DUPLICATE_LIB_OK`
  must be set before torch or numpy is imported. It's set at the very top
  of `api/main.py`, before any other import — if this ever moves, the
  crash returns. Do not "fix" this by removing the line.
- **CORS errors in the browser console** — check `CORS_ORIGINS` matches
  the frontend's *exact* origin (scheme + host + port), and that you
  didn't leave a trailing slash.
- **Login "works" locally but fails in production** — almost always
  `COOKIE_SECURE=true` with the site served over plain HTTP, or
  `CORS_ORIGINS` not listing the frontend's exact origin. See section H.
- **`/api/v1/detect` with `detector=ml` returns 503** — the ML checkpoint
  (`experiments/m4_2/results/dot_heatmap_net_v2.pt`) is missing or failed
  to load. This is intentional (rule: no silent fallback to classical) —
  check `GET /api/v1/health`'s `ml_detector_available` field.

## Rollback

- **Backend code rollback**: standard — redeploy the previous image tag
  on your platform. The auth tables' shape hasn't changed across this
  feature's commits, so no data migration is needed to roll back.
- **Database rollback**: since there's no migration tool, "rollback" for
  the auth tables means restoring a database backup if you need to undo
  data changes (not schema changes — nothing here alters existing
  columns). Take a backup before any manual schema change.
- **If `AUTH_SECRET` is rotated by mistake**: not reversible from the old
  value alone (it isn't stored anywhere but the env config) — restore the
  previous secret from wherever it was originally generated/stored (e.g.
  your secrets manager's history) rather than regenerating a new one, or
  accept that all users need to log in again.
- **Frontend rollback**: the frontend is a static build — rolling back
  means redeploying the previous `dist/` build or, on Vercel/Cloudflare
  Pages, promoting a previous deployment. No data migration involved.

## Cost considerations

CPU-only, sub-second requests, no queue or GPU: this fits comfortably in
most platforms' free or lowest-cost tier (Render/Fly.io/Railway free or
hobby tier for the API container; Vercel/Cloudflare Pages free tier for
the static frontend). The default SQLite auth database has no separate
hosting cost; moving `DATABASE_URL` to a managed Postgres instance for
production adds a small, typically-free-tier-eligible cost. Revisit this
section if/when a future milestone introduces a real need for heavier
compute or additional persistent storage.
