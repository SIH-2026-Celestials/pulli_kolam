"""M4.1 gating experiment (Phase 6 of the ML completion campaign):
investigate whether a principled gate -- confidence threshold beyond the
range M4.2's own validation-only sweep tested (peak_sweep.py only tried
0.2-0.6, see docs/M4_2_MODEL.md), and/or a lattice-geometric-consistency
check -- can reduce the ML detector's documented 100% no-dot
false-positive rate WITHOUT destroying its already-marginal usefulness
on real in-scope photos.

Uses the EXISTING trained checkpoint (experiments/m4_2/results/
dot_heatmap_net_v2.pt) unmodified -- no retraining. Reuses
experiments/m4_1/peak_detect.py's detect_peaks() and
engine.image_io._fit_lattice_coords() UNMODIFIED.

Methodology discipline (same as peak_sweep.py originally established):
the CONFIDENCE-THRESHOLD SWEEP is measured on the VALIDATION set only
(experiments/m4_2/data/val) -- the held-out TEST set is touched exactly
once, at the very end, to confirm the FINALLY SELECTED configuration,
never used to choose among candidates. Real photos have no pixel-exact
ground truth (unchanged fact, see docs/M4_EVALUATION_PROTOCOL.md) --
real-photo numbers here are raw detection counts / false-positive
firing, never reported as precision/recall.

LATTICE-CONSISTENCY GATE: after peak detection, attempt
engine.image_io._fit_lattice_coords on the raw peaks (same function the
classical detector and both ML adapters already use) and compute the
mean residual between the fitted affine lattice's predicted pixel
positions and the actual detected positions. A real, roughly-periodic
dot grid should fit an affine lattice tightly (low residual); scattered
texture/noise firings should not. If the residual exceeds
LATTICE_RESIDUAL_THRESHOLD_PX, the WHOLE detection is rejected (collapsed
to empty) -- this is a per-image gate, not a per-point filter, matching
the existing "collapse sparse/malformed detections to empty" convention
already used throughout the ML adapters (docs/ML_CONTRACT.md).

Usage:
    python experiments/m4_2/gating_experiment.py
"""

from __future__ import annotations

import glob
import json
import os
import sys
import time

import cv2
import numpy as np
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from engine import image_io  # noqa: E402
from engine.image_io import _fit_lattice_coords  # noqa: E402
from experiments.m4_1.classical_baseline import REAL_DIR, REAL_EXCLUDED, REAL_INSCOPE  # noqa: E402
from experiments.m4_1.peak_detect import detect_peaks  # noqa: E402
from experiments.m4_2.model import DotHeatmapNetV2, MODEL_INPUT_SIZE, OUTPUT_STRIDE  # noqa: E402

CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "results", "dot_heatmap_net_v2.pt")
VAL_DIR = os.path.join(os.path.dirname(__file__), "data", "val")
TEST_DIR = os.path.join(os.path.dirname(__file__), "data", "test")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results", "gating_experiment.json")

MIN_DISTANCE_HEATMAP_CELLS = 2.0  # unchanged from M4.2's own validation-selected value (peak_sweep.json)
MATCH_TOLERANCE_PX = 6.0

# Extends M4.2's own peak_sweep.py range (0.2-0.6) upward -- that sweep
# never tested whether pushing PAST 0.6 trades a little synthetic recall
# (already ~0.999 at 0.6, so there is headroom) for fewer real
# false-positives.
THRESHOLDS = [0.6, 0.7, 0.8, 0.9, 0.95, 0.99]

# Calibration for this constant is reported in
# docs/M4_1_ML_COMPLETION_REPORT.md, not assumed -- selected from the
# empirical residual DISTRIBUTION measured below (Section "lattice
# residual distribution"), not chosen to make a headline number look good.
LATTICE_RESIDUAL_THRESHOLD_PX = 10.0


def _load_model():
    model = DotHeatmapNetV2()
    model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location="cpu"))
    model.eval()
    return model


