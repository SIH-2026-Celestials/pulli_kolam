"""M4.1.1: diagnose WHERE M4.1's learned-detector failure actually comes
from -- the CNN heatmap itself, peak_detect.py's extraction, a data/
degradation mismatch, or some combination. Evaluates the EXISTING,
already-trained checkpoint (experiments/m4_1/results/dot_heatmap_net.pt)
ONLY -- no retraining, no architecture change, no changes to the frozen
ML contract, trace_path, the classical detector, or peak_detect.py /
ml_lattice_detector.py themselves.

Run with: KMP_DUPLICATE_LIB_OK=TRUE python diagnose_m4_1_heatmap.py
(same OpenMP-conflict requirement documented in PROJECT_STATE.md for any
script combining torch inference with engine.image_io in one process --
this script's peak-detection ablation calls detect_peaks only, which is
pure numpy/no MKL lstsq, but preprocess() still uses cv2/numpy alongside
torch, so the flag is set defensively.)

Outputs:
  diagnostics/m4_1_heatmap_results.json   -- full per-image machine-readable results
  diagnostics/M4_1_HEATMAP_DIAGNOSIS.md   -- the required markdown report
  diagnostics/m4_1_heatmaps/*.png          -- representative visualizations (not committed)
"""

from __future__ import annotations

import glob
import json
import os
import sys

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from engine import image_io  # noqa: E402
from experiments.m4_1.model import DotHeatmapNet, MODEL_INPUT_SIZE, STRIDE, make_gaussian_heatmap  # noqa: E402
from experiments.m4_1.peak_detect import detect_peaks  # noqa: E402
from experiments.m4_1.ml_lattice_detector import (  # noqa: E402
    CHECKPOINT_PATH, CONFIDENCE_THRESHOLD, MIN_PEAK_DISTANCE_HEATMAP_CELLS,
)
from experiments.m4_1.classical_baseline import (  # noqa: E402
    REAL_DIR, REAL_EXCLUDED, REAL_INSCOPE, REAL_INSCOPE_ESTIMATES,
)

DIAG_DIR = "diagnostics"
VIZ_DIR = os.path.join(DIAG_DIR, "m4_1_heatmaps")
RESULTS_JSON = os.path.join(DIAG_DIR, "m4_1_heatmap_results.json")
REPORT_MD = os.path.join(DIAG_DIR, "M4_1_HEATMAP_DIAGNOSIS.md")

HEATMAP_SIZE = MODEL_INPUT_SIZE // STRIDE
MATCH_TOLERANCE_PX = 6.0  # unchanged convention, matches tests/test_image_io.py etc.

M4_1_DATA_DIR = os.path.join("experiments", "m4_1", "data")

# ============================================================
# Pattern-disjoint check (must match generate_training_data.py exactly)
# ============================================================

CSV19 = "kolam_data/Kolam CSV files/Kolam CSV files/kolam19.csv"
CSV29 = "kolam_data/Kolam CSV files/Kolam CSV files/kolam29.csv"
TRAIN_PATTERNS = {(CSV19, n) for n in [10, 15, 20, 30, 40, 60, 70, 90, 120, 160, 180, 200]} | {
    (CSV29, n) for n in [5, 10, 15, 25, 30, 35]
}
VAL_PATTERNS = {(CSV19, n) for n in [220, 240, 260]} | {(CSV29, n) for n in [40, 45]}
TEST_PATTERNS = {(CSV19, n) for n in [280, 300, 320, 340, 360, 380]} | {(CSV29, n) for n in [55, 60, 65]}


def verify_pattern_disjoint():
    assert not (TRAIN_PATTERNS & VAL_PATTERNS), "train/val pattern overlap"
    assert not (TRAIN_PATTERNS & TEST_PATTERNS), "train/test pattern overlap"
    assert not (VAL_PATTERNS & TEST_PATTERNS), "val/test pattern overlap"
    return {
        "train_patterns": sorted([f"{c.split('/')[-1]}#{n}" for c, n in TRAIN_PATTERNS]),
        "val_patterns": sorted([f"{c.split('/')[-1]}#{n}" for c, n in VAL_PATTERNS]),
        "test_patterns": sorted([f"{c.split('/')[-1]}#{n}" for c, n in TEST_PATTERNS]),
        "disjoint_verified": True,
    }


