"""M5: assemble the comparison table against every prior generator this
project has actually measured -- baseline greedy, connectivity-aware,
connectivity+parity-aware (experiments/m4_2_generation/results/*.json,
frozen, read-only here), plus this session's learned-scorer-guided
search (experiments/m5_generation/results/benchmark_report_lite.json).
Every number here is read directly from an existing results file, never
recomputed or guessed.
"""
from __future__ import annotations

import json
from pathlib import Path

M42 = Path(__file__).resolve().parent.parent / "m4_2_generation" / "results"
M5 = Path(__file__).resolve().parent / "results"


def _load(p):
    return json.loads(p.read_text()) if p.exists() else None


def _rate(rows):
    n = len(rows)
    return sum(1 for r in rows if r["is_valid"]) / n if n else None


def main():
    parity = _load(M42 / "parity_comparison.json")
    connectivity = _load(M42 / "connectivity_comparison.json")
    beam = _load(M42 / "beam_comparison.json")
    m5_lite = _load(M5 / "benchmark_report_lite.json")
    m5_full = _load(M5 / "benchmark_report.json")  # may not exist -- full 500-candidate run not completed this session

    rows = {}
    if parity:
        rows["baseline (greedy, no connectivity/parity)"] = {
            "n": len(parity["arm_a_baseline"]["rows"]),
            "validity_rate": _rate(parity["arm_a_baseline"]["rows"]),
            "source": "experiments/m4_2_generation/results/parity_comparison.json:arm_a_baseline",
        }
        rows["connectivity-aware (greedy)"] = {
            "n": len(parity["arm_b_connectivity"]["rows"]),
            "validity_rate": _rate(parity["arm_b_connectivity"]["rows"]),
            "source": "experiments/m4_2_generation/results/parity_comparison.json:arm_b_connectivity",
        }
        rows["connectivity+parity-aware (greedy)"] = {
            "n": len(parity["arm_c_connectivity_parity"]["rows"]),
            "validity_rate": _rate(parity["arm_c_connectivity_parity"]["rows"]),
            "source": "experiments/m4_2_generation/results/parity_comparison.json:arm_c_connectivity_parity",
        }
    if beam:
        rows["multi-restart beam (hand-tuned score, pre-M5)"] = {
            "n": len(beam["arm_d_beam"]["rows"]),
            "validity_rate": _rate(beam["arm_d_beam"]["rows"]),
            "source": "experiments/m4_2_generation/results/beam_comparison.json:arm_d_beam",
        }
    if m5_lite:
        s = m5_lite["summary"]
        rows["M5 learned-scorer-guided search (THIS SESSION, reduced scale)"] = {
            "n": s["n_generated"], "validity_rate": s["validity_rate"],
            "connectivity_rate": s["connectivity_rate"],
            "multiplicity_violation_rate": s["multiplicity_violation_rate"],
            "avg_latency_seconds": s["avg_generation_latency_seconds"],
            "novelty_unique_rate": s["novelty"].get("unique_rate"),
            "novelty_exact_topological_duplicate_rate": s["novelty"].get("exact_topological_duplicate_rate"),
            "note": s["SCALE_NOTE"],
            "source": "experiments/m5_generation/results/benchmark_report_lite.json",
        }
    if m5_full:
        s = m5_full["summary"]
        rows["M5 learned-scorer-guided search (FULL 500-candidate benchmark)"] = {
            "n": s["n_generated"], "validity_rate": s["validity_rate"],
            "connectivity_rate": s["connectivity_rate"],
            "multiplicity_violation_rate": s["multiplicity_violation_rate"],
            "avg_latency_seconds": s["avg_generation_latency_seconds"],
            "novelty_unique_rate": s["novelty"].get("unique_rate"),
            "novelty_exact_topological_duplicate_rate": s["novelty"].get("exact_topological_duplicate_rate"),
            "source": "experiments/m5_generation/results/benchmark_report.json",
        }

    out = {"comparison": rows}
    out_path = M5 / "decision_matrix.json"
    out_path.write_text(json.dumps(out, indent=2))

    print(f"{'Generator':55s} {'n':>5s} {'valid_rate':>11s}")
    print("-" * 75)
    for name, r in rows.items():
        vr = r.get("validity_rate")
        vr_str = f"{vr:.3f}" if isinstance(vr, float) else str(vr)
        print(f"{name:55s} {r['n']:>5d} {vr_str:>11s}")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
