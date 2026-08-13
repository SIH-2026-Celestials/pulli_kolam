# PULLI Deployment

This document covers local development, Docker, and production deployment
of the two deployable pieces of PULLI today: the React/Vite frontend and
the FastAPI backend (`api/main.py`). See `docs/DEPLOYMENT_AUDIT.md` for
the full architecture audit this document implements.

There is currently **no database, no queue, no object storage, no GPU,
and no background worker** anywhere in this system. Uploaded images are
ephemeral: written to a temp file for the duration of one request and
deleted immediately after (`api/main.py`). Do not deploy infrastructure
for any of these unless a real feature needs it.

---

## A. Local development

### Backend

```
pip install -r requirements.txt
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

`--reload` is for local development only - never use it in production
(see section E).

### Frontend

```
cd frontend/frontend
npm ci
npm run dev
```

The frontend reads `VITE_API_BASE_URL` (see `.env.example`) at **build
time** via Vite's `import.meta.env`. If unset, it defaults to
`http://localhost:8000` (`frontend/frontend/src/lib/api/client.js`), which
matches the default `uvicorn` command above - no configuration needed for
local development.

### CORS in local development

`api/main.py` reads `CORS_ORIGINS` (comma-separated origins) at startup.
If unset, it falls back to the common Vite dev-server origins
(`http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:3000`,
`http://127.0.0.1:3000`) so `npm run dev` talks to `uvicorn --reload`
without any extra setup. This fallback does **not** apply outside of
local development - see section G.

---

## B. Docker build

```
docker build -t pulli-api .
```

The image contains only the API runtime: `engine/`, `api/`, and the
runtime-required subset of `experiments/m4_1`/`experiments/m4_2` (model
definition modules + the one checkpoint the ML detector loads -
`experiments/m4_2/results/dot_heatmap_net_v2.pt`). Datasets,
training/evaluation data, the frontend, and `.git` are excluded - see
the `Dockerfile` header comment and `.dockerignore` for the exact list
and why each exclusion is safe.

The image is CPU-only. `torch` is installed from PyPI's dedicated CPU
wheel index (`https://download.pytorch.org/whl/cpu`) specifically so no
CUDA/`nvidia-*` packages are pulled in - this project has no GPU code.

---

## C. Docker run

```
docker run --rm -p 8000:8000 \
  -e CORS_ORIGINS=http://localhost:5173 \
  pulli-api
```

`CORS_ORIGINS` is the only environment variable the container needs.
`KMP_DUPLICATE_LIB_OK` is set internally by `api/main.py` - do not set it
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
(`docs/DEPLOYMENT_AUDIT.md` section 9) - that scope was intentionally not
expanded here (no DB/queue to check). The `Dockerfile` also declares a
`HEALTHCHECK` that polls this same endpoint from inside the container -
no new health logic was added.

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
   +-- generation engine    (engine/generation.py - see docs/GENERATION.md
                              for current capability status)
```

There is currently no database, queue, object storage, GPU, or worker in
this architecture, and none should be added speculatively - see
`docs/DEPLOYMENT_AUDIT.md` sections 6-7 for the reasoning (synchronous,
sub-second, stateless endpoints; no job needs anything to persist).

Never run `uvicorn --reload` in production - use the exact command the
`Dockerfile` runs:

```
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

## F. Frontend deployment

Set `VITE_API_BASE_URL` to the deployed backend's URL **at build time**:

```
VITE_API_BASE_URL=https://<backend-domain> npm run build
```

or configure it as a build-time environment variable in your static host
(Vercel/Cloudflare Pages project settings). It cannot be changed after
the build without rebuilding - it is baked into the static JS bundle by
Vite, not read at runtime in the browser.

---

## G. Backend deployment

Set the required runtime environment variable:

```
CORS_ORIGINS=https://<frontend-domain>
```

Use the exact deployed frontend origin (scheme + host, no path, no
trailing slash), comma-separated if there is more than one (e.g. a
preview deployment origin alongside the production one). **Never set
this to `*`** in a deployed environment - `api/main.py`'s dev-only
fallback (section A) does not apply once `CORS_ORIGINS` is set.

---

## H. Production upload limits

`api/main.py` validates upload **content type** only
(`ALLOWED_CONTENT_TYPES` - jpeg/png/webp/bmp); there is currently **no
application-level upload size limit**. This is a known gap, documented in
`docs/DEPLOYMENT_AUDIT.md` section 9.

**Any public deployment must enforce a request body size limit at the
platform or reverse-proxy layer** (e.g. your hosting platform's own
request size cap, or a reverse proxy in front of the container) before
being exposed to untrusted traffic. This document does not specify a
provider-specific number - check the limit your chosen platform already
enforces by default and confirm it's reasonable for a single kolam photo
upload; do not assume one is in place without checking.

Adding an explicit application-level size check (reject oversized
uploads before they're written to a temp file) is a reasonable future
hardening item if the platform-level limit turns out to be absent or too
permissive - not implemented in this pass, since it changes
`api/main.py`'s validation behavior and wasn't part of this task's scope.

---

## Troubleshooting

- **`OMP: Error #15` / process crashes on first request** - `KMP_DUPLICATE_LIB_OK`
  must be set before torch or numpy is imported. It's set at the very top
  of `api/main.py`, before any other import - if this ever moves, the
  crash returns. Do not "fix" this by removing the line.
- **CORS errors in the browser console** - check `CORS_ORIGINS` matches
  the frontend's *exact* origin (scheme + host + port), and that you
  didn't leave a trailing slash.
- **`/api/v1/detect` with `detector=ml` returns 503** - the ML checkpoint
  (`experiments/m4_2/results/dot_heatmap_net_v2.pt`) is missing or failed
  to load. This is intentional (rule: no silent fallback to classical) -
  check `GET /api/v1/health`'s `ml_detector_available` field.

## Rollback

The API is a single stateless container with no persisted state - rolling
back means redeploying the previous image tag on your platform. The
frontend is a static build - rolling back means redeploying the previous
`dist/` build or, on Vercel/Cloudflare Pages, promoting a previous
deployment. Neither requires any data migration.

## Cost considerations

CPU-only, sub-second requests, no persistent storage: this fits
comfortably in most platforms' free or lowest-cost tier (Render/Fly.io/
Railway free or hobby tier for the API container; Vercel/Cloudflare Pages
free tier for the static frontend). There is no GPU cost, database cost,
or storage cost today. Revisit this section if/when a future milestone
(M4.2 generation at scale, M5) introduces a real need for persistence or
heavier compute.
