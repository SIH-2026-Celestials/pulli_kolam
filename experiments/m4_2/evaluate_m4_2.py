"""M4.2 Phase L: the evaluation gate. Classical vs. ML (M4.2's new
128x128 model), on IDENTICAL sets, honest reporting -- ML becomes the
production default ONLY if this script's numbers support it. If ML
remains worse, classical stays default and this is reported as a valid
result, not tuned away.

Populations, matching the task's required table:
  - synthetic validation (experiments/m4_2/data/val)
  - synthetic held-out test (experiments/m4_2/data/test)
  - real in-scope photos (4, from real_photos/, unchanged since session 12)
  - real no-dot photos (18, same set)

Also measures inference latency for both detectors (task's explicit
requirement), and false positives/image on the no-dot set.
"""

from __future__ import annotations

import glob
import json
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from engine import image_io  # noqa: E402
from experiments.m4_1.classical_baseline import REAL_DIR, REAL_EXCLUDED, REAL_INSCOPE  # noqa: E402
from experiments.m4_2.ml_lattice_detector import LearnedLatticeDetectorV2, MalformedOutputError  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results", "evaluate_m4_2.json")
MATCH_TOLERANCE_PX = 6.0


def _match_metrics(det_px: np.ndarray, gt_px: np.ndarray, tol: float = MATCH_TOLERANCE_PX) -> dict:
    from scipy.spatial import cKDTree
    if len(det_px) == 0 and len(gt_px) == 0:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "n_detected": 0, "n_ground_truth": 0,
                "mean_localization_error_px": 0.0}
    if len(det_px) == 0:
        return {"precision": 1.0, "recall": 0.0, "f1": 0.0, "n_detected": 0, "n_ground_truth": len(gt_px),
                "mean_localization_error_px": None}
    if len(gt_px) == 0:
        return {"precision": 0.0, "recall": 1.0, "f1": 0.0, "n_detected": len(det_px), "n_ground_truth": 0,
                "mean_localization_error_px": None}
    tree_gt = cKDTree(gt_px)
    d_det, _ = tree_gt.query(det_px)
    tp_mask = d_det < tol
    n_tp = int(tp_mask.sum())
    tree_det = cKDTree(det_px)
    d_gt, _ = tree_det.query(gt_px)
    n_gt_matched = int((d_gt < tol).sum())
    precision = n_tp / len(det_px)
    recall = n_gt_matched / len(gt_px)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    mean_err = float(d_det[tp_mask].mean()) if n_tp > 0 else None
    return {"precision": precision, "recall": recall, "f1": f1, "n_detected": len(det_px),
            "n_ground_truth": len(gt_px), "mean_localization_error_px": mean_err}


def _deskewed_gt(image_path: str, gt_positions: list, preprocessed) -> np.ndarray:
    img = cv2.imread(image_path)
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), preprocessed.rotation_deg, 1.0)
    arr = np.array(gt_positions, dtype=np.float32)
    return cv2.transform(arr.reshape(-1, 1, 2), M).reshape(-1, 2)


def eval_synthetic(directory: str, classical_fn, ml_fn) -> dict:
    classical_rows, ml_rows = [], []
    for json_path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        with open(json_path) as f:
            gt = json.load(f)
        img_path = gt["image_path"]
        gt_positions = list(gt["dot_pixel_positions"].values())

        preprocessed = image_io.preprocess(img_path)
        gt_px = _deskewed_gt(img_path, gt_positions, preprocessed)

        t0 = time.monotonic()
        lattice_c = classical_fn(preprocessed)
        t_c = (time.monotonic() - t0) * 1000
        det_c = np.array(lattice_c.pixel_positions) if lattice_c.pixel_positions else np.empty((0, 2))
        row_c = _match_metrics(det_c, gt_px)
        row_c["latency_ms"] = t_c
        classical_rows.append(row_c)

        t0 = time.monotonic()
        try:
            lattice_m = ml_fn(preprocessed)
            t_m = (time.monotonic() - t0) * 1000
            det_m = np.array(lattice_m.pixel_positions) if lattice_m.pixel_positions else np.empty((0, 2))
            row_m = _match_metrics(det_m, gt_px)
            row_m["latency_ms"] = t_m
        except MalformedOutputError as e:
            row_m = {"precision": 0.0, "recall": 0.0, "f1": 0.0, "error": str(e), "latency_ms": None}
        ml_rows.append(row_m)

    return {"classical": _aggregate(classical_rows), "ml": _aggregate(ml_rows)}


def _aggregate(rows: list[dict]) -> dict:
    if not rows:
        return {}
    recalls = [r["recall"] for r in rows if r.get("recall") is not None]
    precisions = [r["precision"] for r in rows if r.get("precision") is not None]
    errs = [r["mean_localization_error_px"] for r in rows if r.get("mean_localization_error_px") is not None]
    lat = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
    f1s = [r["f1"] for r in rows if r.get("f1") is not None]
    return {
        "n_images": len(rows),
        "mean_recall": float(np.mean(recalls)) if recalls else None,
        "mean_precision": float(np.mean(precisions)) if precisions else None,
        "mean_f1": float(np.mean(f1s)) if f1s else None,
        "mean_localization_error_px": float(np.mean(errs)) if errs else None,
        "mean_latency_ms": float(np.mean(lat)) if lat else None,
    }