def _raw_detect(model, preprocessed, threshold: float, min_distance: float):
    """Same forward pass LearnedLatticeDetectorV2 uses, but with
    `threshold` as an explicit parameter (that class hardcodes
    CONFIDENCE_THRESHOLD) so this script can sweep it without touching
    the frozen adapter or the ML contract."""
    binary = preprocessed.binary
    h, w = binary.shape
    resized = cv2.resize(binary, (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE), interpolation=cv2.INTER_AREA)
    img_t = torch.from_numpy(resized.astype(np.float32) / 255.0).unsqueeze(0).unsqueeze(0)
    with torch.no_grad():
        heatmap = torch.sigmoid(model(img_t))[0, 0].numpy()
    fx, fy = w / MODEL_INPUT_SIZE, h / MODEL_INPUT_SIZE
    peaks, confidences = detect_peaks(heatmap, threshold=threshold, min_distance_px=min_distance)
    pixel_positions = [(hx * OUTPUT_STRIDE * fx, hy * OUTPUT_STRIDE * fy) for hy, hx in peaks]
    return np.array(pixel_positions).reshape(-1, 2), np.array(confidences)


def _lattice_residual_px(pixel_positions: np.ndarray) -> "float | None":
    """None if too few points to fit (< 3) -- matches
    _fit_lattice_coords's own minimum. Otherwise the mean L2 pixel
    distance between the fitted affine lattice's PREDICTED positions and
    the actual detected positions -- low = plausible regular grid,
    high = scattered/non-periodic."""
    if len(pixel_positions) < 3:
        return None
    coords, M, t = _fit_lattice_coords(pixel_positions)
    pred = (M @ np.array(coords).T).T + t
    return float(np.sqrt(((pred - pixel_positions) ** 2).sum(axis=1)).mean())


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


def _deskewed_gt(image_path: str, gt_positions: list, preprocessed) -> np.ndarray:
    img = cv2.imread(image_path)
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), preprocessed.rotation_deg, 1.0)
    arr = np.array(gt_positions, dtype=np.float32)
    return cv2.transform(arr.reshape(-1, 1, 2), M).reshape(-1, 2)


def sweep_synthetic(model, directory: str, thresholds: list, apply_gate: bool) -> dict:
    """Sweep confidence thresholds (optionally + the lattice-consistency
    gate) against a synthetic ground-truth set. Precision/recall/F1 use
    the SAME matching convention M4.2's own evaluate_m4_2.py uses."""
    per_threshold = {t: [] for t in thresholds}
    for json_path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        with open(json_path) as f:
            gt = json.load(f)
        img_path = gt["image_path"]
        gt_positions = list(gt["dot_pixel_positions"].values())
        preprocessed = image_io.preprocess(img_path)
        gt_px = _deskewed_gt(img_path, gt_positions, preprocessed)

        for t in thresholds:
            det_px, _conf = _raw_detect(model, preprocessed, t, MIN_DISTANCE_HEATMAP_CELLS)
            if apply_gate:
                resid = _lattice_residual_px(det_px)
                if resid is None or resid > LATTICE_RESIDUAL_THRESHOLD_PX:
                    det_px = np.empty((0, 2))
            per_threshold[t].append(_match_metrics(det_px, gt_px))

    return {
        t: {
            "mean_precision": float(np.mean([r["precision"] for r in rows])),
            "mean_recall": float(np.mean([r["recall"] for r in rows])),
            "mean_f1": float(np.mean([r["f1"] for r in rows])),
        }
        for t, rows in per_threshold.items()
    }