# ============================================================
# Core heatmap / peak computation against the EXISTING checkpoint
# ============================================================


def load_model() -> DotHeatmapNet:
    model = DotHeatmapNet()
    model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location="cpu"))
    model.eval()
    return model


def compute_heatmap(model: DotHeatmapNet, binary: np.ndarray) -> tuple[np.ndarray, float, float]:
    h, w = binary.shape
    resized = cv2.resize(binary, (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE), interpolation=cv2.INTER_AREA)
    img_t = torch.from_numpy(resized.astype(np.float32) / 255.0).unsqueeze(0).unsqueeze(0)
    with torch.no_grad():
        logits = model(img_t)
    heatmap = torch.sigmoid(logits)[0, 0].numpy()
    fx, fy = w / MODEL_INPUT_SIZE, h / MODEL_INPUT_SIZE
    return heatmap, fx, fy


def heatmap_level_stats(heatmap: np.ndarray) -> dict:
    argmax_rc = np.unravel_index(int(np.argmax(heatmap)), heatmap.shape)
    return {
        "mean": float(heatmap.mean()), "std": float(heatmap.std()),
        "min": float(heatmap.min()), "max": float(heatmap.max()),
        "n_cells_above_0.2": int((heatmap > 0.2).sum()),
        "n_cells_above_0.4": int((heatmap > 0.4).sum()),
        "n_cells_above_0.6": int((heatmap > 0.6).sum()),
        "n_cells_total": int(heatmap.size),
        "argmax_row_col": [int(argmax_rc[0]), int(argmax_rc[1])],
    }


def match_peaks(pred_px: np.ndarray, gt_px: np.ndarray, tol: float = MATCH_TOLERANCE_PX) -> dict:
    """Symmetric nearest-neighbor matching, same convention used
    throughout M4.1 (classical_baseline._match_metrics), but returns
    more diagnostic detail: which points matched, unmatched counts,
    nearest-distance statistics for BOTH directions."""
    n_pred, n_gt = len(pred_px), len(gt_px)
    if n_gt == 0:
        return {"precision": (0.0 if n_pred > 0 else 1.0), "recall": None, "f1": None,
                "n_predicted": n_pred, "n_ground_truth": 0, "n_matched": 0,
                "n_unmatched_predicted": n_pred, "n_unmatched_ground_truth": 0,
                "nearest_gt_distance_stats": None}
    if n_pred == 0:
        return {"precision": 1.0, "recall": 0.0, "f1": 0.0,
                "n_predicted": 0, "n_ground_truth": n_gt, "n_matched": 0,
                "n_unmatched_predicted": 0, "n_unmatched_ground_truth": n_gt,
                "nearest_gt_distance_stats": None}

    tree_gt = cKDTree(gt_px)
    d_pred_to_gt, _ = tree_gt.query(pred_px)
    tp_mask = d_pred_to_gt < tol
    n_tp = int(tp_mask.sum())

    tree_pred = cKDTree(pred_px)
    d_gt_to_pred, _ = tree_pred.query(gt_px)
    n_gt_matched = int((d_gt_to_pred < tol).sum())

    precision = n_tp / n_pred
    recall = n_gt_matched / n_gt
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision, "recall": recall, "f1": f1,
        "n_predicted": n_pred, "n_ground_truth": n_gt, "n_matched": n_tp,
        "n_unmatched_predicted": n_pred - n_tp, "n_unmatched_ground_truth": n_gt - n_gt_matched,
        "nearest_gt_distance_stats": {
            "mean_px": float(d_pred_to_gt.mean()), "median_px": float(np.median(d_pred_to_gt)),
            "min_px": float(d_pred_to_gt.min()), "max_px": float(d_pred_to_gt.max()),
        },
    }


