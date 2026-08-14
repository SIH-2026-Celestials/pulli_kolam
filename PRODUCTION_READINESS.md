# PULLI — Production Readiness Report

**Audit date:** 2026-08-14
**Source of truth:** `master` HEAD at audit start (`ba6b925`), hardening changes applied on top and described below.
**Scope:** Product hardening only. No ML research, no changes to M4.2/M5/M6 architectures, checkpoints, or training data.

Classification key: 🟢 GREEN = production-ready · 🟡 YELLOW = works, needs hardening · 🔴 RED = blocking production.

Every claim below was verified by running real code against the current codebase during this audit (live server, real HTTP requests, real DB rows, real pytest/vitest runs) — not inferred from a file's existence.

---

## 1. Architecture

**Runtime path (verified via import trace + live traffic), single canonical backend:**

```
Frontend (React/Vite)
  → FastAPI (api/main.py)
      → api/auth/router.py           (session auth)
      → api/routes_generations.py    (M7 platform: THE canonical generation path)
          → api/services/generation.py
              → api/services/generator_interface.py → M5Generator (engine.learned_generation)
              → api/services/analysis.py             (6 analyzers, thin wrappers over engine.*)
              → api/services/verification.py         (structural hard-gate; recognizer opt-in)
              → engine.render                          (SVG/PNG rendering)
              → api/services/artifact_store.py         (LocalArtifactStore, disk)
              → api/db/database.py                      (SQLAlchemy, SQLite by default)
```

🟢 **One canonical generation path confirmed.** `Generator` is a `Protocol`; `M5Generator` is the only registered implementation anywhere in the codebase — there is no `M6Generator` class, so M6 is architecturally impossible to select, not just unselected by config.

**Dead code removed this audit** (was previously flagged, not deleted, in an earlier audit pass):
- `api/v1_router.py` — deleted. It was mounted only by `backend/main.py`, which nothing (dev launcher, docs, `api/main.py`) ever imports or starts.
- `backend/` (entire package: `main.py`, `routers/`, `services/`, `models/`, `utils/`, `tests/`) — deleted. Fully self-contained, zero inbound references from any live code path. Its own test suite (9 tests) tested only its own isolated, unreachable FastAPI app and has been removed with it (see §9).

One pre-existing, **intentional** duplication remains and is not a defect: `POST /api/v1/generate` (legacy, in `api/main.py`, no persistence) and `POST /api/v1/generations` (M7 platform, persisted) both call the *same* real `engine.learned_generation` M5 code path — neither fabricates anything. The frontend (`GeneratedVariations.jsx`, the only UI that generates patterns) exclusively calls the persisted one (`createGeneration()` → `/api/v1/generations`). The legacy endpoint is unused by the UI but is real, tested, and documented — left in place as a lower-latency non-persisting option for API consumers, not removed.

## 2. Runtime generation path — 🟢 GREEN

