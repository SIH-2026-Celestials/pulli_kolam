# PULLI Production Deployment Readiness Report

GREEN = implemented AND independently verified. YELLOW = implemented but external
verification unavailable, or a known non-critical limitation. RED = production-blocking.
No finding is downgraded for convenience. "Verified" means actually executed in this
session (a command run, an HTTP response observed, a test that passed) — not "the code
looks right." Where that distinction matters, both are stated explicitly.

---

## 1. Executive Status

**Not production-ready. Two sessions of infrastructure hardening are complete; three
external-credential blockers remain, explicitly BLOCKED, not fabricated.**

This session found and fixed one severe, previously-unknown vulnerability (generation
results had no ownership model at all — any visitor could read/create/delete anyone's
generations), fixed three previously-invisible PostgreSQL-only bugs (an oversized index,
an integer overflow, and a broken SQLite migration), fixed a CORS bug that would have
silently broken artifact deletion from the real production frontend, added security
headers, executed a real, complete backup/destroy/restore/verify drill against a
disposable PostgreSQL instance, and built + ran the actual production Docker image from
a clean environment — which found and fixed a fourth real bug: the image never packaged
the dataset files M5 generation loads at runtime, so a container built exactly as
documented would start, pass liveness, and then be permanently un-ready
(`generation_service_available: false`). All 94 `api/tests/` pass; 50/50 frontend tests
pass; a real generation was completed end-to-end through the built container itself.

**Remaining, explicitly BLOCKED — requires external credential/infrastructure this
environment does not have:**
- Cloudflare R2 (no bucket/credentials)
- Real Supabase Postgres (a disposable local Postgres container was used instead —
  real, not simulated, but not Supabase specifically)
- Vercel/Render accounts (no staging or production deployment exists)

---

## 2. Architecture Verified

Read the running code, not stale docs, per this task's own instruction. Confirmed by
direct inspection this session:

| Component | Actual state |
|---|---|
| Frontend entry | `frontend/frontend/`, Vite + React, `VITE_API_BASE_URL` (build-time only, `client.js:8`) with a `localhost:8000` fallback used only when unset — no other hardcoded backend URL found in `src/`. |
| Backend entry | `api/main.py` (FastAPI), `uvicorn api.main:app`; `Dockerfile` CMD runs `alembic upgrade head && uvicorn ... --port ${PORT:-8000}`. |
| Database | `api/db/database.py` (platform: patterns/generations/artifacts) + `api/auth/db.py` (auth: users/sessions) — two SQLAlchemy `Base`s, one `DATABASE_URL`. SQLite by default; Postgres via `postgresql+psycopg2://...`. Both Alembic-managed (`alembic/env.py` lists both `Base.metadata`s). |
| Artifact storage | `api/storage/{base,local,r2}.py` + `api/services/artifact_store.py`'s `get_artifact_store()` factory, keyed by `STORAGE_PROVIDER` (`local`/`r2`). DB stores store-relative keys, never filesystem paths. |
| Authentication | `api/auth/` — bcrypt password hashing, signed opaque session-token cookie (`pulli_session`, HttpOnly), server-side `user_sessions` table. FastAPI-native, no third-party auth service. |
| ML runtime | `api/detectors.py` (M4.2, `experiments/m4_2/results/dot_heatmap_net_v2.pt`) and `api/generation_service.py`/`api/services/generation.py` (M5, `experiments/m5_generation/checkpoints/placement_scorer.pt`) — both loaded at startup, validated by `api/main.py:_lifespan`. |
| Environment vars | `.env.example` (repo root) — `VITE_API_BASE_URL`, `CORS_ORIGINS`, `DATABASE_URL`, `AUTH_SECRET`, `COOKIE_SECURE`, `COOKIE_DOMAIN`, `DB_POOL_*`/`AUTH_DB_POOL_*`, `STORAGE_PROVIDER`, `R2_*`. Confirmed complete by reading it. |
| CI | `.github/workflows/ci.yml` — `pytest tests/` + `pytest api/tests/` (sequentially, one job) + frontend lint/test/build (separate job). No staging-deploy stage. |