def deskew_gt_positions(image_path: str, gt_pixel_positions: list, rotation_deg: float, w: int, h: int) -> np.ndarray:
    M = cv2.getRotationMatrix2D((w / 2, h / 2), rotation_deg, 1.0)
    gt_arr = np.array(gt_pixel_positions, dtype=np.float32)
    return cv2.transform(gt_arr.reshape(-1, 1, 2), M).reshape(-1, 2)


def process_image(model, image_path: str, group: str, gt_pixel_positions=None,
                   human_estimate=None) -> tuple[dict, np.ndarray, np.ndarray | None, list, np.ndarray | None]:
    preprocessed = image_io.preprocess(image_path)
    binary = preprocessed.binary
    h, w = binary.shape
    heatmap, fx, fy = compute_heatmap(model, binary)

    result = {
        "file": os.path.basename(image_path), "group": group,
        "width": w, "height": h,
        "heatmap_stats": heatmap_level_stats(heatmap),
    }

    gt_px_deskewed = None
    gt_heatmap = None
    if gt_pixel_positions is not None:
        gt_px_deskewed = deskew_gt_positions(image_path, gt_pixel_positions, preprocessed.rotation_deg, w, h)
        result["n_ground_truth_dots"] = len(gt_px_deskewed)
        gt_hs = [(gx / fx / STRIDE, gy / fy / STRIDE) for gx, gy in gt_px_deskewed]
        gt_heatmap = make_gaussian_heatmap(gt_hs, HEATMAP_SIZE, HEATMAP_SIZE).numpy()
        result["heatmap_mse_vs_ground_truth"] = float(np.mean((heatmap - gt_heatmap) ** 2))
    else:
        result["n_ground_truth_dots"] = None
        result["heatmap_mse_vs_ground_truth"] = None
        result["human_estimate"] = human_estimate

    n_before_nms = int((heatmap > CONFIDENCE_THRESHOLD).sum())
    peaks_hs, confidences = detect_peaks(heatmap, threshold=CONFIDENCE_THRESHOLD,
                                          min_distance_px=MIN_PEAK_DISTANCE_HEATMAP_CELLS)
    pred_px = [(hx * STRIDE * fx, hy * STRIDE * fy) for (hy, hx) in peaks_hs]

    result["peak_stats"] = {
        "n_before_nms_raw_cells_above_threshold": n_before_nms,
        "n_after_nms": len(pred_px),
        "confidence_mean": float(np.mean(confidences)) if confidences else None,
        "confidence_min": float(np.min(confidences)) if confidences else None,
        "confidence_max": float(np.max(confidences)) if confidences else None,
        "predicted_peak_pixel_positions": [[float(x), float(y)] for x, y in pred_px],
    }

    if gt_px_deskewed is not None:
        result["match"] = match_peaks(
            np.array(pred_px) if pred_px else np.empty((0, 2)), gt_px_deskewed
        )

    return result, heatmap, gt_heatmap, pred_px, gt_px_deskewed


# ============================================================
# Visualization
# ============================================================


