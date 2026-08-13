"""M4.1 Phase 7: classical vs. learned detector, on IDENTICAL evaluation
sets, metrics kept separate (never blended into one "accuracy" number),
per docs/M4_EVALUATION_PROTOCOL.md.

Evaluation sets used (all disjoint from the learned model's TRAIN
patterns -- see generate_training_data.py's docstring for the exact
disjointness argument):
  - m4_1_val:      experiments/m4_1/data/val/  (used for checkpoint
                    selection during training -- NOT a clean held-out
                    set for the learned model; reported but labeled as
                    such, never presented as the headline number)
  - m4_1_test:      experiments/m4_1/data/test/ (genuinely held out from
                    BOTH training and checkpoint selection -- the
                    primary comparison set)
  - synthetic_tuned / synthetic_heldout: the ORIGINAL classical-baseline
                    sets (synthetic_photos/, synthetic_photos_heldout/)
                    -- different rendering style (gsp.degrade, not
                    degrade_v2), never touched by the learned model's
                    training OR checkpoint selection at all -- a second,
                    independent generalization check.

CONFIDENCE_THRESHOLD and MIN_PEAK_DISTANCE_PX (ml_lattice_detector.py)
were fixed BEFORE this script was ever run against m4_1_test or the
synthetic_heldout sets -- not tuned against them, per the task's
explicit "do not tune thresholds on the held-out test set" rule.
"""

from __future__ import annotations

import glob
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from engine import image_io  # noqa: E402
from experiments.m4_1.classical_baseline import _match_metrics, _deskewed_gt_pixels, MATCH_TOLERANCE_PX  # noqa: E402
from experiments.m4_1.ml_lattice_detector import LearnedLatticeDetector, MalformedOutputError  # noqa: E402

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results", "comparison.json")

EVAL_SETS = {
    "m4_1_val": os.path.join(os.path.dirname(__file__), "data", "val"),
    "m4_1_test": os.path.join(os.path.dirname(__file__), "data", "test"),
    "synthetic_tuned": "synthetic_photos",
    "synthetic_heldout": "synthetic_photos_heldout",
}


def _eval_one_detector(directory: str, detector_name: str, detector_fn) -> list[dict]:
    rows = []
    for json_path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        stem = os.path.splitext(os.path.basename(json_path))[0]
        img_path = os.path.join(directory, f"{stem}.jpg")
        with open(json_path) as f:
            gt = json.load(f)

        preprocessed = image_io.preprocess(img_path)
        gray_mean = float(cv2.cvtColor(cv2.imread(img_path), cv2.COLOR_BGR2GRAY).mean())

        try:
            lattice = detector_fn(preprocessed)
            crashed = False
            crash_type = None
        except (MalformedOutputError, Exception) as e:  # noqa: BLE001
            lattice = None
            crashed = True
            crash_type = type(e).__name__

        row = {"stem": stem, "detector": detector_name, "gray_mean": gray_mean, "crashed": crashed}
        if crashed:
            row["crash_type"] = crash_type
            row.update(precision=0.0, recall=0.0, f1=0.0, mean_localization_error_px=None,
                       n_detected=0, n_ground_truth=len(gt["dot_pixel_positions"]), n_matched=0)
        else:
            det_px = np.array(lattice.pixel_positions) if lattice.pixel_positions else np.empty((0, 2))
            gt_px = _deskewed_gt_pixels(img_path, gt, preprocessed)
            metrics = _match_metrics(det_px, gt_px, MATCH_TOLERANCE_PX)
            row.update(metrics)

        rows.append(row)
    return rows


def _aggregate(rows: list[dict], gray_mean_max: float | None = None) -> dict:
    subset = [r for r in rows if gray_mean_max is None or r["gray_mean"] < gray_mean_max]
    if not subset:
        return {"n_images": 0}
    return {
        "n_images": len(subset),
        "mean_recall": float(np.mean([r["recall"] for r in subset])),
        "mean_precision": float(np.mean([r["precision"] for r in subset])),
        "mean_localization_error_px": float(np.mean(
            [r["mean_localization_error_px"] for r in subset if r["mean_localization_error_px"] is not None]
        )) if any(r["mean_localization_error_px"] is not None for r in subset) else None,
        "n_crashed": sum(1 for r in subset if r["crashed"]),
    }


def main():
    classical_detector = image_io.detect_lattice
    print("Loading learned detector...")
    learned_detector = LearnedLatticeDetector()

    results = {"localization_tolerance_px": MATCH_TOLERANCE_PX, "sets": {}}

    for set_name, directory in EVAL_SETS.items():
        if not os.path.isdir(directory) or not glob.glob(os.path.join(directory, "*.json")):
            print(f"skipping {set_name} ({directory}): no ground-truth JSON found")
            continue
        print(f"Evaluating {set_name}...")
        classical_rows = _eval_one_detector(directory, "classical", classical_detector)
        learned_rows = _eval_one_detector(directory, "learned", learned_detector)

        results["sets"][set_name] = {
            "classical": {
                "per_image": classical_rows,
                "aggregate_all": _aggregate(classical_rows),
                "aggregate_low_contrast_only_gray_mean_lt_100": _aggregate(classical_rows, gray_mean_max=100),
            },
            "learned": {
                "per_image": learned_rows,
                "aggregate_all": _aggregate(learned_rows),
                "aggregate_low_contrast_only_gray_mean_lt_100": _aggregate(learned_rows, gray_mean_max=100),
            },
        }
        print(f"  classical: {results['sets'][set_name]['classical']['aggregate_all']}")
        print(f"  learned:   {results['sets'][set_name]['learned']['aggregate_all']}")
        print(f"  classical (gray_mean<100): {results['sets'][set_name]['classical']['aggregate_low_contrast_only_gray_mean_lt_100']}")
        print(f"  learned   (gray_mean<100): {results['sets'][set_name]['learned']['aggregate_low_contrast_only_gray_mean_lt_100']}")

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
