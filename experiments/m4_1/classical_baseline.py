"""M4.1 Phase 2: classical baseline. Runs the EXISTING, unmodified
engine.image_io detector (engine.image_io.preprocess + detect_lattice +
trace_path) against the four separate populations the task requires be
kept apart:

  1. synthetic TUNED   (synthetic_photos/)          -- pixel-exact ground truth
  2. synthetic HELD-OUT (synthetic_photos_heldout/)  -- pixel-exact ground truth
  3. real IN-SCOPE      (real_photos/, 4 files)      -- NO pixel-exact ground
                                                         truth; only a rough,
                                                         explicitly-uncertain
                                                         human count estimate
                                                         for some images (see
                                                         REAL_INSCOPE_ESTIMATES)
  4. real NO_VISIBLE_DOT_MARKERS (real_photos/, 18 files) -- recall is
     UNDEFINED here (no real dots exist) and is never computed; only
     false-positive-relevant raw detection counts are reported.

This script does not modify engine/image_io.py, does not train anything,
and does not fabricate ground truth for images that don't have any --
per PULLI's standing "do not fabricate ground truth" rule (see
PROJECT_STATE.md, docs/M4_EVALUATION_PROTOCOL.md).

Localization tolerance is 6.0px, matching the existing convention in
tests/test_image_io.py (MATCH_TOLERANCE_PX) -- not re-invented here.
"""

from __future__ import annotations

import glob
import json
import os
import sys

import cv2
import numpy as np
from scipy.spatial import cKDTree

# Allow running as `python experiments/m4_1/classical_baseline.py` from the
# repo root without needing an installed package -- repo root is 2 levels
# up from this file, same pattern the rest of experiments/m4_1/ will use.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from engine import image_io, motifs, validity

MATCH_TOLERANCE_PX = 6.0

SYNTH_DIR = "synthetic_photos"
HELDOUT_DIR = "synthetic_photos_heldout"
REAL_DIR = "real_photos"
RESULTS_PATH = "experiments/m4_1/results/classical_baseline.json"

# Confirmed-excluded (digital rendering, not a photograph) -- see
# real_photos/MANIFEST.md's exclusion note. Never evaluated.
REAL_EXCLUDED = {"ithayakkamalam_pulli_mayooranathan.jpg"}

# Visually classified this session/prior session by direct human inspection
# (Read tool), NOT inferred from detector output -- see PROJECT_STATE.md
# Section 3/4. Every real photo not listed here as in-scope is
# NO_VISIBLE_DOT_MARKERS.
REAL_INSCOPE = {"kolam2_tshrinivasan.jpg", "kolam_attur1_infofarmer.jpg",
                "kolam_naduveetu_meenakshisundaram.jpg", "muggu_kollam_sirensongs.jpg"}

# Rough, explicitly-uncertain human eyeball estimates for in-scope real
# photos. NOT pixel-exact ground truth -- see docs/M4_EVALUATION_PROTOCOL.md
# Section 1 Tier B ("mark it appropriately rather than inventing
# coordinates"). Every entry states its own uncertainty; used ONLY for a
# rough sanity comparison against detector counts, never for precision/
# recall computation (that requires per-dot position matching, which these
# estimates cannot support).
REAL_INSCOPE_ESTIMATES = {
    "kolam2_tshrinivasan.jpg": {
        "estimate": "25-30", "confidence": "low",
        "note": "blurry low-light photo, eyeballed, not precisely countable",
    },
    "kolam_attur1_infofarmer.jpg": {
        "estimate": "~4 clearly visible (pinwheel centers)", "confidence": "low",
        "note": ("re-inspected this session: only 4 large maroon dots clearly "
                 "visible at the 4 outer pinwheel centers; detector found 12 -- "
                 "this DISCREPANCY is reported, not resolved. Possible causes "
                 "(not determined): additional small dots not resolvable at "
                 "this image resolution, OR detector false positives that "
                 "happened to fit a plausible lattice geometry. Do not treat "
                 "the detector's 12/12 'lattice fit succeeded' as a validated "
                 "clean match against true dot count."),
    },
    "kolam_naduveetu_meenakshisundaram.jpg": {
        "estimate": "~100-150 (dense grid)", "confidence": "very low",
        "note": "dense kambi-kolam grid, individual dots not reliably countable at available resolution/glare",
    },
    "muggu_kollam_sirensongs.jpg": {
        "estimate": "~20-30 (visible diamond motif only)", "confidence": "low",
        "note": "photo shows kolam partially, compressed/distant view",
    },
}


