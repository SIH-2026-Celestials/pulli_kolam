# PULLI Deployment Audit

Date: 2026-08-14
Branch audited: `feature/generation-pipeline`
Baseline test run: `python -m pytest -q` → **171 passed** (15.7s, CPU only)

This document is a factual snapshot of the repository as it exists today.
No code was modified to produce it.

---

## 1. Architecture (as it exists today)

PULLI is **already three components**, not a greenfield design problem:

```
frontend/frontend/          React 19 + Vite 8 SPA (react-router-dom v7)
  src/lib/api/client.js      -- centralized fetch client, reads VITE_API_BASE_URL
                                 (defaults to http://localhost:8000)
                                 ALREADY calls the real backend, not a simulation,
                                 for /health, /model, /detect, /analyze,
                                 /reconstruct, /compare-detectors.

api/                         FastAPI service (api/main.py), the ONLY backend
  main.py                    server in the repo. Endpoints:
  detectors.py                 GET  /api/v1/health
  canonical.py                 GET  /api/v1/model
  reconstruct_adapter.py       POST /api/v1/detect
  schemas.py                   POST /api/v1/analyze
  tests/test_api.py            POST /api/v1/reconstruct
                                POST /api/v1/compare-detectors
                              Synchronous, request/response, no job queue.
                              Uploaded images -> tempfile -> deleted after
                              the request. Nothing persisted server-side.

engine/                      Pure deterministic research engine (numpy/scipy/
                              opencv/networkx). No FastAPI/torch dependency.
                              dataset.py, image_io.py, motifs.py, symmetry.py,
                              validity.py, reconstruction.py, novelty.py,
                              generation.py, generation_api.py, render.py,
                              ml_contract.py (FROZEN - do not touch), etc.

experiments/m4_1, m4_2       PyTorch lattice-detection research + trained
                              checkpoints. Only imported when detector=ml.
```

Two detector backends exist behind one API:
- `classical` (default everywhere, per `docs/M4_2_API.md`) - pure OpenCV/numpy/scipy, no ML, no GPU.
- `ml` - PyTorch CNN, CPU-inference-sized checkpoint, loaded lazily, **never** silently substituted for classical on failure (explicit HTTP 503).

**Key finding: Phase 9 (frontend↔API integration) in the task brief is already done.** The frontend is not calling a mock/simulated pipeline for the Analyze/Detect flow - `client.js` hits real endpoints. (There may still be simulated/demo content elsewhere in the UI, e.g. the homepage "Live Analysis Pipeline" showcase - not verified here, out of scope for this audit pass.)

---

## 2. Runtime dependencies

`requirements.txt` (single file, whole repo):
```
numpy, pandas, networkx, matplotlib, scipy, scikit-image, opencv-python, pytest
torch            # experiments/m4_1, m4_2 only - NOT imported by engine/
fastapi, uvicorn, python-multipart   # api/ only - NOT imported by engine/
```
No `requirements-api.txt` / `requirements-engine.txt` split exists yet - one flat file serves all three surfaces. `opencv-python` (full build, not `opencv-python-headless`) pulls in GTK/X11 shared libs that are dead weight in a headless container.

Python: developed against 3.13.5 locally; CI pins **3.11**. No `pyproject.toml`/lockfile - versions are unpinned (`numpy` not `numpy==x.y.z`), so builds are not fully reproducible.

Frontend (`frontend/frontend/package.json`): React 19.2, Vite 8.2, react-router-dom 7, lucide-react. Small, sane dependency set - no unnecessary UI framework. Node 20 pinned in CI; local Node is v26 (works, but CI is the source of truth).

## 3. Build dependencies

- Backend: none beyond `pip install -r requirements.txt`. No compiled extensions besides what numpy/scipy/opencv wheels bring (prebuilt manylinux wheels exist for all of these - no native toolchain needed in the container).
- Frontend: `npm ci && npm run build` → static `dist/` (Vite). CI already runs lint + build (`.github/workflows/ci.yml`, `frontend-build` job).

## 4. ML dependencies

- `experiments/m4_2/results/dot_heatmap_net_v2.pt` - **1.53 MB**, CPU inference, loaded lazily inside `api/detectors.py` only when `detector=ml` is requested.
- `experiments/m4_1/results/dot_heatmap_net.pt` - 248 KB, earlier checkpoint, referenced by `experiments/m4_1` tests, not by `api/`.
- **No GPU dependency anywhere.** Torch is CPU-only usage; checkpoints are small heatmap CNNs, not LLM-scale models.
- Known landmine (documented in `api/main.py`'s own docstring and `docs/M4_2_MODEL.md`): loading both torch and MKL-linked numpy/scipy in the same process triggers an OpenMP DLL conflict (`OMP: Error #15`) unless `KMP_DUPLICATE_LIB_OK=TRUE` is set before either import. This is already handled at the top of `api/main.py`. **Preserve this exact placement** - moving the `os.environ.setdefault` line after any torch/numpy import will reintroduce the crash.
- `experiments/m4_1/model.py` / `experiments/m4_2/model.py` define `MODEL_INPUT_SIZE`/`HEATMAP_SIZE` and are imported live by `/api/v1/model` - so the `experiments/` tree is a **runtime dependency of the API**, not just a research scratch area. It cannot be excluded from the deployed backend image.

## 5. Data dependencies

| Directory | Size | Used by |
|---|---|---|
| `kolam_data/` | 77 MB | dataset loader (`engine/dataset.py`), frontend Explore/Gallery page assets are a separate copy under `frontend/frontend/src/assets/kolam19/` |
| `real_photos/` | 71 MB | real-photo evaluation corpus (`validate_real_photos.py`), has a license/attribution `MANIFEST.md` that is explicitly un-gitignored |
| `synthetic_photos/`, `synthetic_photos_heldout/` | ~2.2 MB combined | synthetic evaluation corpora |
| `diagnostics/` | 8.2 MB | M4.1 heatmap diagnostic artifacts |
| `experiments/m4_1/data`, `experiments/m4_2/data` | (train/val/test splits, not sized above) | ML training/eval only, not needed at inference time |

None of this is required by the **running API** at request time except the two `.pt` checkpoints and `engine/`'s pure-Python logic (the classical detector needs no bundled dataset - it operates on the uploaded image). `kolam_data/` is only needed if/when an endpoint is added that serves dataset patterns directly (currently the frontend's Explore/Gallery page bundles its own copy of kolam19 images as static assets, not fetched from the API).