**Docker — real clean build and run, this session, not just inspection.**
`docker build -t pulli-api-test .` from a clean state (no local Python env involved);
`docker run` the resulting image; verified live:
- `whoami` inside the running container returns `pulli`, not root — the non-root user
  added in a prior session genuinely works, confirmed by execing into the real
  container, not by reading the Dockerfile.
- `alembic upgrade head` ran automatically on container start (visible in
  `docker logs`), before `uvicorn` began accepting traffic.
- **Real bug found and fixed**: the first build's `/api/v1/health/ready` came back
  `generation_service_available: false` — `FileNotFoundError` for `kolam19.csv`.
  `api/generation_service.py` loads every source pattern in `split_manifest.json`'s
  test split via `engine.dataset.load_kolam()`, which reads real CSV files the
  Dockerfile never packaged (`.dockerignore` excluded all of `kolam_data/`). Fixed by
  adding two explicit, minimal `COPY` lines for exactly the two CSVs the test split
  actually references (`kolam19.csv`, `kolam29.csv` — 1.8MB + 1.1MB; confirmed
  `kolam109.csv`, ~18MB, is NOT referenced by the test split before excluding it) and
  a matching `.dockerignore` exception. **A second real bug surfaced fixing the
  first**: the initial fix used shell-style quoted `COPY "path with spaces" "dest"`,
  which is not valid Dockerfile syntax for paths containing spaces and failed the
  build outright (masked once by a `| tail` pipe that silently returned the wrong
  exit code — a real methodology bug in how the build was first tested, also fixed).
  Corrected to Dockerfile's required JSON-array `COPY [...]` form.
- After both fixes: rebuilt, reran, `/api/v1/health/ready` returned fully `ready`
  (all 4 subsystems), and **a complete real generation was executed through the
  running container** (register → login → `POST /generations` → real SVG returned).

---

## 3. Files Changed (this session)

**Modified**: `.dockerignore`, `.gitignore`, `Dockerfile`, `PRODUCTION_DEPLOYMENT_READINESS.md`,
`api/db/models.py`, `api/main.py`, `api/rate_limit.py`, `api/routes_generations.py`,
`api/services/generation.py`, `api/tests/test_platform_followup.py`,
`api/tests/test_platform_generations.py`, `docs/DEPLOYMENT.md`,
`frontend/frontend/src/pages/Playground/Playground.jsx`.

**New**: `alembic/versions/65648c1f34c0_add_user_id_to_generation_requests.py`,
`alembic/versions/88b2d4e65df2_drop_unused_fingerprint_index.py`,
`alembic/versions/cc3960605d67_widen_generation_results_seed_to_bigint.py`,
`api/security_headers.py`, `api/tests/test_rate_limit.py`,
`api/tests/test_security_headers.py`, `docs/DISASTER_RECOVERY.md`.

**Deleted**: `api/object_storage/{__init__,base,local}.py` — a duplicate abstraction
built before discovering the real `api/storage/` package already existed and was wired
in; removed once confirmed unused anywhere.

---

## 4. Database Status

🟡 **Real PostgreSQL 16 verified (Docker); Supabase specifically not verified.**

- Full Alembic chain (5 migrations: initial schema → auth tables → ownership column →
  drop-oversized-index → widen-seed-to-bigint) applied cleanly, upgrade AND downgrade,
  against a disposable Postgres container. Command: `alembic upgrade head`, exit 0.
