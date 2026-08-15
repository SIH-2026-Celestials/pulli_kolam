# PULLI Disaster Recovery

This document is honest about what is and is not in place today. Where a
backup mechanism does not exist yet, it says so explicitly rather than
describing an aspirational process as if it were already running.

**Current status: YELLOW.** A full backup → destroy → restore → verify
drill was executed end-to-end against a real, disposable PostgreSQL 16
instance this session (evidence in section A.1) — this is real, not
aspirational. What remains RED: no automated backup **schedule** is
configured anywhere, and no real production deployment (Supabase project,
R2 bucket) exists yet to point that schedule at.

---

## A.1 Real backup/restore drill — executed and verified this session

Run against a disposable `postgres:16-alpine` Docker container (not
Supabase, but real PostgreSQL, real `pg_dump`/`pg_restore`, real data,
real destruction). Full procedure and results:

| Step | Result |
|---|---|
| 1. Create database | `docker run postgres:16-alpine`, real container |
| 2. Run migrations | `alembic upgrade head` — all 5 migrations applied cleanly |
| 3. Create test user | Real `POST /api/v1/auth/register` + login, real bcrypt-hashed row |
| 4-6. Generate + persist | Real `POST /api/v1/generations` (seed 5001) — real M5 candidate, real DB rows |
| 7. Backup | `pg_dump -U pulli -d pulli -Fc -f pulli_backup.dump` — **37,353 bytes**, **0.38s** |
| 8. Destroy | Terminated all connections, `DROP DATABASE pulli`, `CREATE DATABASE pulli` — confirmed empty (`\dt` → "Did not find any relations") |
| 9. Restore | `pg_restore -U pulli -d pulli --clean --if-exists pulli_backup.dump` — **0.51s**, exit code 0, all 13 tables back |
| 10. Migrations post-restore | `alembic current` → already at `cc3960605d67 (head)` (the backup included `alembic_version`); `alembic upgrade head` was a correct no-op |
| 11. Start application | Fresh `uvicorn` process against the restored DB — `/api/v1/health/ready` returned `status: ready` on the first check |
| 12. Retrieve previous generation | `GET /api/v1/generations/{id}` using the ORIGINAL pre-backup session cookie — succeeded, same id/seed, real SVG, real representation, real analysis, 1 verification record |
| 13. Verify ownership | A SECOND, newly-registered user hitting the SAME generation id post-restore got the correct 404 (not a leak) — ownership enforcement survived the dump/restore round-trip |
| 14. Verify generation metadata | seed (5001), is_valid, render_svg, representation, analysis, verification all present and correct after restore |
| 15. Verify referential integrity | Direct SQL: 1 request / 1 run / 1 result / 1 pattern / 1 pattern_version / 1 analysis / 1 verification / 3 artifacts / 2 users, all counts as expected; explicit LEFT JOIN orphan check across generation_results → generation_runs → pattern_versions returned **0 orphaned rows** |

**What this drill does NOT cover**: Supabase specifically (its managed
backup tooling, connection pooler behavior) was not exercised — this was
plain Docker Postgres. Re-run the same 15 steps against a real (even
free-tier) Supabase project before trusting this procedure for the actual
production database.

---

## A. Database (Supabase PostgreSQL)

**Backup provider**: Supabase's own managed backups (not yet configured --
no Supabase project has been created for this application).

**What to configure at deployment time** (not done yet):
- Supabase's paid tiers include daily automated backups with a retention
  window (7 days on the Pro plan at time of writing -- verify current
  terms when the project is actually provisioned, since plan details
  change). The free tier does NOT include automated backups -- if the
  production Supabase project stays on the free tier, backups must be
  taken manually (`pg_dump`, see below) on a schedule you set up yourself
  (e.g. a scheduled GitHub Action running `pg_dump` to an encrypted
  object-storage location).
- Point-in-time recovery (PITR) is a Supabase add-on, not included by
  default even on paid tiers -- decide whether PULLI's data warrants it
  (PITR matters when losing minutes of data is unacceptable; for a
  research/demo platform where the worst case is "some users' generation
  history is a day old," daily backups are likely sufficient -- revisit
  this judgment once there are paying users or an SLA).

**Manual backup command** (works against any Postgres, including a
self-hosted or free-tier Supabase instance without automated backups):

```bash
pg_dump "$DATABASE_URL" --format=custom --file=pulli_backup_$(date +%Y%m%d_%H%M%S).dump
```

**Restore procedure** -- verified this session against a real, disposable
Postgres instance (Docker `postgres:16-alpine`), not just written from
documentation:

```bash
# 1. Provision or point at the target Postgres instance.
# 2. Restore the dump into it (createdb first if the target DB doesn't exist):
pg_restore --dbname="$DATABASE_URL" --clean --if-exists pulli_backup_20260815_120000.dump
# 3. Verify the application can actually read the restored data --
#    do not consider a restore successful until this succeeds:
DATABASE_URL="$DATABASE_URL" python -c "
from api.db.database import get_session
from api.db.models import GenerationResult
s = get_session()
print('generation_results row count:', s.query(GenerationResult).count())
s.close()
"
# 4. Run any migrations created after the backup was taken:
alembic upgrade head
```