## 6. Storage requirements

- **No database exists anywhere in the repo.** No SQLAlchemy, no Postgres, no sqlite file, no ORM.
- **No object storage integration exists.** Uploaded images are written to `tempfile.mkstemp()` and `os.unlink()`'d in a `finally` block before the response returns - by design, per `api/main.py`'s docstring ("never persisted... never logged").
- No job/queue table - every endpoint is synchronous request→response.

## 7. Compute requirements

- CPU-only. No CUDA imports, no `.cuda()`/`.to('cuda')` calls found.
- Classical detection (OpenCV/scipy) dominates request latency; ML detection is a small CNN forward pass on a 256×256 input, sub-200ms per `docs/M4_2_API.md` sample responses.
- No evidence of memory-heavy operations beyond typical OpenCV image buffers. A single low-tier container (0.5-1 vCPU, 512MB-1GB RAM) is sufficient for demo-scale traffic.

## 8. Environment variables

Currently in use:
- `VITE_API_BASE_URL` (frontend, build-time, Vite convention) - defaults to `http://localhost:8000` if unset.
- `KMP_DUPLICATE_LIB_OK` - set internally by `api/main.py`, not meant to be operator-configured.

That's it. **No `.env` file, no `.env.example`, no secrets, no API keys, no DATABASE_URL, no CORS_ORIGINS anywhere in the repo today.**

## 9. Current blockers

1. **No CORS middleware in `api/main.py`.** A browser-hosted frontend on a different origin than the API (any real deployment split) will have its `fetch()` calls blocked by the browser today. This is the single concrete blocker to a two-service deployment.
2. **No `Dockerfile`/`docker-compose.yml` anywhere in the repo** (confirmed by search) - nothing to containerize yet.
3. **No health-check semantics beyond `/api/v1/health`'s existence check** - it reports whether the ML checkpoint file exists on disk, not whether the process is otherwise healthy; sufficient for a basic platform health probe but worth knowing.
4. **`opencv-python` (GUI build) instead of `opencv-python-headless`** - will pull unneeded system libs into a container unless swapped or apt-installed for.
5. **Unpinned dependency versions** - `requirements.txt` has no version pins, so "works on my machine" today isn't guaranteed reproducible in CI/prod without a lockfile.
6. **`.gitignore` ignores all `*.md` files except an explicit allowlist.** Any new doc this project creates (`docs/DEPLOYMENT_AUDIT.md`, `docs/DEPLOYMENT.md`) must be added to that allowlist or it will silently never be committed.
7. **Upload validation is content-type only** (`ALLOWED_CONTENT_TYPES` in `api/main.py`), no explicit file-size cap - large-upload DoS risk on a public endpoint if deployed without a platform-level body-size limit.
8. **Frontend `dist/` build not yet wired into CI/CD deploy step** - CI builds and lints, but there's no CD job that ships anywhere.

## 10. Production risks (if deployed carelessly)

- Deploying `experiments/m4_1/data`, `experiments/m4_2/data`, `kolam_data/`, `real_photos/` (150MB+ of training/eval imagery) inside the API container image would bloat cold starts and image size for zero runtime benefit - only the two `.pt` files and `experiments/*/model.py` + `ml_lattice_detector.py` modules are needed at request time.
- Running the frozen `engine/ml_contract.py` or `trace_path()` through an automated "cleanup" pass during containerization would violate the project's explicit invariants (multiplicity-exact MultiGraph semantics, canonical CSV loader). None of the phases below touch these files.
- Treating the existing failure taxonomy (`NO_DOT_DETECTION`, `INSUFFICIENT_LATTICE_POINTS`, etc., used in `validate_real_photos.py`) as generic HTTP 500s anywhere in a future async/job-based API would erase information the project explicitly wants preserved (task brief Phase 11).

## 11. Recommended deployment topology (summary - expanded in the follow-up report)

Given: no DB, no object storage, no async job needs today, CPU-only ML, two small checkpoints, synchronous sub-second endpoints, single-developer/student/open-source project stage -

**Recommended now:** Option B - static frontend (Vercel or any static host) + single containerized FastAPI service (Render/Fly.io/Railway free-or-low-cost tier). No database, no queue, no worker split, no Kubernetes. This matches the actual code today; anything heavier would be built ahead of demonstrated need, which the task brief explicitly warns against.

Full comparison of options A-D, cloud platform matrix, and phased implementation plan follow in the chat response, per Phase 16 of the task brief - implementation has not started pending your confirmation of the recommended architecture.
