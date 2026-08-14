"""Graph-QUALITY benchmark for engine/canonicalize.py's variants
(A-G), against the EXISTING, UNMODIFIED DotHeatmapNetV2 checkpoint --
no retraining, no model change. Unlike
experiments/m4_2_canonicalization/run_comparison.py (which measured
no-dot FALSE-POSITIVE suppression across all 22 real photos), THIS
script measures downstream STRUCTURAL GRAPH QUALITY (connected
components, odd-degree nodes, Eulerian validity) on the 4 REAL IN-SCOPE
photos only -- the ones that actually contain a dot lattice, where
"does preprocessing produce a BETTER graph" is a meaningful question at
all. Full trace_path/skeletonize is affordable at n=4 images (unlike
n=22), so this script always runs the complete pipeline, no fast/slow
split needed.

No specific "260x280 dense sikku kolam with a watermark" image was
available this session (not present in the repository, and the API
never persists uploads) -- `kolam_naduveetu_meenakshisundaram.jpg` is
used as the closest available real stand-in: it is this project's
densest, lowest-contrast in-scope real photo (gray mean 72.6, std 63.4,
3072x2304, Otsu raw foreground fraction 71.9% -- badly over-binarized,
the same documented failure mode), and produces the largest ML
over-detection of any real photo in the corpus (563 raw detections at
the production threshold).

Usage:
    python experiments/real_image_preprocessing/run_graph_benchmark.py
"""

from __future__ import annotations

import json
import os
import sys
import time

import cv2
import networkx as nx
import numpy as np
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from engine import image_io  # noqa: E402
from engine.canonicalize import VARIANTS, canonicalize  # noqa: E402
from engine.ml_contract import assert_conforms  # noqa: E402
from engine.validity import check_validity  # noqa: E402
from experiments.m4_1.classical_baseline import REAL_INSCOPE  # noqa: E402
from experiments.m4_1.peak_detect import detect_peaks  # noqa: E402
from experiments.m4_2.model import DotHeatmapNetV2, MODEL_INPUT_SIZE, OUTPUT_STRIDE  # noqa: E402

CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "..", "m4_2", "results", "dot_heatmap_net_v2.pt")
REAL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "real_photos")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

CONFIDENCE_THRESHOLD = 0.6  # unchanged, M4.2's own validation-selected production value
MIN_DISTANCE_HEATMAP_CELLS = 2.0  # unchanged, same

# The densest in-scope photo first -- the primary stand-in for this
# task's "dense sikku kolam" scenario, per the module docstring.
TARGET_PHOTOS = [
    "kolam_naduveetu_meenakshisundaram.jpg",
    "kolam_attur1_infofarmer.jpg",
    "muggu_kollam_sirensongs.jpg",
    "kolam2_tshrinivasan.jpg",
]
assert set(TARGET_PHOTOS) == REAL_INSCOPE


def _load_model():
    model = DotHeatmapNetV2()
    model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location="cpu"))
    model.eval()
    return model


def _detect(model, binary: np.ndarray):
    t0 = time.monotonic()
    h, w = binary.shape
    resized = cv2.resize(binary, (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE), interpolation=cv2.INTER_AREA)
    img_t = torch.from_numpy(resized.astype(np.float32) / 255.0).unsqueeze(0).unsqueeze(0)
    with torch.no_grad():
        heatmap = torch.sigmoid(model(img_t))[0, 0].numpy()
    fx, fy = w / MODEL_INPUT_SIZE, h / MODEL_INPUT_SIZE
    peaks, confidences = detect_peaks(heatmap, threshold=CONFIDENCE_THRESHOLD, min_distance_px=MIN_DISTANCE_HEATMAP_CELLS)
    pixel_positions = np.array(
        [(hx * OUTPUT_STRIDE * fx, hy * OUTPUT_STRIDE * fy) for (hy, hx) in peaks]
    ).reshape(-1, 2)
    latency_ms = (time.monotonic() - t0) * 1000
    return pixel_positions, np.array(confidences), latency_ms


def evaluate_one(model, image_path: str, variant: str) -> dict:
    if variant == "raw":
        binary, rotation = image_io.preprocess(image_path).binary, image_io.preprocess(image_path).rotation_deg
    else:
        binary, rotation = canonicalize(image_path, variant=variant)

    det_px, conf, latency_ms = _detect(model, binary)
    pts = [(float(x), float(y)) for x, y in det_px]

    lattice_coords = image_io._fit_lattice_coords(det_px)[0] if len(det_px) >= 3 else []
    lattice = image_io.Lattice(pts, lattice_coords, 5.0)
    assert_conforms(lattice)

    preprocessed = image_io.Preprocessed(binary=binary, rotation_deg=rotation)
    edges = image_io.trace_path(preprocessed, lattice) if image_io.is_traceable(lattice) else []

    G = nx.MultiGraph()
    G.add_nodes_from(lattice.lattice_coords)
    for a, b in edges:
        G.add_edge(a, b)

    if G.number_of_nodes() > 0:
        validity = check_validity(G)
    else:
        validity = {
            "connected_components": 0, "is_eulerian_circuit": False,
            "has_eulerian_path": False, "largest_component_covers_all_nodes": False,
        }
    n_odd = sum(1 for _n, d in G.degree() if d % 2 == 1) if G.number_of_nodes() else None
    reconstruction_valid = bool(
        validity["largest_component_covers_all_nodes"]
        and (validity["is_eulerian_circuit"] or validity["has_eulerian_path"])
    )

    return {
        "variant": variant,
        "n_dots": len(det_px),
        "lattice_fit_success": len(lattice_coords) >= 3,
        "graph_n_nodes": G.number_of_nodes(),
        "graph_n_edges": G.number_of_edges(),
        "connected_components": validity["connected_components"],
        "connected": validity["largest_component_covers_all_nodes"],
        "odd_degree_nodes": n_odd,
        "is_eulerian_circuit": validity["is_eulerian_circuit"],
        "has_eulerian_path": validity["has_eulerian_path"],
        "eulerian_valid": validity["is_eulerian_circuit"] or validity["has_eulerian_path"],
        "reconstruction_valid": reconstruction_valid,
        "latency_ms": latency_ms,
    }


def main():
    print("Loading checkpoint...")
    model = _load_model()

    results = {}
    for fname in TARGET_PHOTOS:
        path = os.path.join(REAL_DIR, fname)
        print(f"\n=== {fname} ===")
        rows = {}
        for variant in ["raw"] + list(VARIANTS):
            row = evaluate_one(model, path, variant)
            rows[variant] = row
            print(
                f"  {variant:>4s}: dots={row['n_dots']:>4d} edges={row['graph_n_edges']:>5d} "
                f"components={row['connected_components']:>3d} odd={str(row['odd_degree_nodes']):>4s} "
                f"eulerian={row['eulerian_valid']!s:>5s} recon_valid={row['reconstruction_valid']!s:>5s} "
                f"latency={row['latency_ms']:.0f}ms"
            )
        results[fname] = rows

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, "graph_benchmark.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