def save_diagnostic_figure(image_path, heatmap, gt_heatmap, pred_px, gt_px, out_path, title):
    orig = cv2.cvtColor(cv2.imread(image_path), cv2.COLOR_BGR2RGB)
    n_panels = 6
    fig, axes = plt.subplots(1, n_panels, figsize=(4 * n_panels, 4))
    fig.suptitle(title, fontsize=10)

    axes[0].imshow(orig)
    axes[0].set_title("original")
    axes[0].axis("off")

    if gt_heatmap is not None:
        axes[1].imshow(gt_heatmap, cmap="hot", vmin=0, vmax=1)
        axes[1].set_title("ground-truth heatmap")
    else:
        axes[1].text(0.5, 0.5, "no ground truth\navailable", ha="center", va="center")
    axes[1].axis("off")

    axes[2].imshow(heatmap, cmap="hot", vmin=0, vmax=1)
    axes[2].set_title(f"predicted heatmap\n(max={heatmap.max():.2f})")
    axes[2].axis("off")

    h, w = orig.shape[:2]
    heatmap_upscaled = cv2.resize(heatmap, (w, h), interpolation=cv2.INTER_LINEAR)
    axes[3].imshow(orig)
    axes[3].imshow(heatmap_upscaled, cmap="hot", alpha=0.5, vmin=0, vmax=1)
    axes[3].set_title("overlay")
    axes[3].axis("off")

    axes[4].imshow(orig)
    if gt_px is not None and len(gt_px) > 0:
        axes[4].scatter(gt_px[:, 0], gt_px[:, 1], c="lime", marker="o", s=30, label="ground truth", edgecolors="black")
    if pred_px:
        pred_arr = np.array(pred_px)
        axes[4].scatter(pred_arr[:, 0], pred_arr[:, 1], c="red", marker="x", s=40, label="predicted")
    axes[4].set_title(f"gt vs predicted\n(gt={len(gt_px) if gt_px is not None else '?'}, pred={len(pred_px)})")
    axes[4].legend(loc="upper right", fontsize=6)
    axes[4].axis("off")

    if gt_heatmap is not None:
        diff = heatmap - gt_heatmap
        vmax = max(abs(diff.min()), abs(diff.max()), 1e-6)
        im = axes[5].imshow(diff, cmap="coolwarm", vmin=-vmax, vmax=vmax)
        axes[5].set_title("diff (pred - gt)")
        plt.colorbar(im, ax=axes[5], fraction=0.046)
    else:
        axes[5].text(0.5, 0.5, "no ground truth\navailable", ha="center", va="center")
    axes[5].axis("off")

    plt.tight_layout()
    plt.savefig(out_path, dpi=100)
    plt.close(fig)


# ============================================================
# Peak-detector ablation (existing peak_detect.py, NOT modified --
# only its EXISTING parameters are swept)
# ============================================================


def run_ablation(cached_heatmaps: list[tuple[np.ndarray, float, float, np.ndarray]]) -> list[dict]:
    """cached_heatmaps: list of (heatmap, fx, fy, gt_px_deskewed) tuples,
    precomputed once so the CNN forward pass is never re-run during the
    sweep -- only detect_peaks (existing, unmodified) is re-invoked per
    parameter combination."""
    thresholds = [0.2, 0.3, 0.4, 0.5, 0.6]
    min_distances = [1.0, 1.5, 2.0, 2.5, 3.5]

    table = []
    for threshold in thresholds:
        for min_distance in min_distances:
            precisions, recalls, f1s, n_peaks = [], [], [], []
            for heatmap, fx, fy, gt_px in cached_heatmaps:
                peaks_hs, _ = detect_peaks(heatmap, threshold=threshold, min_distance_px=min_distance)
                pred_px = np.array([(hx * STRIDE * fx, hy * STRIDE * fy) for (hy, hx) in peaks_hs]) \
                    if peaks_hs else np.empty((0, 2))
                n_peaks.append(len(pred_px))
                if gt_px is not None and len(gt_px) > 0:
                    m = match_peaks(pred_px, gt_px)
                    precisions.append(m["precision"])
                    if m["recall"] is not None:
                        recalls.append(m["recall"])
                    if m["f1"] is not None:
                        f1s.append(m["f1"])
            table.append({
                "confidence_threshold": threshold,
                "min_distance_heatmap_cells": min_distance,
                "is_current_adapter_config": (threshold == CONFIDENCE_THRESHOLD
                                               and min_distance == MIN_PEAK_DISTANCE_HEATMAP_CELLS),
                "mean_precision": float(np.mean(precisions)) if precisions else None,
                "mean_recall": float(np.mean(recalls)) if recalls else None,
                "mean_f1": float(np.mean(f1s)) if f1s else None,
                "avg_peaks_per_image": float(np.mean(n_peaks)) if n_peaks else None,
            })
    return table


# ============================================================
# Real no-dot false-positive analysis
# ============================================================


