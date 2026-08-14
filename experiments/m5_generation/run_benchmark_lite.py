"""M5: a TIME-BUDGETED variant of run_benchmark.py's serious evaluation.

WHY THIS EXISTS (not silently swapped in for run_benchmark.py): a direct
timing measurement (one candidate, n_restarts=16, a 200-dot real held-out
layout) took ~24 seconds -- so run_benchmark.py's full N_CANDIDATES=500
would take on the order of 3-4 hours, which does not fit this session's
time budget. Rather than let a single evaluation run silently consume
the entire remaining budget with no checkpoint, this script runs the
IDENTICAL metric computation over a smaller N_CANDIDATES/N_RESTARTS,
reported honestly as a reduced-scale run (n_generated/n_restarts are
recorded in the output so nobody mistakes this for the full benchmark).
run_benchmark.py itself is UNCHANGED and can be re-run later with more
time budget for the full 500-candidate evaluation.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from engine.dataset import load_kolam
from engine.generation_api import motif_library_from_sources
from engine.learned_generation import generate_novel_kolam_learned
from engine.learned_scoring import load_scorer
from engine.novelty import novelty_report, graph_fingerprint
from engine.symmetry import analyze_symmetry

RESULTS_PATH = Path(__file__).resolve().parent / "results" / "benchmark_report_lite.json"
DATA_DIR = Path(__file__).resolve().parent / "data"

N_CANDIDATES = 50
N_RESTARTS = 12


def _test_sources() -> list[tuple[str, int]]:
    manifest = json.loads((DATA_DIR / "split_manifest.json").read_text())
    return [tuple(s.split("#")) for s in manifest["test"]]


def run() -> dict:
    test_sources = _test_sources()
    test_sources = [(c, int(p)) for c, p in test_sources]

    scorer = load_scorer()

    layouts = []
    for collection, pid in test_sources:
        pattern = load_kolam(collection, pid)
        layouts.append((f"{collection}#{pid}", pattern.dot_points))

    library_sources = test_sources[: min(5, len(test_sources))]
    motif_library = motif_library_from_sources([(c, p) for c, p in library_sources])
    print(f"motif library size: {len(motif_library)} (from {library_sources})")

    real_sources = [load_kolam(c, p) for c, p in test_sources]

    records = []
    t_start = time.time()
    for i in range(N_CANDIDATES):
        layout_name, dots = layouts[i % len(layouts)]
        seed = i
        t0 = time.time()
        run_result = generate_novel_kolam_learned(
            motif_library, dots, scorer=scorer, n_restarts=N_RESTARTS, seed=seed
        )
        latency = time.time() - t0
        candidate = run_result.candidate
        diag = candidate.diagnosis

        symmetry_info = None
        try:
            _motif, coverage, _tp = analyze_symmetry(candidate.graph, dots=set(candidate.dot_points), radius=1)
            symmetry_info = {"coverage_fraction": coverage}
        except Exception:
            symmetry_info = None

        mult_violations = sum(1 for v in candidate.edge_multiplicity.values() if v > 2)

        records.append({
            "index": i, "seed": seed, "layout": layout_name, "n_dots": candidate.n_dots,
            "is_valid": candidate.is_valid, "connected_components": diag["connected_components"],
            "n_nodes_outside_largest_component": diag["n_nodes_outside_largest_component"],
            "n_odd_degree_nodes": diag["n_odd_degree_nodes"], "total_correction_cost": diag["total_correction_cost"],
            "multiplicity_violations": mult_violations,
            "symmetry_coverage": symmetry_info["coverage_fraction"] if symmetry_info else None,
            "n_restarts_used": len(run_result.restarts), "repair_edges_applied": len(run_result.repair_applied),
            "latency_seconds": latency,
        })
        n_valid_so_far = sum(1 for r in records if r["is_valid"])
        print(f"{i + 1}/{N_CANDIDATES}  valid_so_far={n_valid_so_far}  "
              f"latency={latency:.1f}s  elapsed={time.time() - t_start:.0f}s", flush=True)

    total_time = time.time() - t_start

    n = len(records)
    n_valid = sum(1 for r in records if r["is_valid"])
    n_connected = sum(1 for r in records if r["n_nodes_outside_largest_component"] == 0)
    n_mult_violations = sum(1 for r in records if r["multiplicity_violations"] > 0)
    avg_latency = sum(r["latency_seconds"] for r in records) / n
    symmetry_vals = [r["symmetry_coverage"] for r in records if r["symmetry_coverage"] is not None]

    # reproducibility check (2 seeds, cheaper than the full run's 3)
    repro_checks = []
    for i in [0, 5]:
        if i >= n:
            continue
        layout_name, dots = layouts[i % len(layouts)]
        r1 = generate_novel_kolam_learned(motif_library, dots, scorer=scorer, n_restarts=N_RESTARTS, seed=i)
        r2 = generate_novel_kolam_learned(motif_library, dots, scorer=scorer, n_restarts=N_RESTARTS, seed=i)
        same = graph_fingerprint(r1.candidate.graph) == graph_fingerprint(r2.candidate.graph)
        repro_checks.append({"seed": i, "reproducible": same})

    valid_seeds = [r["seed"] for r in records if r["is_valid"]]
    valid_candidates = []
    for seed in valid_seeds:
        layout_name, dots = layouts[seed % len(layouts)]
        rr = generate_novel_kolam_learned(motif_library, dots, scorer=scorer, n_restarts=N_RESTARTS, seed=seed)
        valid_candidates.append(rr.candidate)

    novelty = novelty_report(valid_candidates, real_sources) if valid_candidates else {
        "n_candidates": 0, "unique_rate": None, "exact_topological_duplicate_rate": None,
        "exact_coordinate_duplicate_rate": None, "near_duplicate_rate": None,
    }

    # reliability-at-k: does more attempts help? (task's explicit ask --
    # measured at 1, 10, 100 attempts where possible; here at 1/10/N given
    # the reduced candidate count)
    def _at_least_one_valid_in_first_k(k):
        return any(r["is_valid"] for r in records[:k])

    reliability = {
        "at_1_attempt": records[0]["is_valid"] if records else None,
        "at_10_attempts": _at_least_one_valid_in_first_k(min(10, n)),
        f"at_{n}_attempts": n_valid > 0,
    }

    report = {
        "SCALE_NOTE": (f"REDUCED-SCALE run: n_generated={n} (vs run_benchmark.py's full N_CANDIDATES=500), "
                        f"n_restarts={N_RESTARTS} (vs full N_RESTARTS=16 nominal -- here {N_RESTARTS}) -- "
                        "time-budget decision, documented not hidden. See module docstring."),
        "n_generated": n, "n_valid": n_valid, "validity_rate": n_valid / n,
        "n_connected_all_nodes": n_connected, "connectivity_rate": n_connected / n,
        "n_multiplicity_violations": n_mult_violations, "multiplicity_violation_rate": n_mult_violations / n,
        "avg_symmetry_coverage": (sum(symmetry_vals) / len(symmetry_vals)) if symmetry_vals else None,
        "avg_generation_latency_seconds": avg_latency, "total_benchmark_time_seconds": total_time,
        "seed_reproducibility_checks": repro_checks, "novelty": novelty,
        "reliability_at_k": reliability,
        "motif_library_size": len(motif_library), "n_layouts": len(layouts),
        "n_restarts_per_candidate": N_RESTARTS, "scorer_metadata": scorer.metadata,
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps({"summary": report, "records": records}, indent=2))
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run()