def eval_real_photos(classical_fn, ml_fn) -> dict:
    inscope_c, inscope_m = [], []
    nodot_c_fp, nodot_m_fp = 0, 0
    nodot_n = 0

    for path in sorted(glob.glob(os.path.join(REAL_DIR, "*.jpg"))):
        fname = os.path.basename(path)
        if fname in REAL_EXCLUDED:
            continue
        preprocessed = image_io.preprocess(path)

        t0 = time.monotonic()
        lattice_c = classical_fn(preprocessed)
        t_c = (time.monotonic() - t0) * 1000
        t0 = time.monotonic()
        try:
            lattice_m = ml_fn(preprocessed)
            t_m = (time.monotonic() - t0) * 1000
            m_count = len(lattice_m.pixel_positions)
        except MalformedOutputError:
            t_m = None
            m_count = 0

        if fname in REAL_INSCOPE:
            inscope_c.append({"file": fname, "n_detected": len(lattice_c.pixel_positions), "latency_ms": t_c})
            inscope_m.append({"file": fname, "n_detected": m_count, "latency_ms": t_m})
        else:
            nodot_n += 1
            if len(lattice_c.pixel_positions) > 0:
                nodot_c_fp += 1
            if m_count > 0:
                nodot_m_fp += 1

    return {
        "real_in_scope": {"classical": inscope_c, "ml": inscope_m},
        "real_no_dot": {
            "n_images": nodot_n,
            "classical_fp_rate": nodot_c_fp / nodot_n if nodot_n else None,
            "ml_fp_rate": nodot_m_fp / nodot_n if nodot_n else None,
        },
    }


def main():
    classical_fn = image_io.detect_lattice
    print("Loading M4.2 ML detector...")
    ml_detector = LearnedLatticeDetectorV2()

    results = {"localization_tolerance_px": MATCH_TOLERANCE_PX, "sets": {}}

    print("Evaluating synthetic validation set...")
    results["sets"]["synthetic_val"] = eval_synthetic(os.path.join(DATA_DIR, "val"), classical_fn, ml_detector)
    print("  classical:", results["sets"]["synthetic_val"]["classical"])
    print("  ml:       ", results["sets"]["synthetic_val"]["ml"])

    print("Evaluating synthetic held-out test set...")
    results["sets"]["synthetic_test"] = eval_synthetic(os.path.join(DATA_DIR, "test"), classical_fn, ml_detector)
    print("  classical:", results["sets"]["synthetic_test"]["classical"])
    print("  ml:       ", results["sets"]["synthetic_test"]["ml"])

    print("Evaluating real photographs...")
    results["real_photos"] = eval_real_photos(classical_fn, ml_detector)
    print("  real_no_dot:", results["real_photos"]["real_no_dot"])

    # ---- decision table ----
    st = results["sets"]["synthetic_test"]
    decision = {
        "ml_beats_classical_on_synthetic_test_recall": (
            (st["ml"]["mean_recall"] or 0) > (st["classical"]["mean_recall"] or 0)
        ),
        "ml_beats_classical_on_synthetic_test_f1": (
            (st["ml"]["mean_f1"] or 0) > (st["classical"]["mean_f1"] or 0)
        ),
        "ml_no_dot_fp_rate_better_or_equal": (
            (results["real_photos"]["real_no_dot"]["ml_fp_rate"] or 1)
            <= (results["real_photos"]["real_no_dot"]["classical_fp_rate"] or 0)
        ),
    }
    decision["recommend_ml_as_default"] = all(decision.values())
    results["decision"] = decision

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 70)
    print(f"{'':20s} {'CLASSICAL':>15s} {'ML':>15s}")
    print("-" * 70)
    for label, key, subkey in [
        ("Synthetic val recall", "synthetic_val", "mean_recall"),
        ("Synthetic val precision", "synthetic_val", "mean_precision"),
        ("Synthetic val F1", "synthetic_val", "mean_f1"),
        ("Synthetic test recall", "synthetic_test", "mean_recall"),
        ("Synthetic test precision", "synthetic_test", "mean_precision"),
        ("Synthetic test F1", "synthetic_test", "mean_f1"),
        ("Localization error (px)", "synthetic_test", "mean_localization_error_px"),
        ("Inference latency (ms)", "synthetic_test", "mean_latency_ms"),
    ]:
        c_val = results["sets"][key]["classical"].get(subkey)
        m_val = results["sets"][key]["ml"].get(subkey)
        c_str = f"{c_val:.4f}" if isinstance(c_val, float) else str(c_val)
        m_str = f"{m_val:.4f}" if isinstance(m_val, float) else str(m_val)
        print(f"{label:20s} {c_str:>15s} {m_str:>15s}")
    print(f"{'No-dot FP rate':20s} {results['real_photos']['real_no_dot']['classical_fp_rate']:>15.4f} "
          f"{results['real_photos']['real_no_dot']['ml_fp_rate']:>15.4f}")
    print("=" * 70)
    print(f"\nDecision: recommend_ml_as_default = {decision['recommend_ml_as_default']}")
    print(f"Wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