- Three real bugs found by actually running against Postgres (SQLite tolerated all
  three silently):
  1. `pattern_versions.fingerprint` (indexed `Text`) exceeded Postgres's btree
     index row-size limit (2704 bytes) on a 500-dot pattern —
     `psycopg2.errors.ProgramLimitExceeded`. Fixed by dropping the index (confirmed
     unused by any query in the codebase first).
  2. `generation_results.seed` (`Integer`, 32-bit) overflowed on random seeds up to
     2³²-1 — `psycopg2.errors.NumericValueOutOfRange`. Fixed: widened to `BigInteger`.
  3. The autogenerated migration for fix #2 used a bare `ALTER TABLE ... ALTER
     COLUMN`, which is not valid SQLite syntax at all — would have broken the next
     `alembic upgrade head` on a fresh SQLite dev DB. Fixed by wrapping in
     `op.batch_alter_table`. Caught by actually running it against SQLite, not by
     inspection.
- **90/90 `api/tests/` (as it stood before this session's later additions) passed in
  full against real Postgres** after both fixes — command:
  `DATABASE_URL=postgresql+psycopg2://... python -m pytest api/tests/ -q`.
- **Real backup/restore drill executed and verified** — see section 12.
- Connection pooling (`pool_size`/`max_overflow`/`pool_timeout`/`pool_recycle`/
  `pool_pre_ping`) configured for both the platform and auth engines when
  `DATABASE_URL` is Postgres; both share one `DATABASE_URL` connection budget if
  co-located — sized (5+10 and 3+5) but not load-tested against a real connection cap.
- **Not verified**: Supabase's specific pooler (`pgbouncer`, transaction-mode
  compatibility with SQLAlchemy's session-per-request pattern). BLOCKED — no Supabase
  project available.

---

## 5. Storage Status

🟡 **Local storage fully verified; R2 implemented but genuinely unverified — BLOCKED,
no credentials.**

- `LocalStorage`/`R2Storage` both implement `save`/`get`/`delete`/`exists`/`url`
  identically (`api/storage/base.py` Protocol).
- Artifact deletion (`DELETE /api/v1/generations/{id}`, new this session) tested
  against local storage: success, missing-artifact 404, unauthorized-deletion 404
  (row confirmed untouched), simulated DB failure → 500 + rollback verified,
  simulated storage failure → DB rows still removed (204). 5/5 required scenarios,
  all passing (`api/tests/test_platform_generations.py`).
- R2: `api/storage/r2.py` reviewed against boto3's documented S3 API; lazy import so
  the module loads even without boto3 installed. **Cannot be execution-tested in this
  environment** — a pre-existing, project-unrelated `cryptography`/`pyOpenSSL`
  conflict in this local conda install breaks `import boto3` (does not affect a clean
  Docker/CI install, and was not the reason R2 itself couldn't be tested — the actual
  blocker is no R2 bucket/credentials exist). Staging verification checklist
  (6 steps: upload, retrieve, export via API, delete-and-confirm-gone, credential
  fallback, large-artifact) is documented in the prior version of this file and in
  `docs/DEPLOYMENT.md` — not re-run here for brevity, unchanged from last session.
- DB stores store-relative keys (`Artifact.storage_path`), never filesystem paths —
  confirmed by reading `api/db/models.py`'s `Artifact` model and its own docstring.

---

## 6. Security Status

🟡 **Most items verified; security headers newly implemented and tested this
session; CORS bug found and fixed this session.**

- **Security headers — NEW, implemented and verified this session**
  (`api/security_headers.py`, `SecurityHeadersMiddleware`): `Strict-Transport-Security`,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
  `Permissions-Policy` (camera/mic/geo/payment/usb all denied), `X-Frame-Options: DENY`,
  and `Content-Security-Policy`. Verified with real HTTP requests against a live
  server: headers present on a 200 (`/api/v1/health/live`), a 401 error response, AND
  `/docs`. CSP is deliberately different for `/docs`/`/redoc`/`/openapi.json`
  (`default-src 'self'; script-src ... cdn.jsdelivr.net`, matching what Swagger UI
  actually loads — confirmed by fetching `/docs`'s HTML and grepping for the CDN URLs
  it references) vs. `default-src 'none'; frame-ancestors 'none'` everywhere else.
  4 regression tests, all passing.
