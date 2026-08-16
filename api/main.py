"""M4.2 Phase G: minimal REST API. No backend server existed anywhere
in this repository before this file (verified in Phase A's audit) --
this is new infrastructure, not an integration into an existing one.

Every endpoint follows the task's explicit rules:
  - detector=classical is the default everywhere a detector is chosen.
  - No silent fallback: if detector=ml is requested and the ML detector
    is unavailable (no checkpoint, load failure, inference error), the
    endpoint returns an explicit error (HTTP 503), never silently
    substitutes classical.
  - Coordinates returned are always ORIGINAL image pixel coordinates
    (api/detectors.py handles the un-deskewing) -- never heatmap-cell
    or model-input-resized coordinates.
  - No NetworkX objects, MotifPlacement objects, or other engine-
    internal Python types are ever returned directly -- see
    api/canonical.py.
  - Uploaded images are written to a temp file for processing and
    deleted immediately after -- never logged, never persisted.

KNOWN ENVIRONMENT REQUIREMENT (discovered in M4.1, re-confirmed here):
this process legitimately needs BOTH torch (for the ML detector /
`/api/v1/model`) and numpy/scipy's MKL-linked linear algebra (for the
classical detector's `engine.image_io._fit_lattice_coords`) in the SAME
process -- an API server can't avoid this the way a single-purpose
script can. Loading both triggers a PyTorch/MKL OpenMP DLL conflict
(`OMP: Error #15`) that hard-crashes the process on first use of either
codepath after the other has loaded. `KMP_DUPLICATE_LIB_OK=TRUE` is set
below, at the top of this entry module, before any torch/numpy import --
the correct, permanent place for a persistent server process (as
opposed to prefixing every one-off script invocation, which is what
M4.1's experimental scripts did). This was independently verified NOT
to silently corrupt numerical output for this workload before being
relied on (M4.1 Phase 5 investigation, PROJECT_STATE.md session 13) --
not applied blindly. See docs/M4_2_API.md for the deployment note.
"""

from __future__ import annotations

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import sys
import tempfile
import time

from dotenv import load_dotenv

# Loads .env (DATABASE_URL, AUTH_SECRET, COOKIE_*, CORS_ORIGINS) if present
# in the repo root -- copy .env.example to .env for local dev. Does
# nothing (no error) if the file doesn't exist, and never overrides a
# variable already set in the real environment (production deployments
# typically set these via the platform, not a checked-in-adjacent file).
load_dotenv()

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from api.security_headers import SecurityHeadersMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.auth.db import init_db  # noqa: E402
from api.rate_limit import (  # noqa: E402
    COMPARE_LIMIT_PER_MINUTE,
    DETECTION_LIMIT_PER_MINUTE,
    GENERATION_LIMIT_PER_MINUTE,
    STREAM_LIMIT_PER_MINUTE,
    enforce_rate_limit,
)
from api.auth.router import router as auth_router  # noqa: E402
from api.canonical import graph_to_json, motif_placements_to_json, reconstruction_to_json, validity_to_json  # noqa: E402
from api.detectors import get_detector  # noqa: E402
from api.generation_service import get_generation_service  # noqa: E402
from api.routes_generations import router as generations_router  # noqa: E402
from api.schemas import (  # noqa: E402
    AnalyzeResponse,
    CompareDetectorsResponse,
    DetectResponse,
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
    ModelInfoResponse,
    ReconstructResponse,
)
from engine import motifs, validity  # noqa: E402


@asynccontextmanager
async def _lifespan(app: FastAPI):  # noqa: ARG001
    """Single lifespan handler replacing the three deprecated @app.on_event('startup')
    decorators. Runs all startup logic sequentially before yielding, exactly as the
    original handlers did (FastAPI calls them in registration order)."""
    # ---- 1. ML runtime + production security validation ----
    if os.environ.get("PULLI_TESTING") == "true":
        print("[pulli-api] Testing environment detected -- bypassing strict startup checkpoint validation.")
    else:
        _cookie_secure = os.environ.get("COOKIE_SECURE", "").lower() in ("1", "true", "yes")
        if _cookie_secure:
            _auth_secret = os.environ.get("AUTH_SECRET")
            if not _auth_secret:
                print("[CRITICAL] Production Security Validation Failed: COOKIE_SECURE is true but AUTH_SECRET is not set.", file=sys.stderr)
                sys.exit(1)
            _cors_origins_check = os.environ.get("CORS_ORIGINS", "").strip()
            if not _cors_origins_check:
                print("[CRITICAL] Production Security Validation Failed: COOKIE_SECURE is true but CORS_ORIGINS is not set.", file=sys.stderr)
                sys.exit(1)
            if _cors_origins_check == "*":
                print("[CRITICAL] Production Security Validation Failed: Wildcard CORS '*' is forbidden when credentials/cookies are used.", file=sys.stderr)
                sys.exit(1)

        from api.generation_service import CHECKPOINT_PATH as M5_CHECKPOINT
        _m4_checkpoint = os.path.join(
            os.path.dirname(__file__), "..", "experiments", "m4_2", "results", "dot_heatmap_net_v2.pt"
        )
        if not os.path.exists(_m4_checkpoint):
            print(f"[CRITICAL] ML Runtime Validation Failed: M4.2 checkpoint missing at {_m4_checkpoint}", file=sys.stderr)
            sys.exit(1)
        if not M5_CHECKPOINT.exists():
            print(f"[CRITICAL] ML Runtime Validation Failed: M5 placement scorer checkpoint missing at {M5_CHECKPOINT}", file=sys.stderr)
            sys.exit(1)
        print("[pulli-api] ML runtime, model checkpoints, and security configurations validated successfully.")

    # ---- 2. Auth tables (always, idempotent) ----
    init_db()

    # ---- 3. Platform DB (M7 generations/models tables + seed, non-fatal) ----
    try:
        from api.db.database import get_session, init_db as init_platform_db
        from api.db.seed import seed_models

        init_platform_db()
        _session = get_session()
        try:
            seed_models(_session)
        finally:
            _session.close()
    except Exception as e:  # noqa: BLE001
        print(f"[pulli-api] platform DB init/seed failed (legacy endpoints unaffected): {type(e).__name__}: {e}", file=sys.stderr)

    yield  # application runs here