def analyze_no_dot_false_positives(no_dot_results: list[dict], no_dot_heatmaps: list[np.ndarray]) -> dict:
    all_peak_positions_normalized = []  # (col/HEATMAP_SIZE, row/HEATMAP_SIZE) per image's peaks
    for r in no_dot_results:
        for (px, py) in r["peak_stats"]["predicted_peak_pixel_positions"]:
            all_peak_positions_normalized.append((px / r["width"], py / r["height"]))

    argmax_positions_normalized = [
        (r["heatmap_stats"]["argmax_row_col"][1] / HEATMAP_SIZE, r["heatmap_stats"]["argmax_row_col"][0] / HEATMAP_SIZE)
        for r in no_dot_results
    ]

    # pairwise heatmap similarity across DIFFERENT no-dot images -- high
    # similarity suggests a generic learned artifact rather than
    # image-specific dot detection
    sims = []
    for i in range(len(no_dot_heatmaps)):
        for j in range(i + 1, len(no_dot_heatmaps)):
            a, b = no_dot_heatmaps[i].flatten(), no_dot_heatmaps[j].flatten()
            denom = (np.linalg.norm(a) * np.linalg.norm(b))
            sims.append(float(np.dot(a, b) / denom) if denom > 0 else 0.0)

    pos_arr = np.array(argmax_positions_normalized)
    return {
        "n_no_dot_images_analyzed": len(no_dot_results),
        "n_images_with_false_positive_peaks": sum(1 for r in no_dot_results if r["peak_stats"]["n_after_nms"] > 0),
        "mean_peaks_per_image": float(np.mean([r["peak_stats"]["n_after_nms"] for r in no_dot_results])),
        "argmax_position_normalized_mean": [float(pos_arr[:, 0].mean()), float(pos_arr[:, 1].mean())],
        "argmax_position_normalized_std": [float(pos_arr[:, 0].std()), float(pos_arr[:, 1].std())],
        "pairwise_heatmap_cosine_similarity_mean": float(np.mean(sims)) if sims else None,
        "pairwise_heatmap_cosine_similarity_min": float(np.min(sims)) if sims else None,
        "pairwise_heatmap_cosine_similarity_max": float(np.max(sims)) if sims else None,
        "interpretation_note": (
            "High mean pairwise cosine similarity (close to 1.0) across structurally "
            "different no-dot photos, combined with low argmax-position std (the "
            "activation peak lands in nearly the same normalized location regardless "
            "of image content), is evidence the model learned a generic/positional "
            "artifact rather than image-specific dot features. Low similarity + high "
            "positional variance would instead suggest content-dependent (if still "
            "wrong) activations."
        ),
    }


