from __future__ import annotations

import os
import sys
import numpy as np
import networkx as nx

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from engine.image_io import preprocess, detect_lattice, trace_path, Lattice, Preprocessed


def run_classical_detector(image_path: str) -> tuple[Preprocessed, Lattice, list, nx.MultiGraph]:
    """Run classical CV distance-transform + peak local maxima dot detection."""
    preprocessed = preprocess(image_path)
    lattice = detect_lattice(preprocessed)
    edges = trace_path(preprocessed, lattice)
    G = nx.MultiGraph()
    G.add_nodes_from(lattice.lattice_coords)
    for a, b in edges:
        G.add_edge(a, b)
    return preprocessed, lattice, edges, G


def run_ml_detector(image_path: str) -> tuple[Preprocessed, Lattice, list, nx.MultiGraph, dict]:
    """Run learned ML dot-heatmap network detector if available."""
    preprocessed = preprocess(image_path)
    info = {"available": False, "status": "unknown"}

    try:
        import torch
        from experiments.m4_1.ml_lattice_detector import LearnedLatticeDetector, CHECKPOINT_PATH
        
        if not os.path.exists(CHECKPOINT_PATH):
            info = {"available": False, "status": "checkpoint_missing", "path": CHECKPOINT_PATH}
            lattice = Lattice([], [], 0.0)
            edges = []
            G = nx.MultiGraph()
            return preprocessed, lattice, edges, G, info

        detector = LearnedLatticeDetector(CHECKPOINT_PATH)
        lattice = detector(preprocessed)
        edges = trace_path(preprocessed, lattice)
        G = nx.MultiGraph()
        G.add_nodes_from(lattice.lattice_coords)
        for a, b in edges:
            G.add_edge(a, b)
        
        info = {"available": True, "status": "ok", "checkpoint": CHECKPOINT_PATH}
        return preprocessed, lattice, edges, G, info

    except ImportError:
        info = {"available": False, "status": "torch_not_installed"}
        lattice = Lattice([], [], 0.0)
        edges = []
        G = nx.MultiGraph()
        return preprocessed, lattice, edges, G, info
    except Exception as e:
        info = {"available": False, "status": f"error: {str(e)}"}
        lattice = Lattice([], [], 0.0)
        edges = []
        G = nx.MultiGraph()
        return preprocessed, lattice, edges, G, info


def compare_classical_and_ml_detectors(image_path: str) -> dict:
    """Run classical and ML detectors on the same image and compute spatial diff metrics."""
    prep_c, lat_c, edges_c, G_c = run_classical_detector(image_path)
    prep_m, lat_m, edges_m, G_m, info_m = run_ml_detector(image_path)

    dots_c = lat_c.pixel_positions if lat_c else []
    dots_m = lat_m.pixel_positions if lat_m else []

    # Spatial match matching within 15px radius
    matched_c = set()
    matched_m = set()
    radius_thresh = 15.0

    for i, pc in enumerate(dots_c):
        for j, pm in enumerate(dots_m):
            dist = np.hypot(pc[0] - pm[0], pc[1] - pm[1])
            if dist <= radius_thresh:
                matched_c.add(i)
                matched_m.add(j)

    matched_count = len(matched_c)
    classical_only_count = len(dots_c) - matched_count
    ml_only_count = len(dots_m) - len(matched_m)

    return {
        "classical": {
            "dot_count": len(dots_c),
            "dots": [{"x": float(p[0]), "y": float(p[1])} for p in dots_c],
            "dot_radius": float(lat_c.dot_radius) if lat_c else 0.0,
        },
        "ml": {
            "status": info_m["status"],
            "available": info_m["available"],
            "dot_count": len(dots_m),
            "dots": [{"x": float(p[0]), "y": float(p[1])} for p in dots_m],
            "dot_radius": float(lat_m.dot_radius) if lat_m else 0.0,
        },
        "comparison": {
            "matched_count": matched_count,
            "classical_only_count": classical_only_count,
            "ml_only_count": ml_only_count,
            "match_rate": round(matched_count / max(1, len(dots_c)), 4),
        },
    }