app = FastAPI(title="PULLI API", version="0.1.0", lifespan=_lifespan)

# ────────────────────────────────────────────────────────────────────
#  Rate limiting (Phase 14 hardening -- previously the #1 documented
#  gap: "no rate limiting anywhere in the codebase", flagged in
#  PRODUCTION_READINESS.md section 8/12/13). Implemented as a plain
#  function call (`enforce_rate_limit`, see api/rate_limit.py) at the
#  top of each expensive route body, keyed by client IP -- see
#  api/rate_limit.py's module docstring for why the more conventional
#  `slowapi` decorator was tried and rejected (it breaks FastAPI's
#  request-model resolution in this file specifically, due to
#  `from __future__ import annotations` above interacting badly with
#  `functools.wraps`-based decorators). 429s raised by
#  `enforce_rate_limit` are plain HTTPExceptions with the same
#  {"code": ..., "message": ...} detail shape as every other error path
#  here, so they flow through the SAME http_exception_handler below --
#  no separate exception handler needed.
# ────────────────────────────────────────────────────────────────────

# The frontend (Vite dev server) runs on a different origin than this API
# (5173/5174 vs 8000) -- without this, every browser request is blocked by
# CORS before it even reaches the endpoints below (confirmed: this is not
# hypothetical, it was reproduced in a real browser E2E run against the
# real frontend). allow_credentials=True is required for the auth session
# cookie (api/auth/) to be sent/received cross-origin at all -- per the
# CORS spec this means allow_origins can never be "*", so CORS_ORIGINS
# (comma-separated explicit origins) is the production path; unset, it
# falls back to a permissive localhost-only regex for zero-config local
# dev (covers whatever port Vite picks, not just the common defaults).
_cors_origins_env = os.environ.get("CORS_ORIGINS", "").strip()
_cors_kwargs = (
    {"allow_origins": [o.strip() for o in _cors_origins_env.split(",") if o.strip()]}
    if _cors_origins_env
    else {"allow_origin_regex": r"http://(localhost|127\.0\.0\.1):\d+"}
)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    # DELETE added this session for DELETE /api/v1/generations/{id} (artifact
    # deletion) -- without it, a real cross-origin browser (Vercel frontend
    # calling this Render backend) fails CORS preflight on that endpoint.
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
    **_cors_kwargs,
)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth_router)
app.include_router(generations_router)


# Startup logic is consolidated in the _lifespan context manager above.

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}