def sweep_real_photos(model, thresholds: list, apply_gate: bool) -> dict:
    """No ground truth (per docs/M4_EVALUATION_PROTOCOL.md) -- reports
    raw detection counts and no-dot false-positive firing only, never
    precision/recall for real photos."""
    per_threshold = {t: {"inscope": [], "nodot_fp": 0, "nodot_n": 0, "nodot_residuals": []} for t in thresholds}

    for path in sorted(glob.glob(os.path.join(REAL_DIR, "*.jpg"))):
        fname = os.path.basename(path)
        if fname in REAL_EXCLUDED:
            continue
        preprocessed = image_io.preprocess(path)

        for t in thresholds:
            det_px, conf = _raw_detect(model, preprocessed, t, MIN_DISTANCE_HEATMAP_CELLS)
            resid = _lattice_residual_px(det_px)
            gated_det_px = det_px
            if apply_gate:
                if resid is None or resid > LATTICE_RESIDUAL_THRESHOLD_PX:
                    gated_det_px = np.empty((0, 2))

            if fname in REAL_INSCOPE:
                per_threshold[t]["inscope"].append(
                    {"file": fname, "n_raw": len(det_px), "n_gated": len(gated_det_px), "lattice_residual_px": resid}
                )
            else:
                per_threshold[t]["nodot_n"] += 1
                if len(gated_det_px) > 0:
                    per_threshold[t]["nodot_fp"] += 1
                if resid is not None:
                    per_threshold[t]["nodot_residuals"].append(resid)

    for t in thresholds:
        d = per_threshold[t]
        d["nodot_fp_rate"] = d["nodot_fp"] / d["nodot_n"] if d["nodot_n"] else None

    return per_threshold


def main():
    print("Loading checkpoint...")
    model = _load_model()

    print("Sweeping confidence threshold on VALIDATION set (synthetic, ungated)...")
    synth_val_ungated = sweep_synthetic(model, VAL_DIR, THRESHOLDS, apply_gate=False)
    for t, m in synth_val_ungated.items():
        print(f"  t={t}: recall={m['mean_recall']:.4f} precision={m['mean_precision']:.4f} f1={m['mean_f1']:.4f}")

    print("Sweeping confidence threshold on real photos (ungated)...")
    real_ungated = sweep_real_photos(model, THRESHOLDS, apply_gate=False)
    for t, d in real_ungated.items():
        print(f"  t={t}: no_dot_fp_rate={d['nodot_fp_rate']:.4f} ({d['nodot_fp']}/{d['nodot_n']})")

    print("Measuring lattice-residual distribution (threshold=0.6, the current production value)...")
    residuals_nodot = real_ungated[0.6]["nodot_residuals"]
    residuals_inscope = [r["lattice_residual_px"] for r in real_ungated[0.6]["inscope"] if r["lattice_residual_px"] is not None]
    print(f"  no-dot photos' residuals: {sorted(residuals_nodot)}")
    print(f"  in-scope photos' residuals: {sorted(residuals_inscope)}")

    print("Sweeping confidence threshold on VALIDATION set (synthetic, WITH lattice gate)...")
    synth_val_gated = sweep_synthetic(model, VAL_DIR, THRESHOLDS, apply_gate=True)
    for t, m in synth_val_gated.items():
        print(f"  t={t}: recall={m['mean_recall']:.4f} precision={m['mean_precision']:.4f} f1={m['mean_f1']:.4f}")

    print("Sweeping confidence threshold on real photos (WITH lattice gate)...")
    real_gated = sweep_real_photos(model, THRESHOLDS, apply_gate=True)
    for t, d in real_gated.items():
        print(f"  t={t}: no_dot_fp_rate={d['nodot_fp_rate']:.4f} ({d['nodot_fp']}/{d['nodot_n']})")

    results = {
        "config": {
            "thresholds": THRESHOLDS,
            "min_distance_heatmap_cells": MIN_DISTANCE_HEATMAP_CELLS,
            "lattice_residual_threshold_px": LATTICE_RESIDUAL_THRESHOLD_PX,
        },
        "synthetic_val_ungated": synth_val_ungated,
        "synthetic_val_gated": synth_val_gated,
        "real_photos_ungated": real_ungated,
        "real_photos_gated": real_gated,
    }
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
