from __future__ import annotations

import os
import sys
from typing import Optional
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Query

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.detectors import run_classical_detector, run_ml_detector, compare_classical_and_ml_detectors
from backend.services.analysis_service import analyze_kolam_image
from backend.utils.image_utils import download_image_from_url, validate_and_save_upload
from engine.kolam_pattern import KolamPattern
from engine.reconstruction import reconstruct_kolam
from engine.validity import check_validity, is_valid_single_stroke

router = APIRouter(prefix="/api/v1", tags=["V1 API Endpoints"])


async def _resolve_image_path(image: Optional[UploadFile], image_url: Optional[str]) -> str:
    if image is not None and image.filename:
        file_bytes = await image.read()
        if len(file_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image size exceeds 10MB limit.")
        try:
            return validate_and_save_upload(file_bytes, image.filename)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
    elif image_url and image_url.strip():
        try:
            return await download_image_from_url(image_url.strip())
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch image URL: {e}")
    else:
        sample_path = os.path.join(PROJECT_ROOT, "real_photos", "kolam2_tshrinivasan.jpg")
        if os.path.exists(sample_path):
            return sample_path
        raise HTTPException(status_code=400, detail="Must provide an image file or image_url.")


@router.get("/health")
async def health_v1():
    """Basic liveness check."""
    return {"status": "ok", "version": "1.0.0", "engine": "PULLI Graph & Motif Engine"}


@router.get("/model")
async def model_v1():
    """Currently-loaded ML model version/info."""
    checkpoint_path = os.path.join(PROJECT_ROOT, "experiments", "m4_1", "results", "dot_heatmap_net.pt")
    exists = os.path.exists(checkpoint_path)
    return {
        "loaded": exists,
        "architecture": "DotHeatmapNet",
        "input_size": 128,
        "stride": 4,
        "checkpoint_path": checkpoint_path if exists else None,
        "status": "ready" if exists else "no_checkpoint",
    }


@router.post("/detect")
async def detect_v1(
    image: Optional[UploadFile] = File(None),
    image_url: Optional[str] = Form(None),
    detector: str = Form("classical"),
):
    """Upload an image -> run dot-lattice detection (classical or ML), return detected dots + graph."""
    filepath = await _resolve_image_path(image, image_url)
    
    if detector.lower() == "ml":
        prep, lattice, edges, G, info = run_ml_detector(filepath)
    else:
        prep, lattice, edges, G = run_classical_detector(filepath)
        info = {"available": True, "status": "ok"}

    dots_list = []
    if lattice and lattice.pixel_positions:
        for idx, (px, py) in enumerate(lattice.pixel_positions):
            lc = lattice.lattice_coords[idx] if idx < len(lattice.lattice_coords) else (0, 0)
            dots_list.append({
                "pixel_x": float(px),
                "pixel_y": float(py),
                "lattice_x": int(lc[0]),
                "lattice_y": int(lc[1]),
            })

    formatted_edges = [[list(a), list(b)] for a, b in edges]

    return {
        "detector": detector,
        "detector_info": info,
        "dot_count": len(dots_list),
        "dot_radius": float(lattice.dot_radius) if lattice else 0.0,
        "dots": dots_list,
        "edges": formatted_edges,
        "graph": {
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
        },
    }


@router.post("/analyze")
async def analyze_v1(
    image: Optional[UploadFile] = File(None),
    image_url: Optional[str] = Form(None),
    detector: str = Form("classical"),
    specifications: Optional[str] = Form(None),
):
    """Detect + run full engine analysis on the result (geometry, validity, symmetry, motifs)."""
    filepath = await _resolve_image_path(image, image_url)
    result = analyze_kolam_image(filepath, specifications=specifications)
    return result


@router.post("/reconstruct")
async def reconstruct_v1(
    image: Optional[UploadFile] = File(None),
    image_url: Optional[str] = Form(None),
    residual_policy: str = Form("exact"),
):
    """Run engine/reconstruction.py's motif+residual reconstruction against a detected/uploaded pattern."""
    filepath = await _resolve_image_path(image, image_url)
    prep, lattice, edges, G = run_classical_detector(filepath)

    if G.number_of_nodes() < 3:
        return {
            "status": "degenerate_input",
            "message": "Fewer than 3 dots detected; reconstruction requires a valid dot lattice.",
            "is_valid": False,
        }

    dots_set = set(lattice.lattice_coords)
    source_pattern = KolamPattern(
        pattern_id=1,
        collection="uploaded",
        raw_trace=np.zeros((0, 2)),
        trace_points=(),
        dot_points=dots_set,
        edges=tuple(edges),
        edge_multiplicity={frozenset(e): edges.count(e) for e in set(edges)},
        graph=G,
        bounding_box=(0, 0, 10, 10),
    )

    try:
        recon_result = reconstruct_kolam(source_pattern, [], residual_policy=residual_policy)
        val_info = check_validity(recon_result.candidate_graph)
        is_valid = is_valid_single_stroke(recon_result.candidate_graph)

        return {
            "status": "ok",
            "is_valid": is_valid,
            "capped_excess": recon_result.capped_excess,
            "residual_edges_added": recon_result.residual_edges_added,
            "edge_recall": recon_result.edge_recall,
            "connected_components": val_info.get("connected_components", 1),
            "is_eulerian_circuit": val_info.get("is_eulerian_circuit", False),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "is_valid": False,
        }


@router.post("/compare-detectors")
async def compare_detectors_v1(
    image: Optional[UploadFile] = File(None),
    image_url: Optional[str] = Form(None),
):
    """Run classical and ML detectors on the same image, return both + diff metrics."""
    filepath = await _resolve_image_path(image, image_url)
    result = compare_classical_and_ml_detectors(filepath)
    return result
