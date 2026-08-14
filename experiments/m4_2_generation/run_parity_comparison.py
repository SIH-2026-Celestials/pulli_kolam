"""A/B/C comparison, per docs/M4_2_PARITY_EVALUATION.md:

  A: connectivity_aware=False, parity_aware=False  (original baseline)
  B: connectivity_aware=True,  parity_aware=False  (docs/M4_2_CONNECTIVITY_EVALUATION.md)
  C: connectivity_aware=True,  parity_aware=True   (this experiment)

All three arms call experiments.m4_2_generation.run_benchmark.run() with
IDENTICAL config (same libraries, layouts, multiplicity caps -- 120
candidates per arm) -- there is exactly one place the benchmark grid is
defined, so the three arms cannot silently drift out of sync.

Usage:
    python experiments/m4_2_generation/run_parity_comparison.py
    python experiments/m4_2_generation/run_parity_comparison.py --json experiments/m4_2_generation/results/parity_comparison.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from experiments.m4_2_generation.run_benchmark import run  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


def _print_summary(label: str, s: dict):
    print(f"--- {label} ---")
    print(f"n_candidates: {s['n_candidates']}")
    print(f"valid: {s['n_valid']}/{s['n_candidates']} ({s['validity_rate']:.4f})")
    print(f"fully_connected: {s['n_fully_connected']}/{s['n_candidates']} ({s['fully_connected_rate']:.4f})")
    print(
        f"n_connected_components: min={s['n_connected_components_min']} "
        f"mean={s['n_connected_components_mean']:.2f} max={s['n_connected_components_max']}"
    )
    print(
        f"n_odd_degree_nodes: min={s['n_odd_degree_nodes_min']} "
        f"mean={s['n_odd_degree_nodes_mean']:.2f} max={s['n_odd_degree_nodes_max']}"
    )
    print(f"multiplicity_violations: {s['multiplicity_violations']}")
    nov = s["novelty"]
    print(
        f"novelty: unique_rate={nov['unique_rate']:.4f} "
        f"exact_topological_duplicate_rate={nov['exact_topological_duplicate_rate']:.4f} "
        f"exact_coordinate_duplicate_rate={nov['exact_coordinate_duplicate_rate']} "
        f"near_duplicate_rate={nov['near_duplicate_rate']}"
    )
    print(
        f"runtime: total={s['total_elapsed_seconds']:.2f}s "
        f"mean={s['mean_elapsed_seconds_per_candidate']:.4f}s/candidate"
    )
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--json",
        metavar="PATH",
        default=os.path.join(RESULTS_DIR, "parity_comparison.json"),
        help="Write full machine-readable results (all three arms) to PATH.",
    )
    args = parser.parse_args()

    arm_a = run(connectivity_aware=False, parity_aware=False)
    arm_b = run(connectivity_aware=True, parity_aware=False)
    arm_c = run(connectivity_aware=True, parity_aware=True)

    _print_summary("A: baseline (connectivity=False, parity=False)", arm_a["summary"])
    _print_summary("B: connectivity-aware (connectivity=True, parity=False)", arm_b["summary"])
    _print_summary("C: connectivity + parity-aware (connectivity=True, parity=True)", arm_c["summary"])

    result = {"arm_a_baseline": arm_a, "arm_b_connectivity": arm_b, "arm_c_connectivity_parity": arm_c}
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote full A/B/C comparison to {args.json}")


if __name__ == "__main__":
    main()
