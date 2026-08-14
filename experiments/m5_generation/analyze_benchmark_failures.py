"""M5.1 Phase 3: failure-mode breakdown of the FINAL 500-candidate M5
benchmark (experiments/m5_generation/results/benchmark_report.json,
run_benchmark.py, already complete -- this script performs NO new
generation, only re-classifies the already-recorded per-candidate rows).

WHY multiplicity=3 appears (traced to the exact code path, not guessed):
`engine.learned_generation.repair_multiplicity`'s own
`max_repair_multiplicity` parameter defaults to
`DEFAULT_REPAIR_MAX_MULTIPLICITY = 3` (engine/learned_generation.py:65)
-- ONE HIGHER than `DEFAULT_MAX_MULTIPLICITY = 2`
(engine/novel_generation.py, the cap the SEARCH phase respects while
building the initial candidate). Repair is explicitly allowed to push
an edge from 2 strands to 3 while closing odd-degree parity
(engine/learned_generation.py:299 `if cur >= max_repair_multiplicity:
continue`) -- this is a deliberate code-level override, not an
emergent side effect of the graph algorithm. Phase 2's structural
dataset report (structural_dataset_report.json) is the independent
check on whether real data ever legitimately reaches strand-count 3
-- this script cross-references that report's answer directly (loads
it if present; reports "UNRESOLVED" honestly if Phase 2 hasn't
finished yet, never assumes).
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent / "results"
BENCHMARK_PATH = RESULTS_DIR / "benchmark_report.json"
STRUCTURAL_PATH = RESULTS_DIR / "structural_dataset_report.json"
OUT_PATH = RESULTS_DIR / "benchmark_failure_analysis.json"


def analyze() -> dict:
    data = json.loads(BENCHMARK_PATH.read_text())
    records = data["records"]
    n = len(records)

    valid_no_repair = [r for r in records if r["is_valid"] and r["repair_edges_applied"] == 0]
    valid_after_repair = [r for r in records if r["is_valid"] and r["repair_edges_applied"] > 0]
    invalid = [r for r in records if not r["is_valid"]]

    invalid_connectivity = [r for r in invalid if r["n_nodes_outside_largest_component"] > 0]
    # Among invalid candidates whose largest component already covers every
    # node (connectivity itself is not the blocker), the remaining failure
    # is parity (odd-degree nodes preventing an Eulerian circuit/path) --
    # repair_multiplicity is either not applicable (already valid) or was
    # applied but exhausted its max_repair_multiplicity budget before
    # closing every correction.
    invalid_parity_only = [
        r for r in invalid
        if r["n_nodes_outside_largest_component"] == 0 and r["n_odd_degree_nodes"] > 0
    ]
    invalid_other = [
        r for r in invalid
        if r["n_nodes_outside_largest_component"] == 0 and r["n_odd_degree_nodes"] == 0
    ]

    def _stats(rows, key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return {
            "n": len(vals),
            "mean": statistics.mean(vals) if vals else None,
            "median": statistics.median(vals) if vals else None,
            "min": min(vals) if vals else None,
            "max": max(vals) if vals else None,
        }

    mult_violations_among_valid_no_repair = sum(1 for r in valid_no_repair if r["multiplicity_violations"] > 0)
    mult_violations_among_valid_after_repair = sum(1 for r in valid_after_repair if r["multiplicity_violations"] > 0)

    repair_effect = {
        "n_dots_before_vs_after": "not tracked per-record in benchmark_report.json (n_dots is constant per layout, not affected by repair)",
        "connected_components_valid_after_repair": _stats(valid_after_repair, "connected_components"),
        "n_odd_degree_nodes_valid_after_repair_should_be_0": _stats(valid_after_repair, "n_odd_degree_nodes"),
        "repair_edges_applied_distribution": _stats(valid_after_repair, "repair_edges_applied"),
        "symmetry_coverage_valid_no_repair": _stats(valid_no_repair, "symmetry_coverage"),
        "symmetry_coverage_valid_after_repair": _stats(valid_after_repair, "symmetry_coverage"),
        "symmetry_coverage_invalid": _stats(invalid, "symmetry_coverage"),
    }

    multiplicity_root_cause = {
        "code_location": "engine/learned_generation.py:65 DEFAULT_REPAIR_MAX_MULTIPLICITY = 3",
        "search_phase_cap": "engine/novel_generation.py DEFAULT_MAX_MULTIPLICITY = 2 (respected during initial candidate construction)",
        "repair_phase_cap": "engine/learned_generation.py DEFAULT_REPAIR_MAX_MULTIPLICITY = 3 (ONE HIGHER than search's own cap)",
        "mechanism": (
            "repair_multiplicity's route-doubling loop (engine/learned_generation.py:295-303) walks "
            "diagnose_validity's Chinese-Postman corrections and increments an edge's strand count each "
            "time that edge appears on a correction path, skipped only once it reaches "
            "max_repair_multiplicity=3 -- so any edge that search left at multiplicity 2 AND that also "
            "lies on an odd-degree correction path gets pushed to 3 by design, not by accident."
        ),
        "classification": "PENDING -- see real_data_cross_reference below",
    }

    structural_report = None
    if STRUCTURAL_PATH.exists():
        structural_report = json.loads(STRUCTURAL_PATH.read_text())
        max_real = structural_report["A_edge_multiplicity"]["max_observed_multiplicity"]
        frac_real_gt2 = structural_report["A_edge_multiplicity"]["multiplicity_3plus_fraction"]
        if max_real <= 2:
            classification = "C: absent from the real training distribution (max observed = 2, repair's cap of 3 is unsupported by evidence)"
        elif frac_real_gt2 is not None and frac_real_gt2 < 0.01:
            classification = "B: technically possible but rare in real data"
        else:
            classification = "A: genuinely observed in real kolams at a non-trivial rate"
        multiplicity_root_cause["classification"] = classification
        multiplicity_root_cause["real_data_max_multiplicity"] = max_real
        multiplicity_root_cause["real_data_multiplicity_3plus_fraction"] = frac_real_gt2
    else:
        multiplicity_root_cause["real_data_cross_reference"] = "UNRESOLVED -- structural_dataset_report.json not yet available"

    report = {
        "n_total_candidates": n,
        "n_valid_no_repair": len(valid_no_repair),
        "n_valid_after_repair": len(valid_after_repair),
        "n_invalid_total": len(invalid),
        "n_invalid_connectivity": len(invalid_connectivity),
        "n_invalid_parity_only": len(invalid_parity_only),
        "n_invalid_other_unclassified": len(invalid_other),
        "fraction_valid_no_repair": len(valid_no_repair) / n,
        "fraction_valid_after_repair": len(valid_after_repair) / n,
        "fraction_invalid_connectivity": len(invalid_connectivity) / n,
        "fraction_invalid_parity_only": len(invalid_parity_only) / n,
        "multiplicity_violation_rate_valid_no_repair": mult_violations_among_valid_no_repair / len(valid_no_repair) if valid_no_repair else None,
        "multiplicity_violation_rate_valid_after_repair": mult_violations_among_valid_after_repair / len(valid_after_repair) if valid_after_repair else None,
        "repair_effect_on_valid_candidates": repair_effect,
        "multiplicity_3_root_cause": multiplicity_root_cause,
        "invalid_connectivity_component_stats": _stats(invalid_connectivity, "connected_components"),
        "invalid_connectivity_nodes_outside_stats": _stats(invalid_connectivity, "n_nodes_outside_largest_component"),
        "invalid_parity_odd_node_stats": _stats(invalid_parity_only, "n_odd_degree_nodes"),
        "invalid_parity_correction_cost_stats": _stats(invalid_parity_only, "total_correction_cost"),
    }
    return report


def main() -> None:
    report = analyze()
    OUT_PATH.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"\nwrote {OUT_PATH}")


if __name__ == "__main__":
    main()