def _match_metrics(det_px: np.ndarray, gt_px: np.ndarray, tol: float) -> dict:
    """Symmetric nearest-neighbor matching at `tol` px, same convention as
    tests/test_image_io.py. Returns precision/recall/F1/mean localization
    error over matched pairs."""
    if len(det_px) == 0 and len(gt_px) == 0:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "mean_localization_error_px": 0.0,
                "n_detected": 0, "n_ground_truth": 0, "n_matched": 0}
    if len(det_px) == 0:
        return {"precision": 1.0, "recall": 0.0, "f1": 0.0, "mean_localization_error_px": None,
                "n_detected": 0, "n_ground_truth": len(gt_px), "n_matched": 0}
    if len(gt_px) == 0:
        return {"precision": 0.0, "recall": 1.0, "f1": 0.0, "mean_localization_error_px": None,
                "n_detected": len(det_px), "n_ground_truth": 0, "n_matched": 0}

    tree_gt = cKDTree(gt_px)
    d_det_to_gt, _ = tree_gt.query(det_px)
    tp_mask = d_det_to_gt < tol
    n_tp = int(tp_mask.sum())

    tree_det = cKDTree(det_px)
    d_gt_to_det, _ = tree_det.query(gt_px)
    n_gt_matched = int((d_gt_to_det < tol).sum())

    precision = n_tp / len(det_px)
    recall = n_gt_matched / len(gt_px)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    mean_err = float(d_det_to_gt[tp_mask].mean()) if n_tp > 0 else None

    return {"precision": precision, "recall": recall, "f1": f1,
            "mean_localization_error_px": mean_err,
            "n_detected": len(det_px), "n_ground_truth": len(gt_px), "n_matched": n_tp}


def _deskewed_gt_pixels(img_path: str, gt: dict, preprocessed: image_io.Preprocessed) -> np.ndarray:
    gt_px = np.array(list(gt["dot_pixel_positions"].values()), dtype=np.float32)
    img = cv2.imread(img_path)
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), preprocessed.rotation_deg, 1.0)
    return cv2.transform(gt_px.reshape(-1, 1, 2), M).reshape(-1, 2)


def eval_synthetic_dir(directory: str) -> list[dict]:
    rows = []
    for json_path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        stem = os.path.splitext(os.path.basename(json_path))[0]
        img_path = os.path.join(directory, f"{stem}.jpg")
        with open(json_path) as f:
            gt = json.load(f)

        preprocessed = image_io.preprocess(img_path)
        lattice = image_io.detect_lattice(preprocessed)
        det_px = np.array(lattice.pixel_positions) if lattice.pixel_positions else np.empty((0, 2))
        gt_px = _deskewed_gt_pixels(img_path, gt, preprocessed)

        metrics = _match_metrics(det_px, gt_px, MATCH_TOLERANCE_PX)

        row = {"stem": stem, "n_lattice_coords": len(lattice.lattice_coords), **metrics}

        try:
            edges = image_io.trace_path(preprocessed, lattice)
            G_nodes = lattice.lattice_coords
            row["trace_path_crash"] = False
            row["n_traced_edges"] = len(edges)
            row["n_lattice_nodes"] = len(G_nodes)
        except Exception as e:  # noqa: BLE001
            row["trace_path_crash"] = True
            row["trace_path_crash_type"] = type(e).__name__

        rows.append(row)
    return rows


