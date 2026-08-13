"""A/B/variants comparison: does engine.canonicalize.py's alternative
preprocessing improve the EXISTING, UNMODIFIED DotHeatmapNetV2
checkpoint's real-photo behavior? No retraining, no model change --
only the pixels fed to the model change.

Variant A == engine.image_io.preprocess()'s own binarization exactly
(global Otsu) -- the current production path, used here as the "raw"
baseline for a true apples-to-apples comparison.

Populations:
  - synthetic validation (experiments/m4_2/data/val) -- sanity check
    only: canonicalization must not regress the one population with
    real ground truth.
  - all 22 real photos (real_photos/, ithayakkamalam excluded, same
    convention as every prior session) -- NO ground truth; reports raw
    detection/lattice/graph statistics only, never precision/recall.

Confidence threshold and min_distance are held at M4.2's own
validation-selected production values (0.6, 2.0 heatmap cells) for
every variant -- this experiment isolates the PREPROCESSING variable
only, per the task's explicit "do not change the model checkpoint
between A and B" instruction.

Usage:
    python experiments/m4_2_canonicalization/run_comparison.py
"""

from __future__ import annotations

import glob
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
from experiments.m4_1.classical_baseline import REAL_DIR, REAL_EXCLUDED, REAL_INSCOPE  # noqa: E402
from experiments.m4_1.peak_detect import detect_peaks  # noqa: E402
from experiments.m4_2.model import DotHeatmapNetV2, MODEL_INPUT_SIZE, OUTPUT_STRIDE  # noqa: E402

CHECKPOINT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "m4_2", "results", "dot_heatmap_net_v2.pt"
)
VAL_DIR = os.path.join(os.path.dirname(__file__), "..", "m4_2", "data", "val")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

CONFIDENCE_THRESHOLD = 0.6  # unchanged, M4.2's own validation-selected production value
MIN_DISTANCE_HEATMAP_CELLS = 2.0  # unchanged, same
MATCH_TOLERANCE_PX = 6.0


def _load_model():
    model = DotHeatmapNetV2()
    model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location="cpu"))
    model.eval()
    return model


def _detect_from_binary(model, binary: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
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
    elapsed_ms = (time.monotonic() - t0) * 1000
    return pixel_positions, np.array(confidences), elapsed_ms


def _match_metrics(det_px: np.ndarray, gt_px: np.ndarray, tol: float = MATCH_TOLERANCE_PX) -> dict:
    from scipy.spatial import cKDTree

    if len(det_px) == 0 and len(gt_px) == 0:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if len(det_px) == 0:
        return {"precision": 1.0, "recall": 0.0, "f1": 0.0}
    if len(gt_px) == 0:
        return {"precision": 0.0, "recall": 1.0, "f1": 0.0}
    tree_gt = cKDTree(gt_px)
    d_det, _ = tree_gt.query(det_px)
    precision = float((d_det < tol).mean())
    tree_det = cKDTree(det_px)
    d_gt, _ = tree_det.query(gt_px)
    recall = float((d_gt < tol).mean())
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def eval_synthetic(model, variant: str) -> dict:
    rows = []
    for json_path in sorted(glob.glob(os.path.join(VAL_DIR, "*.json"))):
        with open(json_path) as f:
            gt = json.load(f)
        img_path = gt["image_path"]
        gt_positions = list(gt["dot_pixel_positions"].values())

        binary, rotation = canonicalize(img_path, variant=variant)
        img = cv2.imread(img_path)
        h, w = img.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), rotation, 1.0)
        gt_px = cv2.transform(np.array(gt_positions, dtype=np.float32).reshape(-1, 1, 2), M).reshape(-1, 2)

        det_px, _conf, _ms = _detect_from_binary(model, binary)
        rows.append(_match_metrics(det_px, gt_px))

    return {
        "n_images": len(rows),
        "mean_recall": float(np.mean([r["recall"] for r in rows])),
        "mean_precision": float(np.mean([r["precision"] for r in rows])),
        "mean_f1": float(np.mean([r["f1"] for r in rows])),
    }


