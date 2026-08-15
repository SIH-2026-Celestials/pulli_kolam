# PULLI Deployment

This document covers local development, Docker, and production deployment
of the deployable pieces of PULLI today: the React/Vite frontend and the
FastAPI backend (`api/main.py`, including `api/auth/`). See
`docs/DEPLOYMENT_AUDIT.md` for the original architecture audit; several of
its conclusions (no object storage, single-DB-only persistence) have since
been superseded by the M7 platform work described below — read this file,
not that one, for the current state.

There is no queue or GPU. There IS a background M7 platform database
(patterns, generation runs/results, artifacts — `api/db/database.py`) in
addition to the identity/session database (`api/auth/`), and there IS an
object storage abstraction (`api/storage/`, `api/services/artifact_store.py`)
that persists rendered SVG/PNG artifacts either to local disk (dev default)
or Cloudflare R2 (`STORAGE_PROVIDER=r2`, section G). Uploaded images for
detection/analysis remain ephemeral (temp file, deleted after the request);
generated artifacts are not — see section J for their retention model.

---

## A. Local development

### Backend

```bash
pip install -r requirements.txt
cp .env.example .env          # optional locally; defaults work without it
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

`--reload` is for local development only  -  never use it in production
(see section E). `api/main.py` loads `.env` automatically via
`python-dotenv` (production deployments should set these through the
hosting platform's env config instead of shipping a `.env` file).

On startup, `api/main.py` also calls `api/auth/db.py:init_db()`, which
creates the `users`/`user_sessions` tables if they don't already exist
(plain `Base.metadata.create_all()`  -  there is no migration tool wired up
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
matches the default `uvicorn` command above  -  no configuration needed for
local development.

### CORS in local development

`api/main.py` reads `CORS_ORIGINS` (comma-separated exact origins) at
startup. If unset, it falls back to a permissive
`http://localhost:<any port>` / `http://127.0.0.1:<any port>` regex, so
`npm run dev` talks to `uvicorn --reload` on whatever port Vite picks,
with no extra setup. This fallback does **not** apply outside of local
development  -  see section G.

---

## B. Docker build

```bash
docker build -t pulli-api .
```

The image contains only the API runtime: `engine/`, `api/`, and the
runtime-required subset of `experiments/m4_1`/`experiments/m4_2` (model
definition modules + the one checkpoint the ML detector loads  - 
`experiments/m4_2/results/dot_heatmap_net_v2.pt`). Datasets,
training/evaluation data, the frontend, and `.git` are excluded  -  see the
`Dockerfile` header comment and `.dockerignore` for the exact list and why
each exclusion is safe.

The image is CPU-only. `torch` is installed from PyPI's dedicated CPU
wheel index (`https://download.pytorch.org/whl/cpu`) specifically so no
CUDA/`nvidia-*` packages are pulled in  -  this project has no GPU code.

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
`KMP_DUPLICATE_LIB_OK` is set internally by `api/main.py`  -  do not set it
yourself.

---

## D. Health checks

Three endpoints, for different purposes:

```
GET /api/v1/health        -- full diagnostic snapshot (detectors, generation
                              service, database, artifact storage). Cheap:
                              never runs an actual M5 generation.
GET /api/v1/health/live   -- liveness probe: {"status": "ok"} iff the FastAPI
                              process is up. Use this for the platform's
                              "is the container alive" check.
GET /api/v1/health/ready  -- readiness probe: checks the M4.2 checkpoint file
                              exists, the generation service loaded, the
                              database answers `SELECT 1`, and the artifact
                              store is reachable. Returns HTTP 503 (not 200)
                              when any check fails, so a load balancer/platform
                              readiness gate can act on the status code alone,
                              not just the body.
```

**`PULLI_TESTING=true` bypasses the startup checkpoint/security validation
described in section E** (used only by CI and `api/tests/conftest.py` so
the test suite doesn't need real model checkpoints or `AUTH_SECRET`
present). **Never set `PULLI_TESTING` in a Render/production environment**
— doing so would silently disable the fail-fast checks that would
otherwise refuse to start a misconfigured deployment.

