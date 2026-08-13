"""M4.1 Phase 8: learned detector vs. classical detector on the real
photograph corpus, with the 4 in-scope images and 18
NO_VISIBLE_DOT_MARKERS images kept strictly separate -- recall is never
computed against the no-dot images (there is nothing to recall), matching
the same rule enforced in classical_baseline.py and
PROJECT_STATE.md throughout.

No pixel-exact ground truth exists for any real photo (see
docs/M4_EVALUATION_PROTOCOL.md Section 1 Tier B) -- precision/recall
against real photos is NOT computed here either, for the same reason
classical_baseline.py doesn't compute it. What IS reported per in-scope
image: detector output count for both detectors side by side, the
existing rough human count estimate (REAL_INSCOPE_ESTIMATES, unchanged
from classical_baseline.py), and an explicit failure_reason field.
"""

from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from engine import image_io  # noqa: E402
from experiments.m4_1.classical_baseline import (  # noqa: E402
    REAL_DIR, REAL_EXCLUDED, REAL_INSCOPE, REAL_INSCOPE_ESTIMATES,
)
from experiments.m4_1.ml_lattice_detector import LearnedLatticeDetector, MalformedOutputError  # noqa: E402

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results", "real_photo_comparison.json")


def _run_detector(detector_fn, preprocessed) -> dict:
    try:
        lattice = detector_fn(preprocessed)
        return {"crashed": False, "n_pixel_detections": len(lattice.pixel_positions),
                "n_lattice_coords": len(lattice.lattice_coords)}
    except (MalformedOutputError, Exception) as e:  # noqa: BLE001
        return {"crashed": True, "crash_type": type(e).__name__, "n_pixel_detections": None, "n_lattice_coords": None}


def _failure_reason(fname: str, in_scope: bool, classical: dict, learned: dict) -> str:
    if not in_scope:
        if (classical.get("n_pixel_detections") or 0) > 0 or (learned.get("n_pixel_detections") or 0) > 0:
            return "N/A_NO_DOTS -- any detections here are false positives by definition, not a failure to recall"
        return "N/A_NO_DOTS -- correctly found nothing"
    if classical["crashed"] or learned["crashed"]:
        return "DETECTOR_CRASH -- see crash_type"
    if (classical.get("n_pixel_detections") or 0) == 0 and (learned.get("n_pixel_detections") or 0) == 0:
        return "BOTH_DETECTORS_FOUND_ZERO_DOTS despite dots being visually confirmed present"
    return "SEE_HUMAN_ESTIMATE -- no pixel-exact ground truth to compute a precise failure mode"


def main():
    print("Loading learned detector...")
    learned_detector = LearnedLatticeDetector()
    classical_detector = image_io.detect_lattice

    in_scope_rows = []
    no_dot_rows = []

    for path in sorted(glob.glob(os.path.join(REAL_DIR, "*.jpg"))):
        fname = os.path.basename(path)
        if fname in REAL_EXCLUDED:
            continue
        in_scope = fname in REAL_INSCOPE

        preprocessed = image_io.preprocess(path)
        classical_result = _run_detector(classical_detector, preprocessed)
        learned_result = _run_detector(learned_detector, preprocessed)

        row = {
            "file": fname,
            "in_scope": in_scope,
            "classification": "IN_SCOPE_VISIBLE_DOTS" if in_scope else "NO_VISIBLE_DOT_MARKERS",
            "classical_detector": classical_result,
            "learned_detector": learned_result,
            "human_estimate": REAL_INSCOPE_ESTIMATES.get(fname) if in_scope else None,
            "failure_reason": _failure_reason(fname, in_scope, classical_result, learned_result),
        }
        (in_scope_rows if in_scope else no_dot_rows).append(row)

    results = {
        "note": ("No pixel-exact ground truth exists for real photos -- precision/recall are NOT "
                 "computed here, only raw detection counts and rough human estimates. "
                 "NO_VISIBLE_DOT_MARKERS images never contribute to a recall metric."),
        "in_scope": in_scope_rows,
        "no_visible_dot_markers": no_dot_rows,
    }

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nWrote {RESULTS_PATH}\n")
    print("IN-SCOPE (visible dot markers):")
    for r in in_scope_rows:
        print(f"  {r['file']}: classical={r['classical_detector']['n_pixel_detections']}  "
              f"learned={r['learned_detector']['n_pixel_detections']}  "
              f"human_estimate={r['human_estimate']['estimate'] if r['human_estimate'] else 'n/a'}  "
              f"-- {r['failure_reason']}")
    n_no_dot_fp_classical = sum(1 for r in no_dot_rows if (r["classical_detector"].get("n_pixel_detections") or 0) > 0)
    n_no_dot_fp_learned = sum(1 for r in no_dot_rows if (r["learned_detector"].get("n_pixel_detections") or 0) > 0)
    print(f"\nNO_VISIBLE_DOT_MARKERS: {len(no_dot_rows)} images, "
          f"classical false-positive-images={n_no_dot_fp_classical}, "
          f"learned false-positive-images={n_no_dot_fp_learned}")


if __name__ == "__main__":
    main()