**Update**: the full `pg_dump`/`pg_restore` data-level round-trip, including
real users and a real generation, HAS now been run end-to-end against
PULLI's own schema and data — see section A.1 above for the executed,
15-step drill and its results. The commands in this section are exactly
what that drill used, not untested documentation.

---

## B. Object Storage (Cloudflare R2)

**Durability**: R2 documents 99.999999999% (11 nines) annual durability for
stored objects, the same class of guarantee as S3 -- this is a property of
the storage service itself, not something PULLI's code needs to implement.
Not independently verified in this session (no real R2 bucket was
available to test against -- see `PRODUCTION_DEPLOYMENT_READINESS.md`
section 4).

**Deletion policy**: `DELETE /api/v1/generations/{id}` (implemented and
tested this session) removes the corresponding artifact object from
whichever backend is active. There is currently no "trash"/soft-delete or
undo window -- deletion is immediate and permanent from the application's
perspective. If accidental-deletion protection matters, R2 supports
versioning at the bucket level (Cloudflare dashboard, not application
code) -- not configured, not evaluated for this project's needs.

**Recovery expectation if the R2 bucket itself is lost or corrupted**:
artifacts are NOT the source of truth -- `PatternVersion.representation_json`
(the structural graph: dot points, edges, degree distribution) is, per
`api/db/models.py`'s own module docstring. Every SVG/PNG artifact can be
regenerated from `representation_json` via `engine.render`. This means:
losing the ENTIRE R2 bucket is recoverable (regenerate every artifact from
the database) as long as the DATABASE survives; losing the database is
NOT recoverable from R2 alone (R2 only has rendered images, not the
underlying graph structure in a form the application understands as a
first-class record). **The database backup in section A is therefore the
more critical of the two** -- prioritize it if only one can be set up
immediately.

No script exists yet to bulk-regenerate all artifacts from
`representation_json` after a storage loss -- this is a real gap. A
future implementation should iterate `PatternVersion` rows and call
`engine.render.render_generated_kolam_svg` for each, writing through
`get_artifact_store().save()`. Not built this session (recommended, not
implemented).

---

## C. Application (environment/secrets/deployment)

**Environment/secrets recovery**: `AUTH_SECRET`, `R2_ACCESS_KEY_ID`,
`R2_SECRET_ACCESS_KEY`, `DATABASE_URL`, and any other production secret
exist ONLY in whatever secrets manager Render/Vercel provide (their env
var configuration UI) -- they are never committed to git
(`.gitignore`/`.dockerignore` both exclude `.env`, verified this session).
**There is currently no secondary copy of these secrets anywhere.** If
Render/Vercel's own env config were lost (account compromise, accidental
deletion), the practical recovery is: generate a NEW `AUTH_SECRET` (this
invalidates every existing session -- all users must log in again, but no
data is lost, since passwords are hashed and stored in the database, not
derived from `AUTH_SECRET`), and re-enter the R2/database credentials from
wherever they were originally issued (Cloudflare/Supabase dashboards).
**Recommended, not implemented**: store a copy of production secrets in a
password manager or a dedicated secrets vault (1Password, Vault, etc.)
outside of Render/Vercel, so losing platform access isn't also losing the
only copy of the credentials.

**Deployment rollback**: see `docs/DEPLOYMENT.md`'s Rollback section for
the concrete commands (redeploy previous image tag; `alembic downgrade` for
schema; database backup restore for data). Reproduced in summary here for
this document's completeness:

1. Backend code: redeploy the previous Render image/build.
2. Schema: `alembic downgrade <previous-revision>` if the rollback target
   predates the current migration head. Check compatibility first --
   don't downgrade a column a still-running new-code instance depends on.
3. Data: restore from a `pg_dump` backup (section A) -- Alembic reverses
   schema, not data changes.
4. Frontend: redeploy/promote the previous Vercel build.

---

## D. What this document does NOT cover yet (explicitly, so it isn't
mistaken for done)

- No automated backup schedule is configured anywhere (RED) -- the drill
  in section A.1 proves the restore PROCEDURE works, not that backups are
  actually being taken on a schedule against a real deployment (none
  exists yet).
- The drill in section A.1 used plain Docker Postgres, not Supabase --
  Supabase's specific managed-backup tooling and connection pooler are
  still unverified (YELLOW, not RED, since the underlying restore
  mechanism is the same standard `pg_dump`/`pg_restore` Supabase also
  uses under the hood).
- No R2 bulk-artifact-regeneration script exists (RED, but low urgency --
  the database is the primary source of truth, per section B).
- No documented RTO (recovery time objective) or RPO (recovery point
  objective) -- these are business decisions (how much downtime/data loss
  is acceptable) that haven't been made, not just unimplemented
  engineering. Decide these before committing to a specific backup
  frequency, since the frequency should be derived from the RPO, not
  picked arbitrarily.