- **Real bug found and fixed while reviewing CORS for this phase**: `allow_methods`
  was `["GET", "POST"]` (confirmed by reading the source before editing it) —
  missing `DELETE` entirely, meaning the artifact-deletion endpoint added last
  session would have failed CORS preflight from any real cross-origin browser (the
  actual Vercel-frontend-to-Render-backend production topology). The fix was
  verified live, not just inspected: an `OPTIONS` preflight for `DELETE` from
  `https://pulli-frontend.vercel.app` (with `CORS_ORIGINS` set to that exact origin)
  returned `200` with `access-control-allow-methods: GET, POST, DELETE` and the
  correct `access-control-allow-origin` echoed back. Regression test added.
- **CORS wildcard**: forbidden by a startup check (`api/main.py:_lifespan`,
  `sys.exit(1)` if `CORS_ORIGINS="*"` and `COOKIE_SECURE=true`) — verified by reading
  the code, not re-triggered live this session (was triggered and confirmed in an
  earlier session).
- **CSRF**: no dedicated token; `SameSite=Lax` on the session cookie is the sole
  mitigation, adequate for a pure JSON API with no server-rendered forms — this is a
  documented design choice, not an oversight.
- **Upload limits**: content-type allowlist + `MAX_UPLOAD_BYTES=20MB` (HTTP 413) —
  verified enforced by reading `api/main.py`.
- **Path traversal**: `LocalStorage._resolve()` rejects any key resolving outside its
  root — verified by reading the code (a dedicated regression test,
  `test_artifact_store_rejects_path_traversal`, already existed and passes).
- **SQL injection**: SQLAlchemy ORM parameterization throughout; no raw string
  interpolation found by inspection.
- **Secret exposure**: `R2_ACCESS_KEY_ID`/`R2_SECRET_ACCESS_KEY` grepped across
  `frontend/frontend/src/` — zero matches. `.dockerignore` now excludes `.env`/local
  DB/artifact files from the build context (defense in depth; the Dockerfile never
  `COPY`s them anyway via its explicit-path-only `COPY` list).
- **Error disclosure**: every error path (`_api_error` in `api/main.py`/
  `api/routes_generations.py`) returns the standard `{"success": false, "error", "code"}`
  envelope — no stack traces or filesystem paths observed in any error response
  produced this session (401s, 404s, 422s, 429s, 500s all checked).

---

## 7. Authentication & Authorization

🟢 **Both verified live this session, including the session's central fix.**

**Authentication** — real register → login → authenticated request flow exercised
live (`curl`, real HTTP, real cookie jar) multiple times this session, including
during the backup/restore drill:
- `bcrypt.hashpw`/`checkpw` for passwords (`api/auth/security.py`) — not a homegrown
  scheme.
- Session cookie: `HttpOnly` always; `Secure`+`SameSite=Lax` when `COOKIE_SECURE=true`;
  app refuses to start signing sessions with a fallback secret in that mode.
- Wrong-password login: generic 401 message — no user-enumeration leak (verified live).
- Unauthenticated `/me`/`/generations`: clean 401 (verified live, multiple times).

**Authorization — this session's most significant fix.** Generation endpoints had NO
ownership model at all before this session: any visitor, logged in or not, could
create and retrieve any generation by ID. Fixed:
- `GenerationRequest.user_id` added (Alembic migration, nullable, soft reference —
  auth and platform data live in separate SQLAlchemy `Base`s / potentially separate
  databases, so no DB-enforced FK).
- Every generation route (`POST/GET/DELETE /generations`, `/mathematics`, `/graph`,
  `/export`) now requires login and enforces ownership via a shared
  `_get_owned_generation` helper returning the **same 404** for "doesn't exist" and
  "exists but isn't yours" — never a 403 that would leak existence.
