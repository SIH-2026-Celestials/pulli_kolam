"""M4.1 Phase 9: does better (or different) perception actually change
structural analysis outcomes? Feeds BOTH detectors' output through the
UNCHANGED deterministic pipeline (trace_path -> graph -> motif induction
/ validity) and reports exactly where each one succeeds or fails --
never modifying trace_path or any downstream function to make either
detector look better.

Populations: m4_1_test (the learned model's true held-out set),
synthetic_heldout (independent of the learned model entirely), and the
4 real in-scope photos (never trained on by either detector, since the
classical one isn't trained at all and the learned one was only trained
on synthetic data).
"""

from __future__ import annotations

import glob
import json
import os
import sys

import networkx as nx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from engine import image_io, motifs, validity  # noqa: E402
from experiments.m4_1.classical_baseline import REAL_DIR, REAL_EXCLUDED, REAL_INSCOPE  # noqa: E402
from experiments.m4_1.ml_lattice_detector import LearnedLatticeDetector, MalformedOutputError  # noqa: E402

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results", "downstream_test.json")


def _run_pipeline(detector_fn, image_path: str) -> dict:
    stage = "preprocess"
    try:
        preprocessed = image_io.preprocess(image_path)
        stage = "detect"
        lattice = detector_fn(preprocessed)
        stage = "trace_path"
        edges = image_io.trace_path(preprocessed, lattice)
        stage = "graph_construction"
        G = nx.MultiGraph()
        G.add_nodes_from(lattice.lattice_coords)
        for a, b in edges:
            G.add_edge(a, b)
        stage = "motif_analysis"
        result = {
            "reached_stage": "motif_analysis", "crashed": False,
            "n_dots_detected": len(lattice.pixel_positions),
            "n_lattice_nodes": G.number_of_nodes(),
            "n_traced_edges": len(edges),
        }
        if G.number_of_nodes() >= 1:
            vres = validity.check_validity(G)
            result["connected"] = vres["largest_component_covers_all_nodes"]
            result["is_eulerian_circuit"] = vres["is_eulerian_circuit"]
            dots = set(G.nodes())
            interior = motifs.interior_points(dots, radius=1)
            placements, _residual, _fully_covered = motifs.induce_motif_set_adaptive(
                G, interior, dots, max_radius=2, max_motifs_per_radius=50
            )
            result["motif_analysis_completed"] = True
            result["n_motif_placements"] = len(placements)
        else:
            result["connected"] = None
            result["motif_analysis_completed"] = False
        return result
    except Exception as e:  # noqa: BLE001
        return {"reached_stage": stage, "crashed": True, "crash_type": type(e).__name__, "crash_message": str(e)[:200]}


def _run_set(image_paths: list[str], detector_fn, detector_name: str) -> list[dict]:
    rows = []
    for path in image_paths:
        row = {"file": os.path.basename(path), "detector": detector_name}
        row.update(_run_pipeline(detector_fn, path))
        rows.append(row)
    return rows


def main():
    print("Loading learned detector...")
    learned_detector = LearnedLatticeDetector()
    classical_detector = image_io.detect_lattice

    populations = {
        "m4_1_test": sorted(glob.glob(os.path.join(os.path.dirname(__file__), "data", "test", "*.jpg"))),
        "synthetic_heldout": sorted(glob.glob("synthetic_photos_heldout/*.jpg")),
        "real_in_scope": [
            p for p in sorted(glob.glob(os.path.join(REAL_DIR, "*.jpg")))
            if os.path.basename(p) in REAL_INSCOPE and os.path.basename(p) not in REAL_EXCLUDED
        ],
    }

    results = {}
    for pop_name, paths in populations.items():
        if not paths:
            continue
        print(f"\n{pop_name} ({len(paths)} images)")
        classical_rows = _run_set(paths, classical_detector, "classical")
        learned_rows = _run_set(paths, learned_detector, "learned")
        results[pop_name] = {"classical": classical_rows, "learned": learned_rows}

        for name, rows in [("classical", classical_rows), ("learned", learned_rows)]:
            n_crashed = sum(1 for r in rows if r["crashed"])
            n_completed = sum(1 for r in rows if r.get("motif_analysis_completed"))
            n_connected = sum(1 for r in rows if r.get("connected"))
            print(f"  {name}: {n_crashed}/{len(rows)} crashed, "
                  f"{n_completed}/{len(rows)} reached motif analysis, "
                  f"{n_connected}/{len(rows)} fully connected")

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
