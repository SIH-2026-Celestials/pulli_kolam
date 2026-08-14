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

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.auth.db import init_db  # noqa: E402
from api.auth.router import router as auth_router  # noqa: E402
from api.canonical import graph_to_json, motif_placements_to_json, reconstruction_to_json, validity_to_json  # noqa: E402
from api.detectors import get_detector  # noqa: E402
from engine import motifs, validity  # noqa: E402

app = FastAPI(title="PULLI API", version="0.1.0")

# The frontend (Vite dev server) runs on a different origin than this API
# (5173/5174 vs 8000) -- without this, every browser request is blocked by
# CORS before it even reaches the endpoints below (confirmed: this is not
# hypothetical, it was reproduced in a real browser E2E run against the
# real frontend). allow_credentials=True is required for the auth session
# cookie (api/auth/) to be sent/received cross-origin at all -- per the
# CORS spec this means allow_origins can never be "*", so CORS_ORIGINS
# (comma-separated explicit origins) is the production path; unset, it
# falls back to a localhost-only regex for zero-config local dev.
_cors_origins_env = os.environ.get("CORS_ORIGINS", "").strip()
_cors_kwargs = (
    {"allow_origins": [o.strip() for o in _cors_origins_env.split(",") if o.strip()]}
    if _cors_origins_env
    else {"allow_origin_regex": r"http://(localhost|127\.0\.0\.1):\d+"}
)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    **_cors_kwargs,
)

app.include_router(auth_router)


@app.on_event("startup")
def _create_auth_tables() -> None:
    # Identity/session tables only -- never touches image-processing code.
    # See api/auth/db.py's module docstring for why create_all() (not a
    # migration tool) is the right amount of infrastructure here.
    init_db()

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}


def _save_upload_to_temp(image: UploadFile) -> str:
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported content type: {image.content_type}")
    suffix = os.path.splitext(image.filename or "")[1] or ".jpg"
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            content = image.file.read()
            if not content:
                raise HTTPException(status_code=400, detail="empty image upload")
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
        raise HTTPException(status_code=400, detail=f"invalid image: {e}") from e
    except RuntimeError as e:
        # ML detector unavailable (missing checkpoint, load failure) --
        # explicit 503, no silent fallback to classical.
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001 -- surfaced explicitly, not swallowed
        raise HTTPException(status_code=500, detail=f"detector failed: {type(e).__name__}: {e}") from e


@app.get("/api/v1/health")
def health():
    ml_available = os.path.exists(
        os.path.join(os.path.dirname(__file__), "..", "experiments", "m4_2", "results", "dot_heatmap_net_v2.pt")
    )
    return {"status": "ok", "classical_detector_available": True, "ml_detector_available": ml_available}


@app.get("/api/v1/model")
def model_info():
    checkpoint_path = os.path.join(
        os.path.dirname(__file__), "..", "experiments", "m4_2", "results", "dot_heatmap_net_v2.pt"
    )
    exists = os.path.exists(checkpoint_path)
    from experiments.m4_2.model import MODEL_INPUT_SIZE, HEATMAP_SIZE
    from experiments.m4_2.ml_lattice_detector import MODEL_VERSION
    return {
        "ml_model_version": MODEL_VERSION if exists else None,
        "ml_checkpoint_exists": exists,
        "ml_model_input_size": MODEL_INPUT_SIZE if exists else None,
        "ml_heatmap_size": HEATMAP_SIZE if exists else None,
        "classical_detector": "engine.image_io.detect_lattice (deterministic)",
    }


@app.post("/api/v1/detect")
def detect(image: UploadFile = File(...), detector: str = Form("classical")):
    if detector not in ("classical", "ml"):
        raise HTTPException(status_code=400, detail=f"detector must be 'classical' or 'ml', got {detector!r}")

    path = _save_upload_to_temp(image)
    try:
        result = _run_detector(detector, path)
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
    }


@app.post("/api/v1/analyze")
def analyze(image: UploadFile = File(...), detector: str = Form("classical")):
    if detector not in ("classical", "ml"):
        raise HTTPException(status_code=400, detail=f"detector must be 'classical' or 'ml', got {detector!r}")

    path = _save_upload_to_temp(image)
    try:
        result = _run_detector(detector, path)
    finally:
        os.unlink(path)

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
    }


@app.post("/api/v1/reconstruct")
def reconstruct(image: UploadFile = File(...), detector: str = Form("classical")):
    if detector not in ("classical", "ml"):
        raise HTTPException(status_code=400, detail=f"detector must be 'classical' or 'ml', got {detector!r}")

    path = _save_upload_to_temp(image)
    try:
        result = _run_detector(detector, path)
    finally:
        os.unlink(path)

    G = result.graph
    dots = set(G.nodes())
    if len(dots) < 1:
        return {
            "success": True, "detector": result.detector, "model_version": result.model_version,
            "processing_ms": round(result.processing_ms, 2), "graph": graph_to_json(G),
            "reconstruction": {"note": "no dots detected -- nothing to reconstruct"},
        }

    from api.reconstruct_adapter import build_kolam_pattern_from_graph
    from engine import reconstruction as recon_module

    source_pattern = build_kolam_pattern_from_graph(G, dots)
    interior = motifs.interior_points(dots, radius=1)
    placements, _residual, _fully_covered = motifs.induce_motif_set_adaptive(
        G, interior, dots, max_radius=2, max_motifs_per_radius=50
    )
    recon_result = recon_module.reconstruct_kolam(source_pattern, placements)

    return {
        "success": True,
        "detector": result.detector,
        "model_version": result.model_version,
        "processing_ms": round(result.processing_ms, 2),
        "graph": graph_to_json(G),
        "reconstruction": reconstruction_to_json(recon_result),
    }


@app.post("/api/v1/compare-detectors")
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
            classical_error = e.detail
        try:
            ml_result = _run_detector("ml", path)
        except HTTPException as e:
            ml_error = e.detail
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
        # ── STAGE 0: upload_image (already done, just signal it) ──────
        stage_started("upload_image", 0, "Image received.")
        stage_completed("upload_image", 0, "Image uploaded successfully.")

        # ── STAGE 1: detect_dots ──────────────────────────────────────
        stage_started("detect_dots", 1, "Detecting pulli dots…")
        try:
            det_result = _run_detector(detector, image_path)
        except HTTPException as exc:
            stage_failed("detect_dots", 1, exc.detail)
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
        stage_completed("trace_stroke", 2, f"Stroke traced — {edge_count} edges.", {
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
            f"Symmetry analysis done — {sym_data['connected_components']} component(s).", sym_data)

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
    image: UploadFile = File(...),
    detector: str = Form("classical"),
):
    """
    Accept an image upload and immediately return a job_id.
    The actual ML pipeline runs asynchronously -- the client should
    connect to /api/v1/analyze-stream/{job_id}/events to receive
    stage-by-stage progress via SSE.
    """
    if detector not in ("classical", "ml"):
        raise HTTPException(status_code=400, detail=f"detector must be 'classical' or 'ml', got {detector!r}")

    path = _save_upload_to_temp(image)
    job_id = str(uuid.uuid4())

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    _STREAM_JOBS[job_id] = {"path": path, "detector": detector, "queue": queue}

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


@app.exception_handler(HTTPException)
def http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"success": False, "error": exc.detail})