- **A real bug was caught by the new tests, not found by inspection**: `User.id` is
  `Integer`; the new `user_id` column was `String(36)`. Storing/comparing an `int`
  against that column type round-tripped inconsistently in SQLite, meaning **even the
  correct owner got a 404 retrieving their own generation** until fixed by
  stringifying `current_user.id` at every write/compare site.
- Verified with two real user accounts, both created and logged in live: user B
  reliably gets 404 on user A's generation across GET/mathematics/graph/export/DELETE;
  user A's list never includes user B's rows; deletion by user B is rejected and
  confirmed the row is still fully intact and retrievable by user A afterward.
- 11 regression tests total (6 for read/list ownership, 5 for deletion, one of which
  is specifically the unauthorized-deletion case) — all passing.
- Re-verified end-to-end during the real backup/restore drill (section 12): ownership
  enforcement survived a full `pg_dump`/`DROP DATABASE`/`pg_restore` round-trip — a
  second, freshly-registered user hitting the pre-backup generation's id post-restore
  still got the correct 404.

---

## 8. ML Runtime Status

🟢 **Verified — real generation exercised dozens of times this session and last, with
real measured numbers, no mocks.**

- `api/main.py:_lifespan` fails fast (`sys.exit(1)`) on a missing M4.2 or M5
  checkpoint, or missing `AUTH_SECRET`/`CORS_ORIGINS` under `COOKIE_SECURE=true` —
  verified by reading the code; the bypass (`PULLI_TESTING=true`, used only by CI and
  `api/tests/conftest.py`) is explicitly documented in `docs/DEPLOYMENT.md` as
  "never set in production."
- Real M5 generations executed this session: single-candidate benchmark (50
  candidates, 82% validity, 19.71s avg latency — `experiments/m5_generation/results/
  benchmark_report_lite.json`), concurrency benchmarks at 1/3/5/10 against both
  SQLite and Postgres (~20 more real generations), plus several ad-hoc generations
  during the ownership and backup/restore testing. Every one produced a real SVG, a
  real structural representation, and real M4.2 verification — none synthesized.
- M4.2 recognizer: loaded and reported `ml_detector_available: true` on every
  `/api/v1/health/ready` check this session (SQLite-backed and Postgres-backed
  servers both).
- No modification to `experiments/m4_2/`, `experiments/m5_generation/`, or
  `experiments/m6_generation/` this session — confirmed by `git status --short`,
  none of those paths appear.

---

## 9. Performance & Concurrency

🟡 **Real data at all four concurrency levels, against both databases — but the
Postgres latency figures are confounded and need a clean re-run.**