# Application-level upload cap. This is a minimal safety net, not a
# substitute for a platform/proxy-level body-size limit in production
# (see docs/DEPLOYMENT.md section H) -- a single kolam photo is a few
# MB at most, so 20MB comfortably covers real uploads while bounding
# worst-case memory use per request.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    """Structured error detail -- unpacked by http_exception_handler into
    {"success": false, "error": message, "code": code}. `code` is a
    stable machine-readable identifier for the frontend to switch on
    (see frontend/frontend/src/lib/api/client.js); `error` stays a
    human-readable string for backward compatibility with the existing
    error-message display path."""
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _validate_detector_param(detector: str) -> str:
    """Validates AND normalizes -- callers use the returned value (not
    the raw `detector` argument) for both `_run_detector` and any
    detector-derived response field, so 'ML_GATED'/'gated_ml'/etc. all
    resolve to the same canonical name api/detectors.py's get_detector
    itself normalizes to. Structured error (see _api_error) rather than
    a plain HTTPException so the frontend gets a stable `code` to switch
    on, consistent with every other error path in this module."""
    if not isinstance(detector, str):
        raise _api_error(422, "INVALID_DETECTOR", f"detector must be a string, got {detector!r}")
    normalized = detector.strip().lower().replace("_", "-")
    if normalized in ("ml-gated", "gated-ml"):
        return "ml-gated"
    if normalized in ("classical", "ml"):
        return normalized
    raise _api_error(422, "INVALID_DETECTOR", f"detector must be 'classical', 'ml', or 'ml-gated', got {detector!r}")


def _save_upload_to_temp(image: UploadFile) -> str:
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise _api_error(415, "UNSUPPORTED_MEDIA_TYPE", f"unsupported content type: {image.content_type}")
    suffix = os.path.splitext(image.filename or "")[1] or ".jpg"
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            content = image.file.read(MAX_UPLOAD_BYTES + 1)
            if not content:
                raise _api_error(400, "EMPTY_UPLOAD", "empty image upload")
            if len(content) > MAX_UPLOAD_BYTES:
                raise _api_error(413, "UPLOAD_TOO_LARGE", f"image exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB upload limit")
            f.write(content)
    except Exception:
        os.unlink(path)
        raise
    return path


def _run_detector(detector_name: str, image_path: str):
    detector = get_detector(detector_name)
    try:
        return detector.detect(image_path)
    except FileNotFoundError as e:
        raise _api_error(400, "INVALID_IMAGE", f"invalid image: {e}") from e
    except RuntimeError as e:
        # ML detector unavailable (missing checkpoint, load failure) --
        # explicit 503, no silent fallback to classical.
        raise _api_error(503, "ML_MODEL_UNAVAILABLE", str(e)) from e
    except Exception as e:  # noqa: BLE001 -- surfaced explicitly, not swallowed
        # Server-side diagnostic only -- the client response never
        # includes a traceback, just the exception type/message.
        print(f"[pulli-api] detector={detector_name!r} failed: {type(e).__name__}: {e}", file=sys.stderr)
        raise _api_error(500, "DETECTOR_FAILED", f"detector failed: {type(e).__name__}: {e}") from e


@app.get("/api/v1/health", response_model=HealthResponse)
def health():
    ml_available = os.path.exists(
        os.path.join(os.path.dirname(__file__), "..", "experiments", "m4_2", "results", "dot_heatmap_net_v2.pt")
    )

    # Phase 9 hardening: each of these three checks is a REAL, live
    # probe run on every /health call -- none is a cached/hardcoded
    # "true". Each is wrapped independently so one subsystem's failure
    # (e.g. DB down) doesn't prevent /health itself from responding, and
    # so the response can honestly report "process up, DB down" instead
    # of a single opaque failure.
    try:
        gen_service = get_generation_service()
        generation_service_available = bool(gen_service.available)
        generation_service_error = None if gen_service.available else gen_service.load_error
    except Exception as e:  # noqa: BLE001 -- health check must never itself crash
        generation_service_available = False
        generation_service_error = f"{type(e).__name__}: {e}"

    try:
        from sqlalchemy import text

        from api.db.database import get_session

        session = get_session()
        try:
            session.execute(text("SELECT 1"))
            database_connected = True
        finally:
            session.close()
    except Exception:  # noqa: BLE001 -- health check must never itself crash
        database_connected = False

    # Temporary diagnostic: which SQLAlchemy dialect the live app is
    # actually running against (e.g. distinguishing a Render deployment
    # still on SQLite from one correctly pointed at PostgreSQL), without
    # a Render shell/dashboard. Read directly off the real engine object
    # already in use elsewhere in this process -- never a second
    # connection, never DATABASE_URL string-parsed/inferred, never
    # logged or included in any response. `dialect.name` on SQLAlchemy's
    # own Dialect class is exactly "postgresql" / "sqlite" / etc., not a
    # value this code constructs itself.
    try:
        from api.db.database import engine as _platform_engine

        database_engine = _platform_engine.dialect.name
    except Exception:  # noqa: BLE001 -- health check must never itself crash
        database_engine = "unknown"

    try:
        from api.services.artifact_store import get_artifact_store

        store = get_artifact_store()
        if hasattr(store, "root"):
            artifact_storage_available = store.root.exists() and os.access(store.root, os.W_OK)
        else:
            artifact_storage_available = bool(os.environ.get("R2_BUCKET"))
    except Exception:  # noqa: BLE001 -- health check must never itself crash
        artifact_storage_available = False

    return {
        "status": "ok",
        "classical_detector_available": True,
        "ml_detector_available": ml_available,
        "gated_detector_available": ml_available,
        "generation_service_available": generation_service_available,
        "generation_service_error": generation_service_error,
        "database_connected": database_connected,
        "database_engine": database_engine,
        "artifact_storage_available": artifact_storage_available,
    }


@app.get("/api/v1/health/live")
def health_live():
    """Liveness probe: answers if the FastAPI process is running."""
    return {"status": "ok"}


@app.get("/api/v1/health/ready")
def health_ready():
    """Readiness probe: checks database, ML systems, and object storage connectivity."""
    ml_available = os.path.exists(
        os.path.join(os.path.dirname(__file__), "..", "experiments", "m4_2", "results", "dot_heatmap_net_v2.pt")
    )
    
    try:
        gen_service = get_generation_service()
        generation_service_available = bool(gen_service.available)
    except Exception:
        generation_service_available = False

    try:
        from sqlalchemy import text
        from api.db.database import get_session
        session = get_session()
        try:
            session.execute(text("SELECT 1"))
            database_connected = True
        finally:
            session.close()
    except Exception:
        database_connected = False

    try:
        from api.services.artifact_store import get_artifact_store
        store = get_artifact_store()
        if hasattr(store, "root"):
            artifact_storage_available = store.root.exists() and os.access(store.root, os.W_OK)
        else:
            artifact_storage_available = bool(os.environ.get("R2_BUCKET"))
    except Exception:
        artifact_storage_available = False

    is_ready = ml_available and generation_service_available and database_connected and artifact_storage_available

    status_code = 200 if is_ready else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_ready else "not_ready",
            "database_connected": database_connected,
            "generation_service_available": generation_service_available,
            "ml_detector_available": ml_available,
            "artifact_storage_available": artifact_storage_available,
        }
    )


def _model_attribution(result) -> dict:
    """Which detector/model produced `result` -- attached to /detect,
    /analyze, /reconstruct responses (Phase 4/9's "every downstream
    result must identify which detector produced it" requirement).
    All detectors are CPU-only; ML's name is the actual architecture
    class, not a marketing label. `result.detector` is api/detectors.py's
    own normalized name ("classical" | "ml" | "ml-gated") -- this
    function must stay in sync with that set, not guess at it."""
    if result.detector == "ml":
        return {"name": "DotHeatmapNetV2", "version": result.model_version, "device": "cpu"}
    if result.detector == "ml-gated":
        return {"name": "DotHeatmapNetV2 (lattice-consistency gated)", "version": result.model_version, "device": "cpu"}
    return {"name": "Classical (deterministic, engine.image_io.detect_lattice)", "version": None, "device": "cpu"}


@app.get("/api/v1/model", response_model=ModelInfoResponse)
def model_info():
    checkpoint_path = os.path.join(
        os.path.dirname(__file__), "..", "experiments", "m4_2", "results", "dot_heatmap_net_v2.pt"
    )
    exists = os.path.exists(checkpoint_path)
    from experiments.m4_2.model import MODEL_INPUT_SIZE, HEATMAP_SIZE
    from experiments.m4_2.ml_lattice_detector import MODEL_VERSION as UNGATED_VERSION
    from experiments.m4_2.gated_ml_lattice_detector import MODEL_VERSION as GATED_VERSION

    # Reflects the ML detector singleton's ACTUAL lazy-load state (see
    # api/detectors.py's MLDetector) -- this endpoint does not force a
    # load just to answer a status query. `ml_loaded=False` on a fresh
    # process with a valid checkpoint is honest: the model hasn't run
    # yet, not "unavailable". The gated detector wraps the SAME
    # checkpoint (docs/M4_1_ML_COMPLETION_REPORT.md's "Checkpoint
    # policy") so parameter count is identical regardless of which
    # adapter loaded it first.
    ml_detector = get_detector("ml")
    is_loaded = ml_detector._detector is not None
    parameter_count = None
    if is_loaded:
        parameter_count = sum(p.numel() for p in ml_detector._detector.model.parameters())

    return {
        "ml_model_version": UNGATED_VERSION if exists else None,
        "gated_model_version": GATED_VERSION if exists else None,
        "ml_checkpoint_exists": exists,
        "ml_model_input_size": MODEL_INPUT_SIZE if exists else None,
        "ml_heatmap_size": HEATMAP_SIZE if exists else None,
        "classical_detector": "engine.image_io.detect_lattice (deterministic)",
        "ml_model_name": "DotHeatmapNetV2" if exists else None,
        "ml_parameter_count": parameter_count,
        "ml_device": "cpu" if exists else None,
        "ml_loaded": is_loaded,
        "ml_inference_mode": "torch.no_grad" if is_loaded else None,
        "classical_detector_status": "available",
        "ml_detector_status": "available" if exists else "unavailable",
    }


@app.post("/api/v1/detect", response_model=DetectResponse)
def detect(request: Request, image: UploadFile = File(...), detector: str = Form("classical")):
    enforce_rate_limit(request, "detect", DETECTION_LIMIT_PER_MINUTE)
    detector_norm = _validate_detector_param(detector)

    path = _save_upload_to_temp(image)
    try:
        result = _run_detector(detector_norm, path)
    finally:
        os.unlink(path)  # never persist uploaded images

    return {
        "success": True,
        "detector": result.detector,
        "model_version": result.model_version,
        "image": {"width": result.width, "height": result.height},
        "detections": [{"x": x, "y": y} for x, y in result.dots],
        "count": len(result.dots),
        "processing_ms": round(result.processing_ms, 2),
        "model": _model_attribution(result),
    }


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
def analyze(request: Request, image: UploadFile = File(...), detector: str = Form("classical")):
    enforce_rate_limit(request, "analyze", DETECTION_LIMIT_PER_MINUTE)
    detector_norm = _validate_detector_param(detector)

    path = _save_upload_to_temp(image)
    try:
        result = _run_detector(detector_norm, path)
    finally:
        os.unlink(path)

    # G is result.graph -- built by THIS detector's own Lattice via
    # engine.image_io.trace_path (see api/detectors.py). Selecting
    # detector=ml here means every downstream stage (validity, motifs)
    # operates on the ML-derived graph, not a separately-run classical
    # pass -- there is only ever one graph per request, owned by
    # whichever detector was selected.
    t_analysis_start = time.monotonic()
    G = result.graph
    dots = set(G.nodes())
    validity_result = validity.check_validity(G) if G.number_of_nodes() else {
        "is_eulerian_circuit": False, "has_eulerian_path": False,
        "connected_components": 0, "largest_component_covers_all_nodes": False,
    }

    placements = []
    if len(dots) >= 1:
        interior = motifs.interior_points(dots, radius=1)
        placements, _residual, _fully_covered = motifs.induce_motif_set_adaptive(
            G, interior, dots, max_radius=2, max_motifs_per_radius=50
        )
    analysis_ms = (time.monotonic() - t_analysis_start) * 1000

    return {
        "success": True,
        "detector": result.detector,
        "model_version": result.model_version,
        "dots": [{"x": x, "y": y} for x, y in result.dots],
        "dot_count": len(result.dots),
        "processing_ms": round(result.processing_ms, 2),
        "graph": graph_to_json(G),
        "motifs": motif_placements_to_json(placements),
        "validity": validity_to_json(validity_result),
        "model": _model_attribution(result),
        "timing_ms": {
            "detection": round(result.processing_ms, 2),
            "analysis": round(analysis_ms, 2),
            "total": round(result.processing_ms + analysis_ms, 2),
        },
    }


@app.post("/api/v1/reconstruct", response_model=ReconstructResponse)
def reconstruct(request: Request, image: UploadFile = File(...), detector: str = Form("classical")):
    enforce_rate_limit(request, "reconstruct", DETECTION_LIMIT_PER_MINUTE)
    detector_norm = _validate_detector_param(detector)

    path = _save_upload_to_temp(image)
    try:
        result = _run_detector(detector_norm, path)
    finally:
        os.unlink(path)

    # Same graph-ownership rule as /analyze: G is THIS detector's own
    # result.graph -- reconstruction always operates on whichever
    # detector was selected, never a separately-run classical pass.
    G = result.graph
    dots = set(G.nodes())
    if len(dots) < 1:
        return {
            "success": True, "detector": result.detector, "model_version": result.model_version,
            "processing_ms": round(result.processing_ms, 2), "graph": graph_to_json(G),
            "reconstruction": {"note": "no dots detected -- nothing to reconstruct"},
            "model": _model_attribution(result),
            "timing_ms": {"detection": round(result.processing_ms, 2), "reconstruction": 0.0, "total": round(result.processing_ms, 2)},
        }

    from api.reconstruct_adapter import build_kolam_pattern_from_graph
    from engine import reconstruction as recon_module

    t_recon_start = time.monotonic()
    source_pattern = build_kolam_pattern_from_graph(G, dots)
    interior = motifs.interior_points(dots, radius=1)
    placements, _residual, _fully_covered = motifs.induce_motif_set_adaptive(
        G, interior, dots, max_radius=2, max_motifs_per_radius=50
    )
    recon_result = recon_module.reconstruct_kolam(source_pattern, placements)
    reconstruction_ms = (time.monotonic() - t_recon_start) * 1000

    return {
        "success": True,
        "detector": result.detector,
        "model_version": result.model_version,
        "processing_ms": round(result.processing_ms, 2),
        "graph": graph_to_json(G),
        "reconstruction": reconstruction_to_json(recon_result),
        "model": _model_attribution(result),
        "timing_ms": {
            "detection": round(result.processing_ms, 2),
            "reconstruction": round(reconstruction_ms, 2),
            "total": round(result.processing_ms + reconstruction_ms, 2),
        },
    }


def _error_message(detail) -> str:
    """detail is always {"code": ..., "message": ...} from _api_error --
    this extracts the human-readable string for contexts (like
    /compare-detectors' per-side `error` field) that are typed as a
    plain string, not the full structured error envelope."""
    if isinstance(detail, dict):
        return detail.get("message", str(detail))
    return str(detail)


@app.post("/api/v1/compare-detectors", response_model=CompareDetectorsResponse)
def compare_detectors(request: Request, image: UploadFile = File(...)):
    enforce_rate_limit(request, "compare-detectors", COMPARE_LIMIT_PER_MINUTE)
    path = _save_upload_to_temp(image)
    try:
        classical_result = None
        ml_result = None
        classical_error = None
        ml_error = None
        try:
            classical_result = _run_detector("classical", path)
        except HTTPException as e:
            classical_error = _error_message(e.detail)
        try:
            ml_result = _run_detector("ml", path)
        except HTTPException as e:
            ml_error = _error_message(e.detail)
    finally:
        os.unlink(path)

    def _side(result, error, name):
        if result is None:
            return {"detector": name, "model_version": None, "detections": [], "count": 0,
                    "processing_ms": 0.0, "error": error}
        return {"detector": name, "model_version": result.model_version,
                "detections": [{"x": x, "y": y} for x, y in result.dots],
                "count": len(result.dots), "processing_ms": round(result.processing_ms, 2), "error": None}

    agreement = {"note": "not computed", "classical_count": 0, "ml_count": 0}
    if classical_result is not None and ml_result is not None:
        from scipy.spatial import cKDTree
        import numpy as np
        c_pts = np.array(classical_result.dots) if classical_result.dots else np.empty((0, 2))
        m_pts = np.array(ml_result.dots) if ml_result.dots else np.empty((0, 2))
        tol = 6.0
        n_agree = 0
        if len(c_pts) and len(m_pts):
            tree = cKDTree(m_pts)
            d, _ = tree.query(c_pts)
            n_agree = int((d < tol).sum())
        agreement = {
            "match_tolerance_px": tol, "classical_count": len(c_pts), "ml_count": len(m_pts),
            "agreeing_dots": n_agree,
            "classical_only": len(c_pts) - n_agree,
            "ml_only": len(m_pts) - n_agree,
        }

    return {
        "success": True,
        "image": {"width": (classical_result or ml_result).width if (classical_result or ml_result) else 0,
                  "height": (classical_result or ml_result).height if (classical_result or ml_result) else 0},
        "classical": _side(classical_result, classical_error, "classical"),
        "ml": _side(ml_result, ml_error, "ml"),
        "agreement": agreement,
    }


# ────────────────────────────────────────────────────────────────────
#  SSE Streaming Pipeline  (/api/v1/analyze-stream/*)
#
#  Two endpoints that expose the SAME engine stages already used by
#  /api/v1/analyze, but emit Server-Sent Events between each stage so
#  the frontend stepper can advance in real time.
#
#  No engine/ML code is duplicated here -- every stage calls the same
#  helper / engine function that /analyze uses.  The only addition is
#  the asyncio.Queue-based event bus between the background thread and
#  the SSE generator.
# ────────────────────────────────────────────────────────────────────

import asyncio
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi.responses import StreamingResponse

# In-process job store: job_id → {"path": str, "detector": str, "queue": asyncio.Queue}
# Entries are deleted once the SSE stream is exhausted or on error.
# This is deliberately simple (no Redis, no DB) -- adequate for a
# single-process dev server with low concurrency.
_STREAM_JOBS: dict[str, dict] = {}
_PIPELINE_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pulli-pipeline")


def _sse(event: str, data: dict) -> str:
    """Format a single SSE message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _run_pipeline_in_thread(job_id: str, image_path: str, detector: str, loop: asyncio.AbstractEventLoop) -> None:
    """
    Runs the full Kolam analysis pipeline synchronously (in a thread-pool
    worker) and posts SSE events to the job's asyncio.Queue so the async
    SSE generator can yield them to the browser.

    Stages mirror /api/v1/analyze exactly -- no logic is duplicated, only
    the event-emission wrapper is new.
    """
    job = _STREAM_JOBS.get(job_id)
    if job is None:
        return

    queue: asyncio.Queue = job["queue"]

    def emit(event: str, data: dict) -> None:
        asyncio.run_coroutine_threadsafe(queue.put(_sse(event, data)), loop)

    def stage_started(stage_id: str, idx: int, message: str) -> None:
        emit("stage_started", {
            "job_id": job_id, "stage": stage_id,
            "stage_index": idx, "status": "running", "message": message,
        })

    def stage_completed(stage_id: str, idx: int, message: str, result: dict | None = None) -> None:
        payload: dict = {
            "job_id": job_id, "stage": stage_id,
            "stage_index": idx, "status": "completed", "message": message,
        }
        if result is not None:
            payload["result"] = result
        emit("stage_completed", payload)

    def stage_failed(stage_id: str, idx: int, message: str) -> None:
        # Ensure message is always a plain string even if an HTTPException
        # detail dict is passed through inadvertently.
        if not isinstance(message, str):
            message = str(message)
        emit("stage_failed", {
            "job_id": job_id, "stage": stage_id,
            "stage_index": idx, "status": "failed", "message": message,
        })
        emit("pipeline_failed", {
            "job_id": job_id, "status": "failed",
            "stage": stage_id, "stage_index": idx, "message": message,
        })
        asyncio.run_coroutine_threadsafe(queue.put(None), loop)  # sentinel

    try:
        # FIX: Give the SSE client 150 ms to connect before the first event
        # fires.  The thread-pool worker starts immediately after POST /start
        # returns; on fast machines the first stage_started can race the
        # browser opening its EventSource.  The asyncio.Queue already buffers
        # every event so nothing is ever lost, but this makes the race window
        # essentially zero and avoids confusing "already completed" initial states.
        import time as _time
        _time.sleep(0.15)

        # ── STAGE 0: upload_image (already done, just signal it) ──────
        stage_started("upload_image", 0, "Image received.")
        stage_completed("upload_image", 0, "Image uploaded successfully.")

        # ── STAGE 1: detect_dots ──────────────────────────────────────
        stage_started("detect_dots", 1, "Detecting pulli dots…")
        try:
            det_result = _run_detector(detector, image_path)
        except HTTPException as exc:
            # FIX: exc.detail is a dict {code, message} from _api_error --
            # _error_message() extracts the human-readable string so the
            # frontend receives a proper string, not a serialised dict.
            stage_failed("detect_dots", 1, _error_message(exc.detail))
            return
        stage_completed("detect_dots", 1, f"Detected {len(det_result.dots)} dots.", {
            "dot_count": len(det_result.dots),
            "detector": det_result.detector,
            "model_version": det_result.model_version,
            "processing_ms": round(det_result.processing_ms, 2),
        })

        # ── STAGE 2: trace_stroke ─────────────────────────────────────
        stage_started("trace_stroke", 2, "Tracing stroke from dot arrangement…")
        G = det_result.graph
        edge_count = G.number_of_edges()
        stage_completed("trace_stroke", 2, f"Stroke traced  -  {edge_count} edges.", {
            "edge_count": edge_count,
        })

        # ── STAGE 3: build_graph ──────────────────────────────────────
        stage_started("build_graph", 3, "Building mathematical graph…")
        graph_data = graph_to_json(G)
        stage_completed("build_graph", 3,
            f"Graph built: {graph_data['nodes']} nodes, {graph_data['edges']} edges.", graph_data)

        # ── STAGE 4: detect_symmetry ──────────────────────────────────
        stage_started("detect_symmetry", 4, "Analysing structural symmetry…")
        dots = set(G.nodes())
        if G.number_of_nodes():
            val_result = validity.check_validity(G)
        else:
            val_result = {
                "is_eulerian_circuit": False, "has_eulerian_path": False,
                "connected_components": 0, "largest_component_covers_all_nodes": False,
            }
        sym_data = {
            "connected_components": val_result.get("connected_components", 0),
            "largest_component_covers_all_nodes": val_result.get("largest_component_covers_all_nodes", False),
        }
        stage_completed("detect_symmetry", 4,
            f"Symmetry analysis done  -  {sym_data['connected_components']} component(s).", sym_data)

        # ── STAGE 5: find_motifs ──────────────────────────────────────
        stage_started("find_motifs", 5, "Identifying motif patterns…")
        placements: list = []
        if len(dots) >= 1:
            interior = motifs.interior_points(dots, radius=1)
            placements, _residual, _fully_covered = motifs.induce_motif_set_adaptive(
                G, interior, dots, max_radius=2, max_motifs_per_radius=50
            )
        stage_completed("find_motifs", 5, f"Found {len(placements)} motif placement(s).", {
            "motif_count": len(placements),
        })

        # ── STAGE 6: validate_stroke ──────────────────────────────────
        stage_started("validate_stroke", 6, "Validating Eulerian stroke property…")
        validity_data = validity_to_json(val_result)
        is_valid = validity_data["is_eulerian_circuit"]
        stage_completed("validate_stroke", 6,
            f"Stroke {'is a valid Eulerian circuit' if is_valid else 'is NOT a valid Eulerian circuit'}.",
            validity_data)

        # ── STAGE 7: extract_rules ────────────────────────────────────
        stage_started("extract_rules", 7, "Extracting design rules…")
        rules_data = {
            "dot_count": len(det_result.dots),
            "motif_count": len(placements),
            "is_eulerian_circuit": validity_data["is_eulerian_circuit"],
            "has_eulerian_path": validity_data["has_eulerian_path"],
            "connected_components": validity_data["connected_components"],
            "graph_nodes": graph_data["nodes"],
            "graph_edges": graph_data["edges"],
        }
        stage_completed("extract_rules", 7, "Design rules extracted.", rules_data)

        # ── PIPELINE COMPLETE ─────────────────────────────────────────
        emit("pipeline_completed", {
            "job_id": job_id, "status": "completed",
            "message": "Kolam analysis completed successfully.",
        })

    except Exception as exc:  # noqa: BLE001
        emit("pipeline_failed", {
            "job_id": job_id, "status": "failed",
            "message": f"Unexpected pipeline error: {type(exc).__name__}: {exc}",
        })
    finally:
        # Sentinel: tells the SSE generator to stop.
        asyncio.run_coroutine_threadsafe(queue.put(None), loop)
        # Clean up temp file if not already removed.
        try:
            if os.path.exists(image_path):
                os.unlink(image_path)
        except OSError:
            pass
        # Remove job from store.
        _STREAM_JOBS.pop(job_id, None)


@app.post("/api/v1/analyze-stream/start")
async def analyze_stream_start(
    request: Request,
    image: UploadFile = File(...),
    detector: str = Form("classical"),
):
    """
    Accept an image upload and immediately return a job_id.
    The actual ML pipeline runs asynchronously -- the client should
    connect to /api/v1/analyze-stream/{job_id}/events to receive
    stage-by-stage progress via SSE.
    """
    enforce_rate_limit(request, "analyze-stream", STREAM_LIMIT_PER_MINUTE)
    if detector not in ("classical", "ml"):
        raise HTTPException(status_code=400, detail=f"detector must be 'classical' or 'ml', got {detector!r}")

    path = _save_upload_to_temp(image)
    job_id = str(uuid.uuid4())

    # FIX: get_event_loop() is deprecated and raises RuntimeError in
    # Python 3.12+ inside a running event loop.  get_running_loop() is
    # the correct API inside an async function -- it always returns the
    # currently-running loop without creating a new one.
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    _STREAM_JOBS[job_id] = {
        "path": path,
        "detector": detector,
        "queue": queue,
        "status": "started",       # snapshot for /status reconnect endpoint
        "current_stage": None,
    }

    # Fire-and-forget: runs the full pipeline in a thread-pool worker.
    loop.run_in_executor(
        _PIPELINE_EXECUTOR,
        _run_pipeline_in_thread,
        job_id, path, detector, loop,
    )

    return {"job_id": job_id, "status": "started", "detector": detector}


@app.get("/api/v1/analyze-stream/{job_id}/events")
async def analyze_stream_events(job_id: str):
    """
    Server-Sent Events endpoint.  The client connects here after
    receiving a job_id from /start.  Events are emitted in order as
    each pipeline stage begins and completes.  The stream closes when
    the pipeline finishes or fails.
    """
    job = _STREAM_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No active analysis job with id {job_id!r}.")

    queue: asyncio.Queue = job["queue"]

    async def event_generator():
        # Keep-alive comment so the browser doesn't close a "stalled" connection
        # before the first real event arrives (ML pipeline can take a few seconds
        # to start on a cold process).
        yield ": keep-alive\n\n"
        while True:
            item = await queue.get()
            if item is None:  # sentinel -- pipeline done
                break
            yield item

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # nginx: disable proxy buffering
        },
    )


