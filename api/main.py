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

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.canonical import graph_to_json, motif_placements_to_json, reconstruction_to_json, validity_to_json  # noqa: E402
from api.detectors import get_detector  # noqa: E402
from api.schemas import (  # noqa: E402
    AnalyzeResponse,
    CompareDetectorsResponse,
    DetectResponse,
    HealthResponse,
    ModelInfoResponse,
    ReconstructResponse,
)
from engine import motifs, validity  # noqa: E402

app = FastAPI(title="PULLI API", version="0.1.0")

# CORS_ORIGINS: comma-separated list of allowed frontend origins, e.g.
# "http://localhost:5173,https://pulli.example.com". Deliberately NOT
# defaulted to "*" -- an explicit origin list is required in any
# deployment where the API is reachable from a browser. For local
# development where the variable is unset, the common Vite dev-server
# origins are allowed so `npm run dev` works without extra setup;
# production deployments must set CORS_ORIGINS explicitly.
_DEV_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
_cors_origins_env = os.environ.get("CORS_ORIGINS", "").strip()
CORS_ORIGINS = [origin.strip() for origin in (_cors_origins_env or _DEV_DEFAULT_ORIGINS).split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

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
    return {
        "status": "ok",
        "classical_detector_available": True,
        "ml_detector_available": ml_available,
        "gated_detector_available": ml_available,
    }


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
def detect(image: UploadFile = File(...), detector: str = Form("classical")):
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
def analyze(image: UploadFile = File(...), detector: str = Form("classical")):
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
def reconstruct(image: UploadFile = File(...), detector: str = Form("classical")):
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
def compare_detectors(image: UploadFile = File(...)):
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
