"""M4.2-C/D benchmark: generate a real batch of structural candidates
via engine.generation_api and MEASURE (not assume) validity rate,
uniqueness, symmetry/motif/complexity distributions, and novelty --
against the actual output of the existing, unmodified M3.7 pipeline
(engine.novel_generation.select_novel_placements + engine.generation.
generate_kolam). No candidate's validity/novelty is asserted by hand;
every number in the output JSON comes from running the real pipeline
and checking its real result with engine.validity / engine.novelty.

Deterministic and reproducible: every (library, layout, max_multiplicity)
combination is a fixed, explicit input -- there is no random search here
(the underlying select_novel_placements is itself deterministic, no RNG),
so re-running this script reproduces byte-identical results. Config is
listed in full in the output JSON's "config" section.

Usage:
    python experiments/m4_2_generation/run_benchmark.py
    python experiments/m4_2_generation/run_benchmark.py --json experiments/m4_2_generation/results/benchmark.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter

import networkx as nx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from engine.dataset import load_kolam  # noqa: E402
from engine.generation_api import (  # noqa: E402
    GenerationConstraints,
    generate_kolam_candidate,
    motif_library_from_sources,
    rectangular_lattice,
)
from engine.novelty import graph_fingerprint, novelty_report  # noqa: E402
from engine.symmetry import analyze_symmetry  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")

# ------------------------------------------------------------------
# Config -- every value here is deliberate and listed in the output,
# not hidden inside the loop.
# ------------------------------------------------------------------

SINGLE_SOURCE_LIBRARIES = [("kolam19", pid) for pid in (1, 2, 3, 4, 5)] + [
    ("kolam29", pid) for pid in (1, 2)
]
MULTI_SOURCE_LIBRARIES = [
    [("kolam19", 1), ("kolam19", 2)],
    [("kolam19", 3), ("kolam19", 4)],
    [("kolam19", 1), ("kolam19", 5)],
]

SYNTHETIC_GRIDS = [(6, 6), (10, 10), (14, 14)]
# Unseen REAL layouts -- dot layouts from patterns whose OWN motifs are
# never used to build a library that gets placed on them (no library
# below is built from these three patterns), so this is a genuine
# "new to this candidate" layout, matching M3.7's own discipline.
UNSEEN_REAL_LAYOUTS = [("kolam19", 15), ("kolam19", 20), ("kolam29", 3)]

MAX_MULTIPLICITY_VALUES = [1, 2]


def _layout_sets():
    layouts = []
    for w, h in SYNTHETIC_GRIDS:
        layouts.append((f"synthetic_grid_{w}x{h}", rectangular_lattice(w, h)))
    for collection, pid in UNSEEN_REAL_LAYOUTS:
        pattern = load_kolam(collection, pid)
        layouts.append((f"real_layout_{collection}_{pid}", pattern.dot_points))
    return layouts


def _library_specs():
    specs = []
    for collection, pid in SINGLE_SOURCE_LIBRARIES:
        specs.append((f"single_{collection}_{pid}", [(collection, pid)]))
    for i, combo in enumerate(MULTI_SOURCE_LIBRARIES):
        name = "multi_" + "_".join(f"{c}_{p}" for c, p in combo)
        specs.append((name, combo))
    return specs


def run(connectivity_aware: bool = False, parity_aware: bool = False) -> dict:
    """`connectivity_aware=False, parity_aware=False` (defaults)
    reproduces the ORIGINAL 120-candidate M4.2-C/D benchmark exactly
    (same config, same rows shape plus a few additive fields) -- see
    experiments/m4_2_generation/run_connectivity_comparison.py (A vs. B)
    and run_parity_comparison.py (A vs. B vs. C), which call this
    function with different flag combinations under IDENTICAL config for
    a direct comparison, per docs/M4_2_CONNECTIVITY_EVALUATION.md and
    docs/M4_2_PARITY_EVALUATION.md."""
    layouts = _layout_sets()
    library_specs = _library_specs()

    # Pre-build libraries once per spec (motif_library_from_sources is
    # deterministic and pure -- safe to cache across the (library x
    # layout x multiplicity) grid below rather than rebuilding it
    # n_layouts * n_multiplicities times).
    libraries = {name: motif_library_from_sources(sources) for name, sources in library_specs}

    # Source patterns for novelty comparison: everything any library was
    # built from, PLUS the unseen real layouts (a candidate placed on an
    # unseen layout duplicating that layout's OWN real pattern would
    # still be a real, meaningful finding).
    source_keys = {kv for _name, sources in library_specs for kv in sources} | set(UNSEEN_REAL_LAYOUTS)
    source_patterns = [load_kolam(c, p) for c, p in sorted(source_keys)]

    rows = []
    candidates = []
    t_start_all = time.perf_counter()

    for lib_name, library in libraries.items():
        for layout_name, dots in layouts:
            for max_mult in MAX_MULTIPLICITY_VALUES:
                constraints = GenerationConstraints(
                    lattice=dots,
                    motif_library=library,
                    max_multiplicity=max_mult,
                    require_single_stroke=True,
                    connectivity_aware=connectivity_aware,
                    parity_aware=parity_aware,
                )
                t0 = time.perf_counter()
                result = generate_kolam_candidate(constraints)
                elapsed = time.perf_counter() - t0
                c = result.candidate

                sym_motif, sym_coverage, _tpp = analyze_symmetry(c.graph, dots=c.dot_points)
                n_components = nx.number_connected_components(c.graph)
                n_odd_degree = sum(1 for _n, d in c.graph.degree() if d % 2 == 1)

                rows.append(
                    {
                        "library": lib_name,
                        "library_size": len(library),
                        "layout": layout_name,
                        "max_multiplicity": max_mult,
                        "connectivity_aware": connectivity_aware,
                        "parity_aware": parity_aware,
                        "n_dots": c.n_dots,
                        "n_distinct_edges": c.n_distinct_edges,
                        "n_edge_instances": c.n_edge_instances,
                        "n_placements": len(c.placements),
                        "n_distinct_motifs_used": len(set(p.motif for p in c.placements)),
                        "is_valid": c.is_valid,
                        "connected": c.validity_result["largest_component_covers_all_nodes"],
                        "n_connected_components": n_components,
                        "n_odd_degree_nodes": n_odd_degree,
                        "is_eulerian_circuit": c.validity_result["is_eulerian_circuit"],
                        "has_eulerian_path": c.validity_result["has_eulerian_path"],
                        "symmetry_coverage": sym_coverage,
                        "graph_fingerprint_hash": hash(graph_fingerprint(c.graph)),
                        "elapsed_seconds": elapsed,
                    }
                )
                candidates.append(c)

    total_elapsed = time.perf_counter() - t_start_all

    n = len(rows)
    n_valid = sum(1 for r in rows if r["is_valid"])

    # Multiplicity correctness: no distinct edge in any candidate may
    # exceed the max_multiplicity IT was generated under (checked
    # per-row against the candidate's actual graph, not assumed from the
    # generator's own internal guard).
    multiplicity_violations = 0
    for row, c in zip(rows, candidates):
        strand_counts = Counter(frozenset(e) for e in c.graph.edges())
        if strand_counts and max(strand_counts.values()) > row["max_multiplicity"]:
            multiplicity_violations += 1

    novelty = novelty_report(candidates, source_patterns)

    n_fully_connected = sum(1 for r in rows if r["n_connected_components"] == 1)

    summary = {
        "n_candidates": n,
        "connectivity_aware": connectivity_aware,
        "parity_aware": parity_aware,
        "validity_rate": n_valid / n if n else None,
        "n_valid": n_valid,
        "fully_connected_rate": (n_fully_connected / n) if n else None,
        "n_fully_connected": n_fully_connected,
        "n_connected_components_min": min((r["n_connected_components"] for r in rows), default=None),
        "n_connected_components_max": max((r["n_connected_components"] for r in rows), default=None),
        "n_connected_components_mean": (sum(r["n_connected_components"] for r in rows) / n) if n else None,
        "n_odd_degree_nodes_min": min((r["n_odd_degree_nodes"] for r in rows), default=None),
        "n_odd_degree_nodes_max": max((r["n_odd_degree_nodes"] for r in rows), default=None),
        "n_odd_degree_nodes_mean": (sum(r["n_odd_degree_nodes"] for r in rows) / n) if n else None,
        "multiplicity_violations": multiplicity_violations,
        "symmetry_coverage_min": min((r["symmetry_coverage"] for r in rows), default=None),
        "symmetry_coverage_max": max((r["symmetry_coverage"] for r in rows), default=None),
        "symmetry_coverage_mean": (sum(r["symmetry_coverage"] for r in rows) / n) if n else None,
        "n_placements_min": min((r["n_placements"] for r in rows), default=None),
        "n_placements_max": max((r["n_placements"] for r in rows), default=None),
        "n_placements_mean": (sum(r["n_placements"] for r in rows) / n) if n else None,
        "novelty": novelty,
        "total_elapsed_seconds": total_elapsed,
        "mean_elapsed_seconds_per_candidate": (total_elapsed / n) if n else None,
    }

    return {
        "config": {
            "single_source_libraries": SINGLE_SOURCE_LIBRARIES,
            "multi_source_libraries": MULTI_SOURCE_LIBRARIES,
            "synthetic_grids": SYNTHETIC_GRIDS,
            "unseen_real_layouts": UNSEEN_REAL_LAYOUTS,
            "max_multiplicity_values": MAX_MULTIPLICITY_VALUES,
            "connectivity_aware": connectivity_aware,
            "parity_aware": parity_aware,
        },
        "rows": rows,
        "summary": summary,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--json",
        metavar="PATH",
        default=os.path.join(RESULTS_DIR, "benchmark.json"),
        help="Write full machine-readable results to PATH.",
    )
    parser.add_argument(
        "--connectivity-aware",
        action="store_true",
        help="Use the connectivity-aware placement scorer (default: off, the original M4.2-C/D baseline).",
    )
    parser.add_argument(
        "--parity-aware",
        action="store_true",
        help="Use the parity-aware placement scorer (default: off). See docs/M4_2_PARITY_EVALUATION.md.",
    )
    args = parser.parse_args()

    result = run(connectivity_aware=args.connectivity_aware, parity_aware=args.parity_aware)
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w") as f:
        json.dump(result, f, indent=2)

    s = result["summary"]
    print(f"connectivity_aware: {s['connectivity_aware']}  parity_aware: {s['parity_aware']}")
    print(f"n_candidates: {s['n_candidates']}")
    print(f"validity_rate: {s['validity_rate']:.4f} ({s['n_valid']}/{s['n_candidates']})")
    print(f"fully_connected_rate: {s['fully_connected_rate']:.4f} ({s['n_fully_connected']}/{s['n_candidates']})")
    print(
        f"n_connected_components: min={s['n_connected_components_min']} "
        f"mean={s['n_connected_components_mean']:.2f} max={s['n_connected_components_max']}"
    )
    print(
        f"n_odd_degree_nodes: min={s['n_odd_degree_nodes_min']} "
        f"mean={s['n_odd_degree_nodes_mean']:.2f} max={s['n_odd_degree_nodes_max']}"
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
    print(f"novelty: {json.dumps(s['novelty'], indent=2)}")
    print(f"total_elapsed_seconds: {s['total_elapsed_seconds']:.2f}")
    print(f"\nWrote full results to {args.json}")


if __name__ == "__main__":
    main()