@app.get("/api/v1/analyze-stream/{job_id}/status")
async def analyze_stream_status(job_id: str):
    """
    Lightweight status snapshot for the given job_id.

    Allows the frontend to reconnect after a page refresh: if the job is
    still in _STREAM_JOBS the client re-opens the /events SSE stream and
    the queued events replay naturally.  If the job has been cleaned up
    (pipeline finished) it returns 404 so the client knows not to reconnect.

    This endpoint does NOT replay past events -- the asyncio.Queue already
    holds every buffered event for an in-progress job.  Its only purpose
    is to tell the client whether a given job_id is still alive.
    """
    job = _STREAM_JOBS.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active analysis job with id {job_id!r}. "
                   "The pipeline may have already completed or the server restarted.",
        )
    return {
        "job_id": job_id,
        "status": job.get("status", "running"),
        "detector": job.get("detector"),
        "current_stage": job.get("current_stage"),
        "alive": True,
    }


MAX_GENERATE_COUNT = 5  # bounds worst-case request latency (each candidate runs up to N_RESTARTS search passes)


@app.post("/api/v1/generate", response_model=GenerateResponse)
def generate(request: Request, body: GenerateRequest):
    """M5: learned-scorer-guided structural generation (engine.learned_generation),
    NOT the M3.7/M4.2 greedy pipeline -- see docs/M4_2_GENERATION.md for
    why that pipeline was replaced (0/120 to 1/120 measured valid).
    Candidates are built from held-out (test-split) source patterns'
    motif libraries and dot layouts, exactly as benchmarked in
    experiments/m5_generation/run_benchmark.py -- this endpoint runs the
    SAME code path, not a separate reimplementation.

    No fabricated statistics: every field in the response comes directly
    from engine.validity/engine.learned_generation's own returned
    structures, same discipline as every other endpoint in this module.
    """
    enforce_rate_limit(request, "generate", GENERATION_LIMIT_PER_MINUTE)
    service = get_generation_service()
    if not service.available:
        raise _api_error(503, "GENERATION_MODEL_UNAVAILABLE", service.load_error or "generation model unavailable")

    count = body.count if body.count is not None else 1
    if not isinstance(count, int) or count < 1:
        raise _api_error(422, "INVALID_REQUEST", f"count must be a positive integer, got {body.count!r}")
    if count > MAX_GENERATE_COUNT:
        raise _api_error(422, "INVALID_REQUEST", f"count must be <= {MAX_GENERATE_COUNT}, got {count}")

    base_seed = body.seed if body.seed is not None else int.from_bytes(os.urandom(4), "big")

    from engine.learned_generation import generate_novel_kolam_learned
    from engine.render import render_generated_kolam_svg
    from engine.symmetry import analyze_symmetry

    t_start = time.monotonic()
    candidates_json = []
    layout_name = None
    n_dots_first = 0
    for i in range(count):
        seed = base_seed + i
        layout_name, dots = service.layout_for_seed(seed)
        n_dots_first = len(dots)
        t0 = time.monotonic()
        run_result = generate_novel_kolam_learned(
            service.motif_library, dots, scorer=service.scorer, seed=seed,
        )
        latency_ms = (time.monotonic() - t0) * 1000
        candidate = run_result.candidate
        diag = candidate.diagnosis

        try:
            _motif, symmetry_coverage, _tp = analyze_symmetry(candidate.graph, dots=set(candidate.dot_points), radius=1)
        except Exception:
            symmetry_coverage = None

        mult_violations = sum(1 for v in candidate.edge_multiplicity.values() if v > 2)

        candidates_json.append(
            {
                "seed": seed,
                "is_valid": candidate.is_valid,
                "n_dots": candidate.n_dots,
                "n_distinct_edges": candidate.n_distinct_edges,
                "n_edge_instances": candidate.n_edge_instances,
                "connected_components": diag["connected_components"],
                "n_odd_degree_nodes": diag["n_odd_degree_nodes"],
                "n_nodes_outside_largest_component": diag["n_nodes_outside_largest_component"],
                "multiplicity_violations": mult_violations,
                "symmetry_coverage": symmetry_coverage,
                "novelty_note": (
                    "structurally distinct from the source patterns whose motifs seeded generation "
                    "(no ground-truth comparison performed per-request; see /docs or the M5 benchmark "
                    "report for aggregate novelty measurement)"
                ),
                "n_restarts_used": len(run_result.restarts),
                "repair_edges_applied": len(run_result.repair_applied),
                "generation_latency_ms": round(latency_ms, 2),
                "render_svg": render_generated_kolam_svg(candidate),
                "dot_trace_length": len(candidate.dot_trace) if candidate.dot_trace else None,
            }
        )

    total_latency_ms = (time.monotonic() - t_start) * 1000
    lattice_width, lattice_height = service.reference_lattice_dims()
    return {
        "success": True,
        # See GenerateResponse.generator's docstring in api/schemas.py --
        # this endpoint only ever calls engine.learned_generation (M5), so
        # this is a constant, not a computed/inferred value.
        "generator": "m5",
        "model": {
            "name": "PlacementScorer (learned, imitation-trained MLP) + multi-restart guided search",
            "version": service.scorer.metadata.get("seed"),
            "n_parameters": service.scorer.metadata.get("n_parameters"),
            "checkpoint": "experiments/m5_generation/checkpoints/placement_scorer.pt",
        },
        "constraints": {
            "lattice_width": lattice_width,
            "lattice_height": lattice_height,
            "n_dots": n_dots_first,
            "motif_source_collection": service.library_sources[0][0] if service.library_sources else "",
            "motif_library_size": len(service.motif_library) if service.motif_library else 0,
        },
        "candidates": candidates_json,
        "total_latency_ms": round(total_latency_ms, 2),
    }


