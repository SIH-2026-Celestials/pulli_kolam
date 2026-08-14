"""M4.3 Phase 0: freeze and record the V2 baseline before touching
anything. Read-only with respect to experiments/m4_2/* -- never writes
to experiments/m4_2/results/dot_heatmap_net_v2.pt or
experiments/m4_2/data/. Reuses experiments/m4_2/evaluate_m4_2.json's
already-computed synthetic/no-dot numbers (re-running that eval would
just reproduce the same deterministic detector on the same frozen data)
and ADDS the structural/reconstruction metrics that file does not
compute, using experiments/m4_3/structural_metrics.py against the same
four real in-scope photos and the synthetic test set.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from engine import image_io  # noqa: E402
from experiments.m4_1.classical_baseline import REAL_DIR, REAL_EXCLUDED, REAL_INSCOPE  # noqa: E402
from experiments.m4_2.ml_lattice_detector import LearnedLatticeDetectorV2, CHECKPOINT_PATH  # noqa: E402
from experiments.m4_3.structural_metrics import (  # noqa: E402
    run_detector_with_structural_metrics, aggregate_structural,
)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
V2_EVAL_JSON = os.path.join(
    os.path.dirname(__file__), "..", "m4_2", "results", "evaluate_m4_2.json"
)
M4_2_DATA_TEST = os.path.join(os.path.dirname(__file__), "..", "m4_2", "data", "test")


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def main():
    print("Checkpoint SHA256...")
    v2_sha256 = sha256_of(CHECKPOINT_PATH)
    print(" ", v2_sha256)

    with open(V2_EVAL_JSON) as f:
        v2_eval = json.load(f)

    print("Loading V2 detector for structural-metrics pass (read-only)...")
    v2_detector = LearnedLatticeDetectorV2()

    # structural metrics on synthetic test set (frozen m4_2 data, read only)
    synth_rows = []
    for json_path in sorted(glob.glob(os.path.join(M4_2_DATA_TEST, "*.json"))):
        with open(json_path) as f:
            gt = json.load(f)
        synth_rows.append(run_detector_with_structural_metrics(gt["image_path"], v2_detector))
    synth_struct = aggregate_structural(synth_rows)
    print("synthetic_test structural:", synth_struct)

    # structural metrics on the 4 real in-scope photos (prediction only, no GT)
    inscope_rows = {}
    for path in sorted(glob.glob(os.path.join(REAL_DIR, "*.jpg"))):
        fname = os.path.basename(path)
        if fname in REAL_EXCLUDED or fname not in REAL_INSCOPE:
            continue
        inscope_rows[fname] = run_detector_with_structural_metrics(path, v2_detector)
    print("real in-scope structural (prediction only):", json.dumps(inscope_rows, indent=1))

    result = {
        "phase": "0 -- V2 baseline freeze",
        "v2_checkpoint_path": os.path.relpath(CHECKPOINT_PATH),
        "v2_checkpoint_sha256": v2_sha256,
        "v2_config": {
            "model": "DotHeatmapNetV2", "model_input_size": 256, "output_stride": 2,
            "heatmap_size": 128, "sigma_cells": 1.2,
            "confidence_threshold": 0.6, "min_peak_distance_heatmap_cells": 2.0,
            "model_version": v2_detector.model_version,
            "training_data": "experiments/m4_2/data (135 patterns, kolam19+kolam29, kolam109 excluded)",
        },
        "synthetic_test_from_evaluate_m4_2_json": v2_eval["sets"]["synthetic_test"],
        "synthetic_val_from_evaluate_m4_2_json": v2_eval["sets"]["synthetic_val"],
        "real_no_dot_fp_rate_from_evaluate_m4_2_json": v2_eval["real_photos"]["real_no_dot"],
        "real_in_scope_detection_counts_from_evaluate_m4_2_json": v2_eval["real_photos"]["real_in_scope"],
        "structural_metrics": {
            "synthetic_test": {"per_image_n": len(synth_rows), "aggregate": synth_struct},
            "real_in_scope_prediction_only": inscope_rows,
            "note": ("real_in_scope_prediction_only has NO ground-truth graph -- these are the "
                     "graph/reconstruction properties of V2's OWN predicted dot lattice, not a "
                     "verified match to the true kolam. Never compare to a fabricated GT."),
        },
        "note": ("V2 checkpoint and experiments/m4_2/data/ were not modified by this script -- "
                 "read-only load + inference only."),
    }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, "v2_baseline.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
