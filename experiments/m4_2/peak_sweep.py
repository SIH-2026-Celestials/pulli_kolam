"""M4.2 Phase E: peak-detection parameter sweep, VALIDATION SET ONLY --
never the test set, per the task's explicit rule ("select parameters
using validation data only... do not tune against the final test set").

Reuses experiments/m4_1/peak_detect.py's detect_peaks() UNMODIFIED --
this script only varies the (threshold, min_distance) arguments passed
to it, never its implementation.
"""

from __future__ import annotations

import json
import os
import sys

import cv2
import numpy as np
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from engine import image_io  # noqa: E402
from experiments.m4_1.peak_detect import detect_peaks  # noqa: E402
from experiments.m4_2.model import DotHeatmapNetV2, MODEL_INPUT_SIZE, OUTPUT_STRIDE  # noqa: E402

CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "results", "dot_heatmap_net_v2.pt")
VAL_DIR = os.path.join(os.path.dirname(__file__), "data", "val")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results", "peak_sweep.json")

THRESHOLDS = [0.2, 0.3, 0.4, 0.5, 0.6]
MIN_DISTANCES = [1.0, 1.5, 2.0, 2.5, 3.0]
MATCH_TOLERANCE_PX = 6.0


def _match(pred_px, gt_px, tol=MATCH_TOLERANCE_PX):
    from scipy.spatial import cKDTree
    if len(gt_px) == 0:
        return (0.0 if len(pred_px) else 1.0), None
    if len(pred_px) == 0:
        return 1.0, 0.0
    tree_gt = cKDTree(gt_px)
    d_p, _ = tree_gt.query(pred_px)
    precision = float((d_p < tol).mean())
    tree_p = cKDTree(pred_px)
    d_g, _ = tree_p.query(gt_px)
    recall = float((d_g < tol).mean())
    return precision, recall


def main():
    model = DotHeatmapNetV2()
    model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location="cpu"))
    model.eval()

    cached = []
    for json_path in sorted(__import__("glob").glob(os.path.join(VAL_DIR, "*.json"))):
        with open(json_path) as f:
            gt = json.load(f)
        preprocessed = image_io.preprocess(gt["image_path"])
        binary = preprocessed.binary
        h, w = binary.shape
        resized = cv2.resize(binary, (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE), interpolation=cv2.INTER_AREA)
        img_t = torch.from_numpy(resized.astype(np.float32) / 255.0).unsqueeze(0).unsqueeze(0)
        with torch.no_grad():
            heatmap = torch.sigmoid(model(img_t))[0, 0].numpy()

        M = cv2.getRotationMatrix2D((w / 2, h / 2), preprocessed.rotation_deg, 1.0)
        gt_arr = np.array(list(gt["dot_pixel_positions"].values()), dtype=np.float32)
        gt_px = cv2.transform(gt_arr.reshape(-1, 1, 2), M).reshape(-1, 2)

        cached.append((heatmap, w / MODEL_INPUT_SIZE, h / MODEL_INPUT_SIZE, gt_px))

    table = []
    for threshold in THRESHOLDS:
        for min_distance in MIN_DISTANCES:
            precisions, recalls, n_peaks = [], [], []
            for heatmap, fx, fy, gt_px in cached:
                peaks_hs, _ = detect_peaks(heatmap, threshold=threshold, min_distance_px=min_distance)
                pred_px = np.array([(hx * OUTPUT_STRIDE * fx, hy * OUTPUT_STRIDE * fy) for (hy, hx) in peaks_hs]) \
                    if peaks_hs else np.empty((0, 2))
                p, r = _match(pred_px, gt_px)
                precisions.append(p)
                if r is not None:
                    recalls.append(r)
                n_peaks.append(len(pred_px))
            mean_p = float(np.mean(precisions))
            mean_r = float(np.mean(recalls)) if recalls else None
            f1 = (2 * mean_p * mean_r / (mean_p + mean_r)) if (mean_r and (mean_p + mean_r) > 0) else 0.0
            table.append({
                "confidence_threshold": threshold, "min_distance_heatmap_cells": min_distance,
                "mean_precision": mean_p, "mean_recall": mean_r, "mean_f1": f1,
                "avg_peaks_per_image": float(np.mean(n_peaks)),
            })

    table.sort(key=lambda r: -(r["mean_f1"] or 0))
    with open(RESULTS_PATH, "w") as f:
        json.dump({"evaluated_on": "validation set only (experiments/m4_2/data/val)", "sweep": table}, f, indent=2)

    print(f"{'thresh':>7s} {'min_dist':>9s} {'precision':>10s} {'recall':>7s} {'f1':>6s} {'avg_peaks':>10s}")
    for row in table:
        print(f"{row['confidence_threshold']:7.1f} {row['min_distance_heatmap_cells']:9.1f} "
              f"{row['mean_precision']:10.4f} {row['mean_recall']:7.4f} {row['mean_f1']:6.4f} "
              f"{row['avg_peaks_per_image']:10.1f}")
    print(f"\nBest by F1: {table[0]}")
    print(f"Wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
