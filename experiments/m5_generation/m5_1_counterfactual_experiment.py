"""M5.1 Phase 4: isolated counterfactual experiment.

Does NOT modify engine/learned_generation.py, engine/novel_generation.py,
or engine/validity.py -- every variant is expressed by calling the
EXISTING, unmodified `engine.learned_generation.search_best_candidate`
and `repair_multiplicity` with different arguments (both already expose
the exact knobs this experiment needs: `max_multiplicity`,
`repair_max_multiplicity`, `n_restarts`), plus ONE new repair strategy
(`_reroute_aware_repair`, variant C/D) implemented ENTIRELY in this
script using only public engine.validity/engine.generation calls -- no
private engine internals are duplicated or modified.

SCALE NOTE (documented, not hidden -- same convention
experiments/m5_generation/run_benchmark_lite.py already established):
the FINAL M5 benchmark (run_benchmark.py, N=500, n_restarts=6) took
5730s wall-clock for ONE configuration. Four variants at N=500 each
would take ~6.5 hours, not a diagnosis-scale experiment. This script
runs N_CANDIDATES_PER_VARIANT=60 per variant (SAME seeds 0..59 across
all variants, and the SAME motif-library/layout selection
run_benchmark.py used) -- large enough to see real percentage-point
differences between variants (60 candidates resolves down to ~1.7
percentage points per candidate), small enough to run in one sitting.
This is explicitly NOT a replacement for a full 500-candidate
confirmation of whichever variant Phase 5 recommends -- that is future
work, not claimed here.

VARIANTS:
  baseline   : current M5 production behavior exactly (max_multiplicity=2
               search cap, repair_max_multiplicity=3) -- reproduces
               run_benchmark.py's own configuration, used here as the
               within-this-script control rather than re-reading the
               500-candidate report (so latency/environment conditions
               are comparable across variants run back-to-back).
  variant_A  : hard maximum edge multiplicity = 2 (repair_max_multiplicity=2,
               i.e. repair now REFUSES any correction that would exceed
               real data's observed ceiling -- see structural_dataset_report.json).
               A correction that cannot be satisfied within the cap is
               simply skipped (same "skip, never force through" discipline
               repair_multiplicity's own docstring already establishes),
               so this variant's failure mode is candidates that stay
               invalid (unresolved parity) rather than exceeding the cap.
  variant_B  : soft penalty -- two-tier repair. First attempt repair with
               max_multiplicity=2 (same as variant A). If the candidate is
               STILL invalid after that pass, run a SECOND repair pass
               with max_multiplicity=3 on the remaining corrections only
               (a real "prefer not to, but allow if necessary" policy,
               not a scoring change -- there is no continuous score to
               penalize in a deterministic route-doubling repair, so
               "soft" is implemented as a fallback tier, not a weighted
               objective). Reports how often the fallback tier was needed.
  variant_C  : reroute-aware repair -- before falling back to raising an
               edge's multiplicity past 2, tries the NEXT-shortest path
               between the same odd-degree pair (k=2..5 shortest simple
               paths via nx.shortest_simple_paths) that does not reuse
               any edge already at multiplicity 2. Only escalates to
               multiplicity 3 if EVERY tried alternate path also collides
               with an already-doubled edge.
  variant_D  : connectivity-first -- doubles search effort (n_restarts=12
               instead of the production default 6) on the theory that
               Phase 3 found connectivity (not parity) is M5's sole
               bottleneck (0/141 invalid candidates fail on parity alone,
               100% fail on connectivity -- benchmark_failure_analysis.json),
               so more restarts spent finding a connected structure should
               matter more than any repair change. Uses variant_C's
               reroute-aware repair as its repair stage (compounding the
               two most evidence-supported interventions).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import networkx as nx

from engine.dataset import load_kolam
from engine.generated_kolam import GeneratedKolam
from engine.generation import reconstruct_dot_trace
from engine.generation_api import motif_library_from_sources
from engine.learned_generation import search_best_candidate
from engine.learned_scoring import load_scorer
from engine.novelty import graph_fingerprint, novelty_report
from engine.symmetry import analyze_symmetry
from engine.validity import check_validity, diagnose_validity

DATA_DIR = Path(__file__).resolve().parent / "data"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
OUT_PATH = RESULTS_DIR / "m5_1_counterfactual_report.json"

N_CANDIDATES_PER_VARIANT = 60
N_RESTARTS_DEFAULT = 6
N_RESTARTS_VARIANT_D = 12


def _test_sources() -> list[tuple[str, int]]:
    manifest = json.loads((DATA_DIR / "split_manifest.json").read_text())
    return [tuple(s.split("#")) for s in manifest["test"]]


def _reroute_aware_repair(candidate: GeneratedKolam, max_soft_multiplicity: int = 2, hard_cap: int = 3) -> tuple[GeneratedKolam, list[dict], dict]:
    """EXPERIMENT-ONLY repair strategy (not in engine/) -- reuses
    engine.validity.diagnose_validity's odd-node pairing (unmodified) but,
    for each correction, tries nx.shortest_simple_paths to find an
    alternate route between the same pair that avoids reusing an edge
    already at `max_soft_multiplicity`, only falling back to the
    diagnosis's own shortest path (potentially exceeding
    max_soft_multiplicity, up to hard_cap) if no such alternate exists
    within a bounded number of attempts (K_ALTERNATES)."""
    if candidate.is_valid:
        return candidate, [], {"n_rerouted": 0, "n_forced_above_soft_cap": 0}
    diagnosis = candidate.diagnosis
    if diagnosis["n_nodes_outside_largest_component"] > 0:
        return candidate, [], {"n_rerouted": 0, "n_forced_above_soft_cap": 0}

    from collections import Counter

    graph = candidate.graph.copy()
    largest = max(nx.connected_components(graph), key=len)
    Gc_simple = nx.Graph()
    Gc_simple.add_nodes_from(largest)
    for a, b in graph.subgraph(largest).edges():
        Gc_simple.add_edge(a, b)

    existing_mult = Counter(frozenset(e) for e in graph.edges())
    applied = []
    n_rerouted = 0
    n_forced_above_soft_cap = 0
    K_ALTERNATES = 5

    for correction in diagnosis["corrections"]:
        u, v = correction["pair"]
        chosen_path_edges = None
        try:
            path_gen = nx.shortest_simple_paths(Gc_simple, u, v)
            for i, path in enumerate(path_gen):
                if i >= K_ALTERNATES:
                    break
                path_edges = list(zip(path, path[1:]))
                if all(existing_mult.get(frozenset({a, b}), 0) < max_soft_multiplicity for a, b in path_edges):
                    chosen_path_edges = path_edges
                    if i > 0:
                        n_rerouted += 1
                    break
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            chosen_path_edges = None

        if chosen_path_edges is None:
            chosen_path_edges = correction["path_edges"]
            n_forced_above_soft_cap += 1

        for a, b in chosen_path_edges:
            e = frozenset({a, b})
            cur = existing_mult.get(e, 0)
            if cur >= hard_cap:
                continue
            graph.add_edge(a, b)
            existing_mult[e] = cur + 1
            applied.append({"edge": [list(a), list(b)], "new_multiplicity": cur + 1})

    validity_result = check_validity(graph)
    new_diagnosis = diagnose_validity(graph)
    is_valid = validity_result["largest_component_covers_all_nodes"] and (
        validity_result["is_eulerian_circuit"] or validity_result["has_eulerian_path"]
    )
    dot_trace = reconstruct_dot_trace(graph) if is_valid else None
    edge_multiplicity = dict(Counter(frozenset(e) for e in graph.edges()))

    repaired = GeneratedKolam(
        dot_points=set(candidate.dot_points), graph=graph, placements=list(candidate.placements),
        edge_multiplicity=edge_multiplicity, validity_result=validity_result,
        diagnosis=new_diagnosis, dot_trace=dot_trace,
    )
    return repaired, applied, {"n_rerouted": n_rerouted, "n_forced_above_soft_cap": n_forced_above_soft_cap}


def _two_tier_repair(candidate: GeneratedKolam) -> tuple[GeneratedKolam, list, bool]:
    """Variant B: try max_multiplicity=2 first; fall back to 3 only if
    still invalid. Reuses engine.learned_generation.repair_multiplicity
    unmodified, called twice with different caps."""
    from engine.learned_generation import repair_multiplicity

    tier1, applied1 = repair_multiplicity(candidate, max_repair_multiplicity=2)
    if tier1.is_valid:
        return tier1, applied1, False
    tier2, applied2 = repair_multiplicity(candidate, max_repair_multiplicity=3)
    return tier2, applied2, True


def _run_variant(name: str, motif_library, layouts, scorer, n_restarts: int, repair_fn) -> dict:
    records = []
    t_start = time.time()
    for i in range(N_CANDIDATES_PER_VARIANT):
        layout_name, dots = layouts[i % len(layouts)]
        seed = i
        t0 = time.time()
        candidate, restarts_info = search_best_candidate(
            motif_library, dots, scorer=scorer, n_restarts=n_restarts,
            max_multiplicity=2, seed=seed,
        )
        raw_valid_no_repair = candidate.is_valid
        repair_used_fallback = None
        if not candidate.is_valid:
            result = repair_fn(candidate)
            # repair_fn is one of: engine.learned_generation.repair_multiplicity
            # (returns 2-tuple: candidate, applied), _two_tier_repair (returns
            # 3-tuple: candidate, applied, used_fallback: bool), or
            # _reroute_aware_repair (returns 3-tuple: candidate, applied,
            # stats: dict) -- disambiguate by tuple length, then by the
            # THIRD element's type for the two 3-tuple cases.
            if len(result) == 2:
                candidate, applied = result
            elif isinstance(result[2], bool):
                candidate, applied, repair_used_fallback = result
            else:
                candidate, applied, _stats = result
        else:
            applied = []
        latency = time.time() - t0

        diag = candidate.diagnosis
        mult_violations = sum(1 for v in candidate.edge_multiplicity.values() if v > 2)
        max_mult = max(candidate.edge_multiplicity.values()) if candidate.edge_multiplicity else 0

        try:
            _motif, symmetry_coverage, _tp = analyze_symmetry(candidate.graph, dots=set(candidate.dot_points), radius=1)
        except Exception:
            symmetry_coverage = None

        records.append({
            "index": i, "seed": seed, "layout": layout_name,
            "is_valid": candidate.is_valid, "raw_valid_no_repair": raw_valid_no_repair,
            "connected_components": diag["connected_components"],
            "n_nodes_outside_largest_component": diag["n_nodes_outside_largest_component"],
            "n_odd_degree_nodes": diag["n_odd_degree_nodes"],
            "multiplicity_violations": mult_violations, "max_multiplicity": max_mult,
            "repair_edges_applied": len(applied), "repair_used_fallback": repair_used_fallback,
            "symmetry_coverage": symmetry_coverage, "n_edges": candidate.n_distinct_edges,
            "latency_seconds": latency,
            "fingerprint": hash(graph_fingerprint(candidate.graph)),
        })
    total_time = time.time() - t_start

    n = len(records)
    n_valid = sum(1 for r in records if r["is_valid"])
    n_raw_valid = sum(1 for r in records if r["raw_valid_no_repair"])
    n_connectivity_failed = sum(1 for r in records if not r["is_valid"] and r["n_nodes_outside_largest_component"] > 0)
    n_mult_violations = sum(1 for r in records if r["multiplicity_violations"] > 0)
    n_unique_fp = len({r["fingerprint"] for r in records})

    summary = {
        "variant": name, "n_candidates": n, "n_restarts": n_restarts,
        "validity_rate": n_valid / n, "raw_validity_rate_before_repair": n_raw_valid / n,
        "post_repair_validity_rate": n_valid / n,
        "connectivity_failure_rate": n_connectivity_failed / n,
        "multiplicity_violation_rate": n_mult_violations / n,
        "uniqueness_rate": n_unique_fp / n,
        "avg_symmetry_coverage": sum(r["symmetry_coverage"] for r in records if r["symmetry_coverage"] is not None) / max(1, sum(1 for r in records if r["symmetry_coverage"] is not None)),
        "avg_latency_seconds": sum(r["latency_seconds"] for r in records) / n,
        "avg_n_edges": sum(r["n_edges"] for r in records) / n,
        "total_time_seconds": total_time,
        "n_repair_fallback_used": sum(1 for r in records if r.get("repair_used_fallback") is True),
    }
    return {"summary": summary, "records": records}


def main() -> None:
    test_sources = [(c, int(p)) for c, p in _test_sources()]
    scorer = load_scorer()

    layouts = []
    for collection, pid in test_sources:
        pattern = load_kolam(collection, pid)
        layouts.append((f"{collection}#{pid}", pattern.dot_points))
    library_sources = test_sources[:5]
    motif_library = motif_library_from_sources(list(library_sources))
    print(f"motif library size: {len(motif_library)} from {library_sources}", flush=True)

    from engine.learned_generation import repair_multiplicity

    variants = {
        "baseline": lambda c: repair_multiplicity(c, max_repair_multiplicity=3),
        "variant_A_hard_cap_2": lambda c: repair_multiplicity(c, max_repair_multiplicity=2),
        "variant_B_soft_two_tier": _two_tier_repair,
        "variant_C_reroute_aware": lambda c: _reroute_aware_repair(c, max_soft_multiplicity=2, hard_cap=3),
    }

    results = {}
    for name, repair_fn in variants.items():
        print(f"=== running {name} ===", flush=True)
        results[name] = _run_variant(name, motif_library, layouts, scorer, N_RESTARTS_DEFAULT, repair_fn)
        print(json.dumps(results[name]["summary"], indent=2), flush=True)

    print("=== running variant_D_connectivity_first (n_restarts=12, reroute repair) ===", flush=True)
    results["variant_D_connectivity_first"] = _run_variant(
        "variant_D_connectivity_first", motif_library, layouts, scorer, N_RESTARTS_VARIANT_D,
        lambda c: _reroute_aware_repair(c, max_soft_multiplicity=2, hard_cap=3),
    )
    print(json.dumps(results["variant_D_connectivity_first"]["summary"], indent=2), flush=True)

    out = {
        "scale_note": (
            f"N_CANDIDATES_PER_VARIANT={N_CANDIDATES_PER_VARIANT}, same seeds 0..{N_CANDIDATES_PER_VARIANT - 1} "
            "across all variants. NOT a full 500-candidate confirmation -- diagnosis scale, see module docstring."
        ),
        "comparison_table": {name: r["summary"] for name, r in results.items()},
        "full_records": {name: r["records"] for name, r in results.items()},
    }
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {OUT_PATH}")


if __name__ == "__main__":
    main()