On Render, configure the health check path as `/api/v1/health/ready` (not
`/api/v1/health`) so the platform won't route traffic to an instance whose
DB or artifact store isn't actually reachable yet. The `Dockerfile`'s own
`HEALTHCHECK` polls `/api/v1/health` (a liveness-style check sufficient for
`docker run`'s own restart policy); Render's separate readiness gate is
configured through the platform, not the Dockerfile.

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

There is still no queue or worker — detect/analyze/reconstruct requests are
synchronous. Generation (M5, `/api/v1/generations`) is also synchronous
(the caller's HTTP request blocks until the candidate(s) are generated,
persisted, and returned — see section K for measured latency), which is
why it is separately rate-limited (`api/rate_limit.py`) rather than queued.

Never run `uvicorn --reload` in production. The `Dockerfile`'s actual
production command (also what Render should run) applies pending database
migrations before starting the server, and binds to the platform's `$PORT`
rather than a hardcoded port:

```bash
alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

---

## F. Frontend deployment

Set `VITE_API_BASE_URL` to the deployed backend's URL **at build time**:

```bash
VITE_API_BASE_URL=https://<backend-domain> npm run build
```

or configure it as a build-time environment variable in your static host
(Vercel/Cloudflare Pages project settings). It cannot be changed after the
build without rebuilding  -  it is baked into the static JS bundle by Vite,
not read at runtime in the browser.

---

## G. Backend deployment  -  environment variables

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
| `R2_PUBLIC_BASE_URL` | unset | Public base URL serving objects directly (e.g. `https://pub-<hash>.r2.dev`). If unset, `url()` falls back to a 1-hour presigned URL per object instead — see `api/storage/r2.py`. |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_TIMEOUT_SECONDS` / `DB_POOL_RECYCLE_SECONDS` | ignored (SQLite has no connection pool) | optional tuning for the platform-data Postgres pool (`api/db/database.py`). Defaults (5 / 10 / 30s / 1800s) are reasonable starting points, not measured against a specific Supabase plan — revisit under real concurrent load. |
| `AUTH_DB_POOL_SIZE` / `AUTH_DB_MAX_OVERFLOW` | ignored (SQLite) | same, for the auth database pool (`api/auth/db.py`), sized smaller (3 / 5) since it's a much lighter read/write pattern than the platform DB. **Both pools share the same `DATABASE_URL` connection budget when auth and platform data live in the same Postgres instance** — account for both when sizing against your plan's max-connections limit. |

Use the exact deployed frontend origin for `CORS_ORIGINS` (scheme + host,
no path, no trailing slash), comma-separated if there is more than one
(e.g. a preview deployment origin alongside the production one).

---

## H. Database & migrations

Alembic manages database migrations for both the platform schema (`api/db/database.py`
— patterns, generation runs/results, artifacts) and the auth schema (`api/auth/db.py`
— users, user_sessions); see `alembic/env.py`. The `Dockerfile`'s production start
command already runs this on every container boot:

```bash
alembic upgrade head
```

This applies pending migrations deterministically before the server starts accepting
traffic. `init_db()` in both `api/db/database.py` and `api/auth/db.py` will only call
`Base.metadata.create_all()` when `DATABASE_URL` is SQLite (local dev) — against
Postgres it prints a message and does nothing, so a real deployment cannot
accidentally bypass Alembic by starting the app before running migrations.

**Verified this session**: `alembic upgrade head` then `alembic downgrade base`
against a real (throwaway) SQLite database, confirming table creation and removal
directly via `sqlite_master` queries. **Not verified**: never run against a real
PostgreSQL instance (no Supabase credentials available in this environment) — do
this once, against a disposable staging database, before trusting it against
production data.

### Cookies in production

The session cookie (`pulli_session`, set by `api/auth/router.py`) is
`HttpOnly` always, and `Secure` + `SameSite=Lax` when `COOKIE_SECURE=true`.
Concretely:

- Serve the frontend and backend over HTTPS in production  -  a `Secure`
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

`api/main.py` validates upload **content type** (`ALLOWED_CONTENT_TYPES` —
jpeg/png/webp/bmp) and enforces an application-level size cap
(`MAX_UPLOAD_BYTES = 20MB`, `api/main.py`): the request body is read up to
that limit plus one byte, and anything larger is rejected with `413
UPLOAD_TOO_LARGE` before the full file is buffered in memory. This
supersedes `docs/DEPLOYMENT_AUDIT.md` section 9, written before this check
existed.

Still recommended: also enforce a request body size limit at the platform
or reverse-proxy layer in front of the container, as defense in depth — the
application-level check bounds per-request memory use, but a platform-level
cap (checked before the request body is even fully received) is cheaper
protection against a flood of oversized requests. Check what your chosen
platform enforces by default rather than assuming.

---

## J. Artifact lifecycle & retention

Generated Kolam artifacts (SVG/PNG renders, one set per `GenerationResult`)
are written through `api/services/artifact_store.py:get_artifact_store()` —
`LocalStorage` (disk, dev default) or `R2Storage` (`STORAGE_PROVIDER=r2`).
The `Artifact` DB row stores a store-relative key, never a filesystem path
or bucket URL, so switching providers doesn't require touching existing
rows.

- **Permanent until explicitly deleted**: `DELETE /api/v1/generations/{id}`
  (implemented and tested this session — see `PRODUCTION_DEPLOYMENT_READINESS.md`
  section 6) removes the DB rows (GenerationResult, PatternVersion,
  PatternAnalysis, VerificationResult, Artifact, and the parent Pattern if
  it has no other versions) AND the underlying storage object, in that
  order (DB commit first, storage cleanup after — a storage failure never
  blocks or fails the DB deletion; see the endpoint's own docstring in
  `api/routes_generations.py`). Ownership-checked like every other
  `/generations/{id}` route. There is still no automatic expiry job —
  deletion is user-initiated only, never time-based.
- **Ephemeral**: uploaded images for `/api/v1/detect`/`/analyze` are
  written to a temp file for one request and removed immediately after —
  unrelated to the artifact store, never persisted.
- **Recommended, not implemented**: an R2 bucket lifecycle rule
  (Cloudflare dashboard, not application code) as a backstop against
  unbounded growth from artifacts nobody ever explicitly deletes; a
  bulk-regeneration script for rebuilding artifacts from
  `representation_json` if the R2 bucket is ever lost entirely (see
  `docs/DISASTER_RECOVERY.md` section B).

---

## K. Measured performance (generation load)

Real measurements from this environment (single local process, `uvicorn`
without `--workers`, CPU-only, M5 `generate_novel_kolam_learned`) — not
estimates. Two separate measurements, run at different scope:

**Single-candidate generation quality/latency** (`experiments/m5_generation/run_benchmark_lite.py`,
a documented reduced-scale run — 50 candidates, 12 restarts each, vs. the
full evaluation's 500/16 — see the script's own docstring for why):
validity rate 82% (41/50), connectivity rate 82%, avg latency **19.71s**
per candidate, 100% unique topological fingerprints across valid
candidates, reliability-at-k: 100% chance of at least one valid candidate
within 10 attempts. Full data: `experiments/m5_generation/results/benchmark_report_lite.json`.

**Concurrent HTTP load** against a live local server (`POST /api/v1/generations`,
count=1 per request), measured this session:

| Concurrency | OK | 429 (rate-limited) | 500 (error) | p50 | p95 | p99 | RSS before → after |
|---|---|---|---|---|---|---|---|
| 1 | 1/1 | 0 | 0 | 7.8s | 7.8s | 7.8s | 496 → 499 MB |
| 3 | 3/3 | 0 | 0 | 16.1s | 21.7s | 21.7s | 496 → 506 MB |
| 5 | 5/5 | 0 | 0 | 21.3s | 35.6s | 35.6s | 506 → 510 MB |
| 10 | 4/10 | 4 | **2** | 19.9s | 42.1s | 42.1s | 511 → 524 MB |

Measured against `DATABASE_URL=sqlite:///...`. **At concurrency 10, 2 of
10 requests failed with HTTP 500** (`sqlalchemy.exc.OperationalError:
(sqlite3.OperationalError) database is locked`, each after exhausting the
30s `busy_timeout` set on this connection — see `api/db/database.py`'s
`_set_sqlite_pragma`). SQLite's single-writer model is the direct cause.

**Update, same session**: this exact test was re-run against a real,
disposable PostgreSQL 16 instance (Docker). **At concurrency 10, Postgres
produced zero HTTP 500s** (6 succeeded, 4 were cleanly rate-limited) —
confirming MVCC handles the write contention SQLite's single-writer model
cannot. Full comparison table, plus an important caveat about a
methodology confound in the Postgres latency numbers (an `ALTER TABLE`
migration ran concurrently with part of that benchmark), is in
`PRODUCTION_DEPLOYMENT_READINESS.md` section 3 — read that caveat before
using the Postgres latency figures for capacity planning; the
success/failure counts are unaffected by it. Real Supabase (as opposed to
plain Docker Postgres) has not been tested — its connection pooler
(`pgbouncer`) can have its own compatibility quirks with SQLAlchemy's
session-per-request pattern, not evaluated here.

Also note: the rate limiter (6/min per IP) is what actually kept
concurrency 1/3/5 from ever reaching this failure mode — at 10 concurrent
requests, 4 were rejected by the rate limiter itself before ever reaching
the database, which is arguably why only 2 (not more) of the remaining 6
hit the lock timeout.

`api/rate_limit.py`'s in-process limiter (`GENERATION_LIMIT_PER_MINUTE = 6`,
IP-keyed) is what actually caps concurrency from a single source today —
see section on rate limiting below for why this is a real constraint on a
single Render instance behind a shared IP (office network, mobile carrier
NAT) and why it does not survive a multi-instance deployment without
Redis/Valkey.