| Concurrency | SQLite OK/429/500 | SQLite p50/p95 | Postgres OK/429/500 | Postgres p50/p95 |
|---|---|---|---|---|
| 1 | 1/0/0 | 7.8s / 7.8s | 1/0/0 | 5.9s / 5.9s |
| 3 | 3/0/0 | 16.1s / 21.7s | 2/0/1* | 18.8s / 18.8s |
| 5 | 5/0/0 | 21.3s / 35.6s | 4/0/1* | 86.8s / 87.4s |
| 10 | 4/4/**2** | 19.9s / 42.1s | 6/4/**0** | 45.1s / 74.9s |

\* Both Postgres failures at concurrency 3/5 were the seed-overflow bug (database
section, bug #2), not a distinct failure mode — a migration-timing artifact of when
the fix landed mid-benchmark.

**Headline, real result**: at concurrency 10, SQLite produced 2 genuine
`database is locked` HTTP 500s; **Postgres produced zero** — direct evidence real
MVCC handles write contention SQLite's single-writer model cannot.

**Known confound, disclosed rather than hidden**: the Postgres p50=86.8s at
concurrency 5 coincides with an `ALTER TABLE` migration (bug #2's fix) being applied
to the SAME live table while that benchmark level ran. `ALTER COLUMN` takes an
ACCESS EXCLUSIVE lock in Postgres, which would block concurrent writers for its
duration — the elevated latency is very likely this artifact, not Postgres's genuine
steady-state performance. **A clean re-run (no concurrent schema changes) is required
before these specific latency numbers are used for capacity planning.** The
success/failure counts are unaffected by this confound.

RSS: SQLite peaked ~524MB at concurrency 10; Postgres ~623MB at concurrency 5 (pre-
confound). CPU contention from concurrent M5 generation, not memory, is the binding
constraint in both cases.

---

## 10. Frontend Status

🟢 **No fabricated data found; ownership-fix impact handled honestly.**

- Grepped `frontend/frontend/src/` for hardcoded `localhost`/`127.0.0.1`/ports —
  only the documented `VITE_API_BASE_URL` build-time fallback in `client.js`, not a
  production code path.
- `Playground.jsx`'s generate/history calls already send `credentials: 'include'` on
  every request, so a logged-in user's flow needed zero change from the ownership fix.
  Added an honest 401-specific message ("Generation requires an account so your
  results are kept private to you...") instead of the generic retry hint, and a
  distinct "Log in to see your generation history" state — both real, not fabricated
  fallback content.
- Frontend test suite: 50/50 passing (`npm run test -- --run`), including the
  existing "no fabricated fallback data" scan across Playground/GeneratedVariations/
  RecentKolams/AuthContext for banned patterns (`FALLBACK_CANDIDATES`,
  `MOCK_KOLAM_ITEMS`, etc.) — still zero matches.
- **Not re-verified this session**: a live browser E2E click-through of every listed
  route (dashboard/playground/analyze/detect/history/export). Backend-side E2E was
  exercised via curl (register→login→generate→retrieve, section 12's drill), not a
  real browser session. Recommended, not done — time budget.

---

## 11. CI/CD Status

🟡 **Verified by reading `.github/workflows/ci.yml`; unchanged this session.**

- PR gate: `pytest tests/` + `pytest api/tests/` (sequentially, one job,
  `PULLI_TESTING=true`) + a separate frontend job (`npm ci` → lint → test → build).
  Both must pass for a green PR.
- **No staging-deploy or smoke-test pipeline stage exists** — promotion from a green
  main branch to a real deployment is a fully manual process today, not automated.
  This matches the task's own instruction not to auto-deploy, but it also means there
  is no CI-enforced gate between "tests pass" and "someone manually deploys" — a real,
  named gap, not fixed this session (would require actual Render/Vercel deploy hooks
  wired into the workflow, which needs those accounts to exist first).

---

## 12. Backup & Recovery

🟡 **A real, complete backup/restore drill was executed and verified this session —
against disposable Docker Postgres, not Supabase. No backup schedule exists anywhere
against a real deployment, because no real deployment exists yet.**

Full 15-step drill executed against a real, disposable `postgres:16-alpine` container:

| Step | Result |
|---|---|
| 1. Create database | Real Docker container |
| 2. Migrations | `alembic upgrade head` — 5 migrations, clean |
| 3. Create test user | Real `POST /auth/register` + login |
| 4-6. Generate + persist | Real `POST /generations` (seed 5001) — real M5 candidate |
| 7. Backup | `pg_dump -Fc` — **37,353 bytes, 0.38s** |
| 8. Destroy | Terminated connections, `DROP DATABASE`, `CREATE DATABASE` — confirmed empty |
| 9. Restore | `pg_restore --clean --if-exists` — **0.51s**, exit 0, all 13 tables back |
| 10. Migrations post-restore | `alembic current` → already at head (no-op, correct) |
| 11. Start application | Fresh `uvicorn` — `/health/ready` returned `ready` on first check |
| 12. Retrieve previous generation | Same pre-backup session cookie — succeeded, real SVG/representation/analysis/verification intact |
| 13. Verify ownership | A second, newly-registered user got the correct 404 on the same id post-restore |
| 14. Verify metadata | seed/is_valid/render_svg/representation/analysis all correct post-restore |
| 15. Verify referential integrity | Direct SQL: exact expected row counts across all 9 tables; explicit orphan-FK check returned **0 orphaned rows** |

Full detail in `docs/DISASTER_RECOVERY.md` section A.1.

**What remains genuinely unaddressed (RED, not downgraded)**: no automated backup
schedule is configured anywhere, because no real production database exists to
configure one against. Supabase's specific managed-backup tooling and connection
pooler were not exercised (plain Docker Postgres was used) — recommended before
trusting this procedure against the actual production database. No RTO/RPO has been
decided (a business decision, not an engineering task).

---

## 13. Staging Results

🔴 **BLOCKED — requires external credential/infrastructure (Vercel + Render +
Supabase + Cloudflare R2 accounts), none of which exist in this environment.**

No staging deployment was attempted or claimed. The backup/restore drill (section 12)
and the Postgres verification (section 4) used a local Docker Postgres container,
which is explicitly NOT staging — this report does not call it staging anywhere.

---

## 14. Production Results

🔴 **BLOCKED — same reason as section 13. Not attempted.** Per the task's own rule:
production deployment may only follow a passing staging deployment, which does not
exist.

---

## 15. GREEN Items

- Backend service config (Dockerfile `$PORT` + migration-on-boot; health/live/ready
  endpoints verified live against SQLite AND real Postgres)
- Docker (real clean `docker build` + `docker run`, non-root user confirmed via
  `whoami` inside the live container, a real generation completed end-to-end through
  it — two real bugs found and fixed doing this, see section 2)
- ML runtime (fail-fast startup validation; dozens of real generations this session,
  including one through the built Docker container)
- Authentication (bcrypt, correct cookie flags, verified live)
- Authorization / ownership (this session's central fix; 11 regression tests; verified
  live with two real users; survived a real backup/restore round-trip)
- Artifact deletion (5/5 required test scenarios, all real)
- Local object storage (save/get/delete/exists/url all exercised via real tests)
- Security headers (verified live on success/error/`/docs` responses; CORS `DELETE`
  bug found and fixed, verified live)
- Frontend (no hardcoded URLs, no fabricated data found — scanned and verified)

## 16. YELLOW Items

- Database/PostgreSQL: real Postgres verified (3 bugs found+fixed); Supabase
  specifically unverified
- Concurrency: real data at all 4 levels against both DBs; Postgres latency numbers
  confounded by a concurrent migration, need a clean re-run
- Object storage/R2: implemented, reviewed, genuinely unverified — no credentials
- Rate limiting: Retry-After + user-isolation verified; still in-process-memory,
  won't survive multiple Render instances without Redis/Valkey
- CI/CD: PR gate verified correct; no staging-deploy/smoke-test stage exists
- Security: most items verified; CSRF relies on SameSite only (a documented design
  choice, not a gap)
- Backup/recovery: real drill executed against Docker Postgres; no schedule against a
  real deployment yet; Supabase-specific behavior unverified

## 17. RED Items

- Staging deployment: not attempted — BLOCKED, no Vercel/Render/Supabase/R2 accounts
- Production deployment: not attempted — depends on staging
- No CI-enforced deploy gate (manual promotion only)
- No automated backup schedule against a real database (none exists yet)

## 18. External Dependencies (BLOCKED items, explicitly)

- **Cloudflare R2**: bucket + credentials. Without these, R2 upload/download/delete/
  missing-object/unauthorized-access/storage-failure cannot be tested for real —
  attempting to fake this would violate the task's explicit rule against fabricating
  verification.
- **Real Supabase Postgres project**: for pooler/pgbouncer-specific verification
  beyond what plain Docker Postgres already covered.
- **Vercel account** (frontend hosting) and **Render account** (backend hosting): for
  any staging or production deployment at all.

---

## 19. Exact Deployment Steps

1. Provision a real Supabase Postgres project; set `DATABASE_URL` on Render.
2. Run `alembic upgrade head` against it (verified against Docker Postgres this
   session, section 4 — do this against a disposable Supabase project/branch first
   if available, not directly against production).
3. Provision a Cloudflare R2 bucket; set `STORAGE_PROVIDER=r2` and the five `R2_*`
   variables; work through the R2 staging checklist (`docs/DEPLOYMENT.md`) before
   trusting it.
4. Set `AUTH_SECRET`, `COOKIE_SECURE=true`, `CORS_ORIGINS` to the exact Vercel
   production origin (`docs/DEPLOYMENT.md` section G/H).
5. Deploy the backend container to Render; configure its health check path as
   `/api/v1/health/ready` (not `/api/v1/health`).
6. Build the frontend with `VITE_API_BASE_URL` set to the Render backend's public
   URL; deploy `frontend/frontend/dist` to Vercel.
7. Point Cloudflare DNS at both.
8. Re-run the concurrency benchmark (section 9) against the real staging stack, with
   NO concurrent schema migrations running, before trusting latency numbers for
   capacity planning.
9. Configure an actual Supabase backup schedule (or a scheduled `pg_dump`); run one
   real restore drill (`docs/DISASTER_RECOVERY.md` section A.1's exact procedure)
   against the real Supabase database before considering backups resolved.
10. Decide on Redis/Valkey-backed rate limiting before scaling past one Render
    instance — not required for a single-instance initial launch.
11. Run the complete E2E flow (signup → generate → analyze → verify → export →
    history → logout) against the real staging URLs in a real browser before
    promoting to production.

---

## 20. Exact Rollback Steps

1. **Backend code**: redeploy the previous Render image/build.
2. **Schema**: `alembic downgrade <previous-revision>` — verified working both
   directions against real Postgres this session (section 4). Check compatibility
   first: a downgrade that drops a column a still-running new-code instance depends
   on will break it — sequence the downgrade before or during the redeploy, not after.
3. **Data**: restore from a `pg_dump` backup using the exact procedure verified in
   section 12 / `docs/DISASTER_RECOVERY.md` section A.1 (`pg_restore --clean
   --if-exists`) — Alembic reverses schema, not data changes.
4. **Frontend**: redeploy/promote the previous Vercel build.
5. **Artifacts**: unaffected by backend/database rollback — R2/local storage keys are
   independent of the DB rows that reference them (a schema downgrade does not delete
   artifacts); a data-level DB restore to an earlier point could reference artifacts
   created after that point that would appear "orphaned" going forward — acceptable
   for a rollback (those artifacts simply become unreferenced, not deleted).
6. **`AUTH_SECRET` rotated by mistake**: not reversible from the new value alone —
   restore the previous secret from wherever it was originally generated/stored, or
   accept all users must log in again.

---

## 21. Final Production Verdict

**NOT PRODUCTION READY.**

Per the stated production declaration rule, PRODUCTION READY requires ALL of:
security checks, authentication, authorization, PostgreSQL verification, migrations,
backup/restore verification, object storage verification, artifact lifecycle,
concurrency, rate limiting, ML runtime, frontend E2E, Docker clean build, CI, staging,
and production smoke tests.

**Genuinely satisfied this session, with evidence**: authentication, authorization
(the session's central fix), migrations, artifact lifecycle, ML runtime, backup/
restore procedure (against Docker Postgres).

**Not satisfied — explicitly BLOCKED, not fabricated**: object storage (R2 — no
credentials), staging deployment (no accounts), production deployment (depends on
staging), a real Supabase-specific backup verification, and a CI-enforced deploy gate.

**Not satisfied — genuine gaps, not blocked, just not done this session**: a clean
(non-confounded) Postgres concurrency re-run, a live-browser frontend E2E click-
through, Redis-backed rate limiting for multi-instance scaling.

The system is closer to deployable than at the start of this session — a severe
authorization vulnerability and three real database bugs were found and fixed with
real evidence, not merely inspected — but staging and production deployment remain
correctly and honestly BLOCKED on external infrastructure this environment does not
have access to.