def eval_real_photos() -> dict:
    inscope_rows = []
    no_dot_rows = []
    for path in sorted(glob.glob(os.path.join(REAL_DIR, "*.jpg"))):
        fname = os.path.basename(path)
        if fname in REAL_EXCLUDED:
            continue

        preprocessed = image_io.preprocess(path)
        try:
            lattice = image_io.detect_lattice(preprocessed)
        except Exception as e:  # noqa: BLE001
            row = {"file": fname, "detect_lattice_crash": True, "crash_type": type(e).__name__}
            (inscope_rows if fname in REAL_INSCOPE else no_dot_rows).append(row)
            continue

        row = {
            "file": fname,
            "n_pixel_detections": len(lattice.pixel_positions),
            "n_lattice_coords": len(lattice.lattice_coords),
            "detect_lattice_crash": False,
        }

        try:
            edges = image_io.trace_path(preprocessed, lattice)
            row["trace_path_crash"] = False
            row["n_traced_edges"] = len(edges)
        except Exception as e:  # noqa: BLE001
            row["trace_path_crash"] = True
            row["trace_path_crash_type"] = type(e).__name__

        if fname in REAL_INSCOPE:
            row["in_scope"] = True
            row["human_estimate"] = REAL_INSCOPE_ESTIMATES.get(fname)
            row["note"] = ("No pixel-exact ground truth exists for this image -- "
                            "precision/recall NOT computed. human_estimate is a rough, "
                            "explicitly-uncertain visual count for qualitative comparison only.")
            inscope_rows.append(row)
        else:
            row["in_scope"] = False
            row["classification"] = "NO_VISIBLE_DOT_MARKERS"
            row["note"] = ("This image has NO real dot markers by design (confirmed by direct "
                            "visual inspection). Any nonzero n_pixel_detections above is a FALSE "
                            "POSITIVE by definition -- recall is undefined and NOT computed for "
                            "this image. Per PROJECT_STATE.md: never treat this as a detector "
                            "'failure' relative to a recall metric.")
            no_dot_rows.append(row)

    n_no_dot_with_false_positives = sum(1 for r in no_dot_rows if r.get("n_pixel_detections", 0) > 0)
    return {
        "in_scope": inscope_rows,
        "no_visible_dot_markers": no_dot_rows,
        "summary": {
            "n_in_scope": len(inscope_rows),
            "n_no_visible_dot_markers": len(no_dot_rows),
            "n_no_visible_dot_markers_with_false_positive_detections": n_no_dot_with_false_positives,
            "false_positive_image_rate_on_no_dot_photos": (
                n_no_dot_with_false_positives / len(no_dot_rows) if no_dot_rows else None
            ),
        },
    }


def _aggregate(rows: list[dict]) -> dict:
    if not rows:
        return {}
    recalls = [r["recall"] for r in rows]
    precisions = [r["precision"] for r in rows]
    errs = [r["mean_localization_error_px"] for r in rows if r.get("mean_localization_error_px") is not None]
    n_crashes = sum(1 for r in rows if r.get("trace_path_crash"))
    return {
        "n_images": len(rows),
        "mean_recall": float(np.mean(recalls)),
        "mean_precision": float(np.mean(precisions)),
        "mean_localization_error_px": float(np.mean(errs)) if errs else None,
        "n_trace_path_crashes": n_crashes,
    }


def main():
    print("Evaluating synthetic TUNED set...")
    tuned_rows = eval_synthetic_dir(SYNTH_DIR)
    print("Evaluating synthetic HELD-OUT set...")
    heldout_rows = eval_synthetic_dir(HELDOUT_DIR)
    print("Evaluating real photographs (in-scope + NO_VISIBLE_DOT_MARKERS)...")
    real_results = eval_real_photos()

    results = {
        "detector": "engine.image_io.detect_lattice (classical, deterministic, unmodified)",
        "localization_tolerance_px": MATCH_TOLERANCE_PX,
        "synthetic_tuned": {"per_image": tuned_rows, "aggregate": _aggregate(tuned_rows)},
        "synthetic_heldout": {"per_image": heldout_rows, "aggregate": _aggregate(heldout_rows)},
        "real_photos": real_results,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nWrote {RESULTS_PATH}")
    print(f"Synthetic tuned:    {results['synthetic_tuned']['aggregate']}")
    print(f"Synthetic held-out: {results['synthetic_heldout']['aggregate']}")
    print(f"Real in-scope:      {len(real_results['in_scope'])} images (see JSON, no aggregate recall -- no ground truth)")
    print(f"Real no-dot:        {real_results['summary']}")


if __name__ == "__main__":
    main()