@app.exception_handler(HTTPException)
def http_exception_handler(request, exc):
    # exc.detail is {"code": ..., "message": ...} for every error raised
    # via _api_error (all of this module's own error paths); fall back
    # to treating it as a plain string for anything raised by FastAPI
    # itself (e.g. request validation errors) so no caller ever sees a
    # raw traceback either way.
    if isinstance(exc.detail, dict) and "message" in exc.detail:
        content = {"success": False, "error": exc.detail["message"], "code": exc.detail.get("code", "ERROR")}
    else:
        content = {"success": False, "error": str(exc.detail), "code": "ERROR"}
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request, exc):
    # RequestValidationError is NOT an HTTPException (it's raised by
    # FastAPI's own request-parsing layer, e.g. a missing required
    # multipart field or a malformed JSON body, before any endpoint
    # function runs) -- so it never reaches http_exception_handler above
    # despite that handler's docstring claim. Without this, callers saw
    # FastAPI's default {"detail": [...]} shape instead of this module's
    # {"success": false, "error", "code"} envelope. exc.errors()[0] is
    # used (not the full list) to keep the message short and readable,
    # matching every other error path in this module.
    first = exc.errors()[0] if exc.errors() else {}
    loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    msg = first.get("msg", "invalid request")
    message = f"{loc}: {msg}" if loc else msg
    return JSONResponse(status_code=422, content={"success": False, "error": message, "code": "VALIDATION_ERROR"})