**Sizing implication for Render**: generation is CPU-bound and
single-request latency is ~8-20s depending on load; do not run more
`uvicorn` worker processes than available vCPUs, since CPU contention (not
memory) is the binding constraint observed here.

---

## L. Security headers

`api/security_headers.py`'s `SecurityHeadersMiddleware` (wired in
`api/main.py`) applies `Strict-Transport-Security`,
`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
`Permissions-Policy` (camera/mic/geolocation/payment/usb all denied),
`X-Frame-Options: DENY`, and `Content-Security-Policy` to every response.
CSP is deliberately different for `/docs`/`/redoc`/`/openapi.json`
(permissive enough for Swagger UI/ReDoc's known CDN sources) than
everywhere else (`default-src 'none'; frame-ancestors 'none'`) — see the
module's own docstring before changing either policy, since a stricter
CSP on the docs paths will break them.

Also note: `CORSMiddleware`'s `allow_methods` includes `DELETE` (added
alongside `DELETE /api/v1/generations/{id}` — a real gap, `allow_methods`
was `["GET", "POST"]` for one deployment cycle, which would have broken
that endpoint's CORS preflight from the real Vercel frontend). If a
future endpoint needs `PUT`/`PATCH`, add it there too — CORS methods are
not inferred automatically from the route table.

---

## Troubleshooting

- **`OMP: Error #15` / process crashes on first request**  -  `KMP_DUPLICATE_LIB_OK`
  must be set before torch or numpy is imported. It's set at the very top
  of `api/main.py`, before any other import  -  if this ever moves, the
  crash returns. Do not "fix" this by removing the line.
