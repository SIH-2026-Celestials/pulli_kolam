"""A/B comparison: baseline generator (connectivity_aware=False) vs.
connectivity-aware generator (connectivity_aware=True), under IDENTICAL
config -- same source patterns, same layouts, same motif budget, same
multiplicity caps, same candidate count (120 in each arm). Both arms
call experiments.m4_2_generation.run_benchmark.run(), so there is
exactly one place the benchmark grid is defined -- this script cannot
silently drift out of sync with the original 120-candidate baseline.

Usage:
    python experiments/m4_2_generation/run_connectivity_comparison.py
    python experiments/m4_2_generation/run_connectivity_comparison.py --json experiments/m4_2_generation/results/connectivity_comparison.json
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
    print(f"validity_rate: {s['validity_rate']:.4f} ({s['n_valid']}/{s['n_candidates']})")
    print(f"fully_connected_rate: {s['fully_connected_rate']:.4f} ({s['n_fully_connected']}/{s['n_candidates']})")
    print(
        f"n_connected_components: min={s['n_connected_components_min']} "
        f"mean={s['n_connected_components_mean']:.2f} max={s['n_connected_components_max']}"
    )
    print(f"multiplicity_violations: {s['multiplicity_violations']}")
    print(
        f"symmetry_coverage: min={s['symmetry_coverage_min']:.3f} "
        f"mean={s['symmetry_coverage_mean']:.3f} max={s['symmetry_coverage_max']:.3f}"
    )
    print(
        f"n_placements: min={s['n_placements_min']} mean={s['n_placements_mean']:.2f} "
        f"max={s['n_placements_max']}"
    )
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
        default=os.path.join(RESULTS_DIR, "connectivity_comparison.json"),
        help="Write full machine-readable results (both arms) to PATH.",
    )
    args = parser.parse_args()

    baseline = run(connectivity_aware=False)
    aware = run(connectivity_aware=True)

    _print_summary("A: baseline (connectivity_aware=False)", baseline["summary"])
    _print_summary("B: connectivity-aware (connectivity_aware=True)", aware["summary"])

    result = {"baseline": baseline, "connectivity_aware": aware}
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote full A/B comparison to {args.json}")


if __name__ == "__main__":
    main()