def main():
    os.makedirs(VIZ_DIR, exist_ok=True)
    print("Verifying pattern-disjoint split...")
    split_check = verify_pattern_disjoint()
    print("  OK:", split_check["disjoint_verified"])

    print("Loading checkpoint (no retraining)...")
    model = load_model()

    all_results = {"groups": {}}

    # ---- Group 1: synthetic train + val (data the model was optimized on / selected on) ----
    train_json_paths = sorted(glob.glob(os.path.join(M4_1_DATA_DIR, "train", "*.json")))
    val_json_paths = sorted(glob.glob(os.path.join(M4_1_DATA_DIR, "val", "*.json")))
    group1_paths = [(p, "train") for p in train_json_paths] + [(p, "val") for p in val_json_paths]
    print(f"Group 1 (train+val, {len(group1_paths)} images)...")
    group1_results = []
    viz_count = 0
    for json_path, subgroup in group1_paths:
        with open(json_path) as f:
            gt = json.load(f)
        img_path = gt["image_path"]
        gt_positions = list(gt["dot_pixel_positions"].values())
        result, heatmap, gt_heatmap, pred_px, gt_px = process_image(model, img_path, f"synthetic_{subgroup}", gt_positions)
        group1_results.append(result)
        if viz_count < 3:
            save_diagnostic_figure(img_path, heatmap, gt_heatmap, pred_px, gt_px,
                                    os.path.join(VIZ_DIR, f"group1_{result['file']}.png"), f"Group1 (train/val): {result['file']}")
            viz_count += 1
    all_results["groups"]["synthetic_train_val"] = group1_results

    # ---- Group 2: synthetic held-out test (true generalization set) ----
    group2_paths = sorted(glob.glob(os.path.join(M4_1_DATA_DIR, "test", "*.json")))
    print(f"Group 2 (held-out test, {len(group2_paths)} images)...")
    group2_results = []
    group2_cache = []  # (heatmap, fx, fy, gt_px) for the ablation
    viz_count = 0
    for json_path in group2_paths:
        with open(json_path) as f:
            gt = json.load(f)
        img_path = gt["image_path"]
        gt_positions = list(gt["dot_pixel_positions"].values())
        result, heatmap, gt_heatmap, pred_px, gt_px = process_image(model, img_path, "synthetic_heldout_test", gt_positions)
        group2_results.append(result)
        preprocessed = image_io.preprocess(img_path)
        h, w = preprocessed.binary.shape
        fx, fy = w / MODEL_INPUT_SIZE, h / MODEL_INPUT_SIZE
        group2_cache.append((heatmap, fx, fy, gt_px))
        if viz_count < 4:
            save_diagnostic_figure(img_path, heatmap, gt_heatmap, pred_px, gt_px,
                                    os.path.join(VIZ_DIR, f"group2_{result['file']}.png"), f"Group2 (held-out test): {result['file']}")
            viz_count += 1
    all_results["groups"]["synthetic_heldout_test"] = group2_results

    # ---- Group 3: real in-scope photos ----
    print("Group 3 (4 real in-scope photos)...")
    group3_results = []
    for fname in sorted(REAL_INSCOPE):
        img_path = os.path.join(REAL_DIR, fname)
        result, heatmap, gt_heatmap, pred_px, gt_px = process_image(
            model, img_path, "real_in_scope", gt_pixel_positions=None,
            human_estimate=REAL_INSCOPE_ESTIMATES.get(fname),
        )
        group3_results.append(result)
        save_diagnostic_figure(img_path, heatmap, None, pred_px, None,
                                os.path.join(VIZ_DIR, f"group3_{result['file']}.png"), f"Group3 (real in-scope): {result['file']}")
    all_results["groups"]["real_in_scope"] = group3_results

    # ---- Group 4: real NO_VISIBLE_DOT_MARKERS photos (all 18 for stats, first few visualized) ----
    all_real = sorted(glob.glob(os.path.join(REAL_DIR, "*.jpg")))
    no_dot_files = [os.path.basename(p) for p in all_real
                    if os.path.basename(p) not in REAL_EXCLUDED and os.path.basename(p) not in REAL_INSCOPE]
    print(f"Group 4 ({len(no_dot_files)} real NO_VISIBLE_DOT_MARKERS photos)...")
    group4_results = []
    group4_heatmaps = []
    viz_count = 0
    for fname in no_dot_files:
        img_path = os.path.join(REAL_DIR, fname)
        result, heatmap, gt_heatmap, pred_px, gt_px = process_image(
            model, img_path, "real_no_dot_markers", gt_pixel_positions=None,
        )
        group4_results.append(result)
        group4_heatmaps.append(heatmap)
        if viz_count < 4:
            save_diagnostic_figure(img_path, heatmap, None, pred_px, None,
                                    os.path.join(VIZ_DIR, f"group4_{result['file']}.png"), f"Group4 (no dot markers): {result['file']}")
            viz_count += 1
    all_results["groups"]["real_no_visible_dot_markers"] = group4_results

    # ---- Peak-detector ablation on Group 2 (the decisive held-out set) ----
    print("Running peak-detector ablation on held-out test set...")
    ablation_table = run_ablation(group2_cache)
    all_results["peak_detector_ablation"] = {
        "evaluated_on": "synthetic_heldout_test (group 2)",
        "current_adapter_config": {"confidence_threshold": CONFIDENCE_THRESHOLD,
                                    "min_distance_heatmap_cells": MIN_PEAK_DISTANCE_HEATMAP_CELLS},
        "sweep": ablation_table,
    }

    # ---- No-dot false-positive analysis ----
    print("Analyzing real no-dot false positives...")
    all_results["no_dot_false_positive_analysis"] = analyze_no_dot_false_positives(group4_results, group4_heatmaps)

    all_results["pattern_disjoint_check"] = split_check

    os.makedirs(DIAG_DIR, exist_ok=True)
    with open(RESULTS_JSON, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nWrote {RESULTS_JSON}")
    print(f"Wrote visualizations to {VIZ_DIR}/")


if __name__ == "__main__":
    main()