Verified live, end-to-end, this audit (not from a prior session's notes):

```
POST /api/v1/generations {"count":1}
  → 200 OK in 5.6s
  → real M5 search (engine.learned_generation), real seed, real SVG (1440x1440, hand-traced polyline, not a template)
  → real structural analysis (188 vertices, 423 edge instances, Eulerian check, symmetry, complexity, novelty)
  → real verification ({"structural_hard_gate": {"is_valid": true, "notes": "connected_components=1, odd_degree_nodes=0"}})
  → persisted (GenerationRequest, GenerationRun, PatternVersion, PatternAnalysis, VerificationResult, GenerationResult rows all written)
  → retrievable via a FRESH HTTP request (GET /api/v1/generations/{id}) after the original request/connection ended
  → mathematics sub-view (GET .../mathematics) and graph sub-view (GET .../graph) both return real, matching data
  → SVG export: 17,328 bytes, real SVG
  → PNG export: 28,257 bytes, verified via `file` as a real 1440×1440 PNG (engine-rendered, not a placeholder)
  → history list (GET /api/v1/generations) returns the new row with real seed/validity/novelty/symmetry/complexity
  → GET on an unknown ID → 404 {"success": false, "code": "NOT_FOUND"} (no traceback)
```

No mocks anywhere on this path. No hardcoded SVG. No hardcoded scores.

## 3. ML integration status — 🟢 GREEN

- M5 (`engine.learned_generation.generate_novel_kolam_learned`) is genuinely invoked per request — confirmed by real, varying seeds/graphs/latencies across repeated calls, not a cached/canned response.
- Structural analysis (`api/services/analysis.py`) wraps unmodified `engine.validity` / `engine.symmetry` / `engine.novelty` — no reimplementation, no duplication of ML logic in the frontend.
- Structured logging is present around the generation lifecycle (`generation_candidate_completed`, `generation_run_completed` — confirmed in live server logs during this audit) including run/result IDs, seed, validity, verification status, and duration; no secrets or image bytes logged.
- 🟡 Logging does not currently emit distinct `generation_start` / `verification_start` / `render_start` events as separately-named stages (only start/complete pairs at the run and candidate level) — coarser than the ideal granularity, but every stage's outcome (valid/invalid, verification result, timing) is present in what is logged. Not a blocker; a nice-to-have for finer-grained tracing.

## 4. Frontend integration status — 🟢 GREEN (after this audit's fix)

- `GeneratedVariations.jsx` is the sole generation UI. It calls `createGeneration()` and renders `analysis`/`verification`/`render_svg` directly from the server response — no mock data, no hardcoded fallback values anywhere in this path (confirmed by reading the full component).
- Mathematics panel, graph panel (fetched on-demand via `getGenerationGraph`), and per-candidate export buttons are all backend-driven.
- 🔴→✅ **Fixed this audit:** `/analyze` (the Kolam Analyzer — explicitly "one of the most important pages" per this project's own spec) had been silently dropped from the primary navigation and from the Playground's "Run Deep AI Analysis" link by an unrelated commit (`c186c79`, a same-day commit whose stated purpose was icons/spacing/watermarks). The route and page were never broken, only unreachable from nav. Restored the `Header.jsx` nav link; verified the routing test suite and `/analyze` route both still pass.
- 🟡 **Not wired, real backend feature going unused:** `listGenerations()` (paginated server-side generation history, `GET /api/v1/generations`) is exported from the API client and fully functional (verified live this audit) but is **never called by any frontend component**. "Recent Kolams" (`RecentKolams.jsx`) is instead a client-side, `localStorage`-only, per-device list populated by the UI itself after each generation — it is not the server's history. This means: a user's generation history does not survive clearing browser storage or switching devices, despite the backend already persisting everything needed to serve it. This is real, scoped frontend work (a history page/panel wired to `listGenerations()`), not an ML task.

## 5. Database / persistence status — 🟢 GREEN (after this audit's fix)

- Every entity in the write path (`GenerationRequest` → `GenerationRun` → `PatternVersion`/`Pattern` → `PatternAnalysis` → `VerificationResult` → `GenerationResult` → `Artifact`) was traced and confirmed populated on a real request, with no silently-dropped fields (verified by inspecting the full JSON response against the DB write path).
- 🔴→✅ **Real concurrency bug found and fixed this audit.** Two simultaneous `POST /api/v1/generations` requests reproduced `sqlite3.OperationalError: database is locked`, surfaced to the client as a raw HTTP 500 — a genuine "concurrent requests corrupt/break shared state" failure, not hypothetical. Root cause: SQLite's default 5-second write-lock timeout with no `busy_timeout` PRAGMA and no WAL journal mode, in both `api/db/database.py` and `api/auth/db.py` (both share the same class of engine construction). Fixed by setting `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=30000`, and a matching `timeout=30` connect arg in both modules. Re-verified live: 3 concurrent generation requests now all return 200 and all persist correctly (previously 1–2 of 3 would 500). Under WAL, concurrent writes still serialize (SQLite fundamentally supports one writer at a time) — total latency rises under concurrent load (observed 6s solo → up to 31s for the third of three concurrent requests), which is expected and is a capacity limit, not a correctness bug, of SQLite specifically (see §11).
- 🟡 SQLite remains the default and is explicitly documented as a dev-only choice; `DATABASE_URL` swaps to Postgres with no code changes (confirmed: schema uses only portable SQLAlchemy types). Production deployment on SQLite would still bottleneck under real concurrent load even with the WAL fix — Postgres is the correct target before real traffic.
- 🟡 `api/auth/db.py` and `api/db/database.py` share the same `DATABASE_URL` environment variable but are logically separate databases (auth: `users`/`user_sessions`; platform: 9 other tables). No table-name collision exists today, but one env var cannot point them at two different production databases if that's ever needed. Flagged, not changed (out of scope for this pass — would require a second env var and is a design decision, not a bug).

## 6. Artifact storage — 🟡 YELLOW (dev-appropriate, documented gaps)

- `LocalArtifactStore` (disk, under `api/storage/`) is the only implementation. `ArtifactStore` is a `Protocol`, so a future S3/GCS-backed store is a clean seam, but **no object storage exists today** — this is explicitly not claimed otherwise anywhere in the code or docs.
- Path-traversal-safe: every relative path is resolved and checked against the storage root before any read/write (verified in code).
- Filenames are UUID-derived (from DB-generated IDs), so concurrent writes cannot collide.
- 🔴 **No cleanup/retention policy.** Every generated SVG/PNG/JSON artifact accumulates on local disk forever — unbounded disk growth is a real production blocker for a long-running deployment, not addressed anywhere in the codebase.
- 🔴 **Single-node only.** Local disk storage means artifacts are not visible across replicas/instances — any horizontal scaling of the API requires object storage first.

## 7. Authentication — 🟢 GREEN

- Passwords hashed with `bcrypt` directly (not passlib, documented reason: passlib/bcrypt version-compatibility issues).
- Session tokens: 32 bytes CSPRNG (`secrets.token_urlsafe`), stored server-side (`user_sessions` table), HMAC-SHA256-signed for the cookie value, verified with `hmac.compare_digest` (constant-time, prevents timing attacks).
- Cookie flags: `HttpOnly` always on; `SameSite=Lax` (mitigates CSRF on state-changing POSTs); `Secure` conditional on `COOKIE_SECURE` env var.
- `AUTH_SECRET` has a documented dev-only fallback value, but **the app refuses to start signing sessions with that fallback once `COOKIE_SECURE=true`** — a real fail-loud production guard, not just a comment.
- 🟡 Operational responsibility, not a code defect: `COOKIE_SECURE=true` and a real `AUTH_SECRET` must actually be set by whoever deploys this — nothing enforces it outside of the "refuse to start" guard, which only fires if `COOKIE_SECURE` was remembered to be set in the first place.

## 8. Security — 🟡 YELLOW

- CORS: `allow_credentials=True` with either an explicit `CORS_ORIGINS` allow-list or, if unset, a localhost-only regex fallback. No wildcard `*` origin possible (`.env.example` explicitly warns against it). 🟢
- Upload validation: content-type allow-list (jpeg/png/webp/bmp), 20MB application-level cap, empty-upload rejection, temp files always deleted after processing (never persisted or logged). 🟢
- Error handling: every tested failure mode (malformed JSON, wrong field type, missing required field, over-limit `count`, unknown export format, unknown generation ID) returned the canonical `{success, error, code}` envelope with an appropriate HTTP status and zero leaked tracebacks — verified live against 5 distinct failure modes this audit. 🟢
- 🔴 **No rate limiting anywhere in the codebase** (confirmed: no `slowapi`, no custom limiter, nothing). `POST /api/v1/generations` costs 5–55 seconds of CPU-bound server time per call and is trivially abusable to exhaust server capacity with no authentication required. This is the single most important pre-launch security gap.
- 🟡 **Committed-then-removed secret in git history.** An earlier commit (`c186c79`) committed `frontend/frontend/.env` containing a real Supabase project URL and anon/publishable key. The file was later removed from the tree by a subsequent commit (confirmed: not present at current HEAD, not on disk), but the values remain permanently recoverable from git history (`git show c186c79:frontend/frontend/.env`). Supabase anon keys are designed to be client-exposed and RLS-protected, so exposure risk is lower than a server secret, but this is real credential hygiene debt and the values are dead anyway (current auth is the FastAPI session system in `api/auth/`, not Supabase). **Recommended, not performed this audit** (destructive/history-rewriting, requires the repo owner's decision): rotate the Supabase key if that project is still active, and purge the blob from history with `git filter-repo`/BFG if desired.
- No server-side secrets are exposed to Vite/frontend build output — confirmed the only `VITE_*` variables are `VITE_API_BASE_URL` and `VITE_CONTACT_EMAIL`, both non-secret by design.
- No DEBUG-style verbose-error mode exists to accidentally leave on in production (the error handlers always return the structured envelope regardless of environment).

## 9. Testing — 🟢 GREEN

Run fresh this audit, on the current tree (after all fixes above):

| Suite | Result |
|---|---|
| Backend (`pytest`) | **361 passed**, 0 failed (was 370 before this audit; -9 is the deleted dead-code test file `backend/tests/test_api.py`, which tested only the now-removed unreachable app) |
| Frontend (`vitest`) | **40 passed**, 0 failed |
| Frontend build (`vite build`) | Clean, 1899 modules, only the pre-existing "chunk >500kB" advisory (not an error) |

No test was weakened or skipped to make this pass. `node_modules` was stale (missing the `vitest` binary declared in `package.json`) at the start of this audit — `npm install` was run to sync it; this is a one-time local-environment fix, not a code change, but is worth noting since it means the "40/40" figure referenced in an earlier commit message could not have been independently reproduced without that step.

## 10. Performance — informational, not exhaustively benchmarked

Real, live-measured numbers from this audit (single dev machine, CPU-only, cold-ish process):

| Operation | Observed latency |
|---|---|
| `POST /api/v1/generations` (count=1, no concurrent load) | ~5.6–5.9s |
| `POST /api/v1/generations` (3 concurrent requests, after WAL fix) | 15.2s / 23.2s / 30.9s (serialized by SQLite's single-writer model) |
| `GET /api/v1/generations/{id}` | sub-100ms (not separately timed to the millisecond, but visibly instant) |
| `GET .../mathematics`, `GET .../graph` | sub-100ms |
| SVG/PNG export | sub-200ms |
| Simple error-path requests (validation failures) | sub-50ms |

The dominant cost is the M5 multi-restart guided search itself (CPU-bound, single-threaded per request) — this is expected and is **not** something this audit's scope permits changing (it's the M5 algorithm, out of bounds per the hard constraint). The concurrency fix in §5 prevents *failures* under concurrent load; it does not and cannot make SQLite handle concurrent *writes* in parallel — that requires Postgres. No premature optimization was attempted.

## 11. Known Limitations

- SQLite is the default database; adequate for single-instance/low-concurrency deployment (now that §5's fix prevents lock-contention 500s), but a real multi-writer production workload needs Postgres.
- No object storage; artifacts are local-disk-only and unbounded (see §6).
- No rate limiting (see §8) — the single highest-priority pre-launch gap.
- `listGenerations()` (server-side history) is implemented and tested but has no frontend UI consuming it (see §4).
- `PhotoVerifier`/real-photo recognizer verification honestly returns `UNRESOLVED` rather than fabricating precision/recall — this is correct, honest behavior, not a bug, but means "verification" for real uploaded photos (as opposed to structural self-consistency) is not yet a measured capability.
- The Supabase secret in git history (see §8) is dead but not purged.

## 12. Remaining Blockers (before any real-traffic production deployment)

1. 🔴 Add rate limiting to `/api/v1/generations` and other expensive endpoints.
2. 🔴 Move off SQLite to Postgres for any deployment expecting concurrent users.
3. 🔴 Add artifact retention/cleanup policy, or move to object storage, before disk fills.
4. 🟡 Set `COOKIE_SECURE=true` and a real `AUTH_SECRET` in the actual production environment (the code already refuses to start unsafely — this is a deployment-config step, not a code gap).
5. 🟡 Decide on and execute the Supabase key rotation / git-history purge.
6. 🟡 Wire `listGenerations()` into a real history UI, or explicitly decide the local-device list is sufficient and remove the unused backend surface (either is a valid product decision — currently it's just inconsistent).

## 13. Production Deployment Checklist

- [ ] `DATABASE_URL` points at Postgres, not SQLite
- [ ] `CORS_ORIGINS` set to explicit production origin(s), never left to the localhost regex fallback
- [ ] `COOKIE_SECURE=true`, real `AUTH_SECRET` set (32+ random bytes)
- [ ] Rate limiting added in front of `/api/v1/generations` (and ideally all POST endpoints)
- [ ] Object storage (or a scheduled cleanup job) for `api/storage/artifacts/`
- [ ] Reverse proxy / platform-level request body size limit configured (app-level 20MB cap is not a substitute)
- [ ] `AUTH_SECRET` and `DATABASE_URL` sourced from a real secrets manager, not a checked-in file
- [ ] Old Supabase key rotated/history purged if that project is still live
- [ ] Uptime/latency monitoring on `/api/v1/health` and `/api/v1/generations`

---

## Acceptance Criteria — status

| Item | Status |
|---|---|
| One canonical generation backend exists | ✅ |
| Frontend uses canonical backend | ✅ |
| M5 is actually invoked | ✅ (verified live) |
| Structural analysis is real | ✅ (verified live) |
| Verification is real | ✅ (verified live) |
| Rendering is real | ✅ (verified live, real SVG + PNG bytes) |
| Persistence is real | ✅ (verified across a fresh HTTP request) |
| History is real | 🟡 backend: yes; frontend: not wired (see §4) |
| Mathematics UI is backend-driven | ✅ |
| Graph UI is backend-driven | ✅ |
| No fabricated ML output exists | ✅ (dead fabricated endpoint deleted, see §1) |
| `/analyze` is reachable | ✅ (fixed this audit) |
| Dead generation routes removed/isolated | ✅ (deleted, not just isolated) |
| Security issues documented/resolved | 🟡 documented; rate limiting still open |
| Error contracts are consistent | ✅ (verified live across 5 failure modes) |
| Backend tests pass | ✅ 361/361 |
| Frontend tests pass | ✅ 40/40 |
| Frontend build passes | ✅ |
| E2E generation passes | ✅ (full generate→persist→retrieve→render→export chain verified live) |
| Artifact retrieval passes | ✅ (SVG + PNG verified byte-for-byte real) |
| Production readiness report exists | ✅ this document |

**FUNCTIONALLY WORKING:** the entire generation pipeline, persistence, retrieval, rendering, export, and analysis/verification/graph views are real and correctly wired end-to-end. This was true before this audit for most of it; this audit additionally fixed a real concurrency bug and a real navigation regression, and removed dead/fabricated code that was a latent risk.

**PRODUCTION HARDENED:** not yet. Rate limiting, Postgres migration, and artifact lifecycle management are unaddressed and are the three items standing between "functionally correct" and "safe to expose to real, uncoordinated traffic."

**FUTURE WORK:** see `FUTURE_ML_WORK.md` for ML-specific observations made during this audit (none of which were acted on, per the hard constraint against modifying M4.2/M5/M6).