- **CORS errors in the browser console**  -  check `CORS_ORIGINS` matches
  the frontend's *exact* origin (scheme + host + port), and that you
  didn't leave a trailing slash.
- **Login "works" locally but fails in production**  -  almost always
  `COOKIE_SECURE=true` with the site served over plain HTTP, or
  `CORS_ORIGINS` not listing the frontend's exact origin. See section H.
- **`/api/v1/detect` with `detector=ml` returns 503**  -  the ML checkpoint
  (`experiments/m4_2/results/dot_heatmap_net_v2.pt`) is missing or failed
  to load. This is intentional (rule: no silent fallback to classical)  - 
  check `GET /api/v1/health`'s `ml_detector_available` field.

## Rollback

See also `docs/DISASTER_RECOVERY.md` for full backup/restore procedures
(database `pg_dump`/`pg_restore`, R2 durability/recovery expectations,
secrets recovery) — this section covers code/schema rollback only.

- **Backend code rollback**: redeploy the previous image tag on your
  platform. If the rolled-back code predates the current migration head,
  also run `alembic downgrade <previous-revision>` — check compatibility
  first (a schema rollback that drops a column a still-running new-code
  instance depends on will break it; sequence downgrade before or during
  the redeploy, not after).
- **Database rollback**: `alembic downgrade <revision>` reverses schema
  changes deterministically (see section H) for anything under Alembic's
  management. For data changes (not schema changes), restore from a
  database backup — Alembic manages structure, not data snapshots. Take a
  backup before any production migration, not just before manual schema
  changes.
- **If `AUTH_SECRET` is rotated by mistake**: not reversible from the old
  value alone (it isn't stored anywhere but the env config)  -  restore the
  previous secret from wherever it was originally generated/stored (e.g.
  your secrets manager's history) rather than regenerating a new one, or
  accept that all users need to log in again.
- **Frontend rollback**: the frontend is a static build  -  rolling back
  means redeploying the previous `dist/` build or, on Vercel/Cloudflare
  Pages, promoting a previous deployment. No data migration involved.

## Cost considerations

CPU-only, no GPU, no queue. Detect/analyze/reconstruct requests are
sub-second; generation requests are not (~8-20s measured, section K) and
are the one endpoint that meaningfully taxes CPU — size the Render
instance/plan around generation throughput, not the other endpoints. This
still fits comfortably in most platforms' low-cost tiers (Render/Fly.io/
Railway hobby tier for the API container; Vercel/Cloudflare Pages free
tier for the static frontend) at low traffic. The default SQLite database
has no separate hosting cost; moving `DATABASE_URL` to a managed Postgres
instance for
production adds a small, typically-free-tier-eligible cost. Revisit this
section if/when a future milestone introduces a real need for heavier
compute or additional persistent storage.