def eval_real_photos(model, variant: str, run_graph: bool = True) -> dict:
    """`run_graph=False` skips trace_path/skeletonize (the expensive
    step on large real photos, some up to 9248x6936px) -- used for the
    fast 5-variant screening pass. The FULL graph-construction check
    (`run_graph=True`, the default) is run afterward only for the
    baseline and the winning variant, per this experiment's time budget
    -- see docs/M4_2_CANONICALIZATION_EVALUATION.md Section on
    methodology for why detection/lattice-fit alone was used to screen
    all 5 variants first."""
    per_image = []
    errors = []
    for path in sorted(glob.glob(os.path.join(REAL_DIR, "*.jpg"))):
        fname = os.path.basename(path)
        if fname in REAL_EXCLUDED:
            continue
        try:
            binary, rotation = canonicalize(path, variant=variant)
            det_px, conf, latency_ms = _detect_from_binary(model, binary)

            pts = [(float(x), float(y)) for x, y in det_px]
            lattice_coords = image_io._fit_lattice_coords(det_px)[0] if len(det_px) >= 3 else []
            lattice_fit_success = len(lattice_coords) >= 3

            row = {
                "file": fname,
                "in_scope": fname in REAL_INSCOPE,
                "n_detections": len(det_px),
                "lattice_fit_success": lattice_fit_success,
                "latency_ms": latency_ms,
                "error": None,
            }

            if run_graph:
                # Real graph/connectivity check using the CANONICALIZED
                # binary mask itself (the actual ink pixels this variant
                # produced) -- reuses engine.image_io.trace_path UNMODIFIED.
                preprocessed = image_io.Preprocessed(binary=binary, rotation_deg=0.0)
                lattice = image_io.Lattice(pts, lattice_coords, 5.0)
                assert_conforms(lattice)
                edges = image_io.trace_path(preprocessed, lattice) if image_io.is_traceable(lattice) else []
                G = nx.MultiGraph()
                G.add_nodes_from(lattice.lattice_coords)
                for a, b in edges:
                    G.add_edge(a, b)
                n_components = nx.number_connected_components(G) if G.number_of_nodes() else 0
                n_odd = sum(1 for _n, d in G.degree() if d % 2 == 1) if G.number_of_nodes() else None
                connected = (n_components == 1) if G.number_of_nodes() else False
                row.update(
                    {
                        "graph_n_nodes": G.number_of_nodes(),
                        "graph_n_edges": G.number_of_edges(),
                        "graph_n_components": n_components,
                        "graph_connected": connected,
                        "graph_n_odd_degree": n_odd,
                    }
                )

            per_image.append(row)
        except Exception as e:  # noqa: BLE001 -- benchmark script: record, never crash the sweep
            errors.append({"file": fname, "error": f"{type(e).__name__}: {e}"})
            per_image.append({"file": fname, "in_scope": fname in REAL_INSCOPE, "error": str(e)})

    inscope = [r for r in per_image if r.get("in_scope") and r.get("error") is None]
    nodot = [r for r in per_image if not r.get("in_scope") and r.get("error") is None]
    nodot_fp = sum(1 for r in nodot if r["n_detections"] > 0)

    return {
        "n_images": len(per_image),
        "n_crashes": len(errors),
        "errors": errors,
        "inscope": inscope,
        "nodot_n": len(nodot),
        "nodot_fp": nodot_fp,
        "nodot_fp_rate": (nodot_fp / len(nodot)) if nodot else None,
        "mean_latency_ms": float(np.mean([r["latency_ms"] for r in per_image if r.get("error") is None])) if per_image else None,
        "n_lattice_fit_success_inscope": sum(1 for r in inscope if r["lattice_fit_success"]),
        "n_graph_connected_inscope": (
            sum(1 for r in inscope if r.get("graph_connected")) if run_graph else None
        ),
    }


def main():
    print("Loading checkpoint...")
    model = _load_model()

    results = {"config": {"confidence_threshold": CONFIDENCE_THRESHOLD, "variants": VARIANTS}, "variants": {}}

    # PASS 1 (fast): detection + lattice-fit only, all 5 variants, no
    # trace_path/skeletonize -- the expensive step on some real photos
    # up to 9248x6936px. Screens all variants against the metric
    # hierarchy's first, cheaply-measurable levels (no-dot FP rate,
    # lattice-fit success) within this experiment's time budget.
    for variant in VARIANTS:
        print(f"\n=== Variant {variant} (fast pass: detection + lattice-fit only) ===")
        synth = eval_synthetic(model, variant)
        print(f"  synthetic val: recall={synth['mean_recall']:.4f} precision={synth['mean_precision']:.4f} f1={synth['mean_f1']:.4f}")
        real = eval_real_photos(model, variant, run_graph=False)
        print(
            f"  real photos: no_dot_fp_rate={real['nodot_fp_rate']:.4f} ({real['nodot_fp']}/{real['nodot_n']}) "
            f"crashes={real['n_crashes']} lattice_fit_inscope={real['n_lattice_fit_success_inscope']}/4 "
            f"mean_latency={real['mean_latency_ms']:.1f}ms"
        )
        results["variants"][variant] = {"synthetic_val": synth, "real_photos_fast": real}

    # Select the variant with the lowest no-dot FP rate; ties broken by
    # highest in-scope lattice-fit success -- matches this experiment's
    # own documented metric hierarchy (false positives first, THEN
    # detection/fit quality, never raw detection count alone).
    def _rank(v):
        r = results["variants"][v]["real_photos_fast"]
        return (r["nodot_fp_rate"], -r["n_lattice_fit_success_inscope"])

    non_baseline = [v for v in VARIANTS if v != "A"]
    winner = min(non_baseline, key=_rank)
    print(f"\nFast-pass winner (excluding baseline A): variant {winner}")

    # PASS 2 (full): trace_path/graph construction, ONLY for the
    # baseline (A) and the winner -- the expensive check, run just
    # twice per photo instead of five times, per this experiment's time
    # budget.
    for variant in ("A", winner) if winner != "A" else ("A",):
        print(f"\n=== Variant {variant} (full pass: + graph construction) ===")
        real_full = eval_real_photos(model, variant, run_graph=True)
        print(
            f"  graph_connected_inscope={real_full['n_graph_connected_inscope']}/4 "
            f"lattice_fit_inscope={real_full['n_lattice_fit_success_inscope']}/4"
        )
        results["variants"][variant]["real_photos_full"] = real_full

    results["winner"] = winner

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, "comparison.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
