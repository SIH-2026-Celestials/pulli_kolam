"""M5.1 Phase 2: empirical structural distributions of the REAL training
corpus (kolam19 + kolam29, 500 patterns -- kolam109 excluded, same
precedent as every other analysis in this repo: too dense, poor small-
scale recoverability).

Every measurement here reuses existing, unmodified engine/ code
(engine.dataset.load_kolam, engine.validity.check_validity,
engine.symmetry.analyze_symmetry, engine.motifs.induce_motif_set_adaptive)
-- this script computes NO new structural logic, only aggregates what
those functions already report across every real pattern.

Nothing here is a threshold or a rule -- Phase 2 is measurement only.
M5_1_CONSTRAINT_SPEC.md (Phase 5) is where measured evidence becomes a
constraint decision.
"""

from __future__ import annotations

import json
import statistics
import time
from collections import Counter
from pathlib import Path

import networkx as nx

from engine.dataset import list_pattern_ids, load_kolam
from engine.motifs import induce_motif_set_adaptive, interior_points
from engine.symmetry import analyze_symmetry
from engine.validity import check_validity

RESULTS_DIR = Path(__file__).resolve().parent / "results"
JSON_PATH = RESULTS_DIR / "structural_dataset_report.json"
MD_PATH = RESULTS_DIR / "structural_dataset_report.md"

COLLECTIONS = ["kolam19", "kolam29"]


def _percentiles(values: list, ps=(0, 5, 25, 50, 75, 95, 100)) -> dict:
    if not values:
        return {f"p{p}": None for p in ps}
    s = sorted(values)
    out = {}
    for p in ps:
        idx = min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))
        out[f"p{p}"] = s[idx]
    return out


def _edge_length(a: tuple, b: tuple) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def analyze() -> dict:
    t0 = time.time()

    all_multiplicities: list[int] = []
    n_patterns_with_mult_gt2 = 0
    max_observed_multiplicity = 0

    all_degrees: list[int] = []
    component_counts: list[int] = []
    n_fully_connected = 0
    component_size_dist: Counter = Counter()

    all_edge_lengths: list[float] = []
    nn_distances: list[float] = []
    n_long_edges = 0  # length > sqrt(2) (beyond an immediate-diagonal lattice step)

    utilization_fractions: list[float] = []

    symmetry_coverages: list[float] = []

    n_nodes_list: list[int] = []
    n_distinct_edges_list: list[int] = []
    n_edge_instances_list: list[int] = []
    n_eulerian_circuit = 0
    n_eulerian_path = 0

    motif_shape_counter: Counter = Counter()
    motif_size_list: list[int] = []
    n_motif_types_per_pattern: list[int] = []
    motif_induction_failures = 0

    n_patterns = 0
    for collection in COLLECTIONS:
        for pid in list_pattern_ids(collection):
            n_patterns += 1
            pattern = load_kolam(collection, pid)
            G = pattern.graph
            dots = pattern.dot_points

            # A. Edge multiplicity
            mult_values = list(pattern.edge_multiplicity.values())
            all_multiplicities.extend(mult_values)
            if mult_values:
                pattern_max = max(mult_values)
                max_observed_multiplicity = max(max_observed_multiplicity, pattern_max)
                if pattern_max > 2:
                    n_patterns_with_mult_gt2 += 1

            # B. Node degree
            degrees = [d for _, d in G.degree()]
            all_degrees.extend(degrees)

            # C. Connectivity
            n_components = nx.number_connected_components(G)
            component_counts.append(n_components)
            for comp in nx.connected_components(G):
                component_size_dist[len(comp)] += 1
            validity = check_validity(G)
            if validity["largest_component_covers_all_nodes"]:
                n_fully_connected += 1

            # D. Edge locality
            for a, b in G.edges():
                length = _edge_length(a, b)
                all_edge_lengths.append(length)
                if length > 2 ** 0.5 + 1e-9:
                    n_long_edges += 1
            if len(dots) >= 2:
                from scipy.spatial import cKDTree
                import numpy as np

                pts = np.array(sorted(dots))
                tree = cKDTree(pts)
                dist, _idx = tree.query(pts, k=2)
                nn_distances.extend(dist[:, 1].tolist())

            # E. Dot/node utilization
            xs = [p[0] for p in dots]
            ys = [p[1] for p in dots]
            if xs and ys:
                width = max(xs) - min(xs) + 1
                height = max(ys) - min(ys) + 1
                capacity = width * height
                utilization_fractions.append(len(dots) / capacity if capacity else 0.0)

            # F. Symmetry
            try:
                _motif, coverage, _tp = analyze_symmetry(G, dots=set(dots), radius=1)
                symmetry_coverages.append(coverage)
            except Exception:
                pass

            # G. Structural complexity
            n_nodes_list.append(G.number_of_nodes())
            n_distinct_edges_list.append(len({frozenset(e) for e in G.edges()}))
            n_edge_instances_list.append(G.number_of_edges())
            if validity["is_eulerian_circuit"]:
                n_eulerian_circuit += 1
            elif validity["has_eulerian_path"]:
                n_eulerian_path += 1

            # H. Motifs
            try:
                interior = interior_points(dots, radius=1)
                placements, _residual, _full = induce_motif_set_adaptive(
                    G, interior_points=interior, dots_set=dots
                )
                n_motif_types_per_pattern.append(len(placements))
                for p in placements:
                    motif_shape_counter[p.motif] += 1
                    motif_size_list.append(len(p.motif))
            except Exception:
                motif_induction_failures += 1

    elapsed = time.time() - t0

    mult_hist = Counter(all_multiplicities)
    n_total_edges = len(all_multiplicities)

    report = {
        "n_patterns": n_patterns,
        "collections": COLLECTIONS,
        "analysis_time_seconds": elapsed,

        "A_edge_multiplicity": {
            "n_total_distinct_edges_measured": n_total_edges,
            "multiplicity_1_count": mult_hist.get(1, 0),
            "multiplicity_1_fraction": mult_hist.get(1, 0) / n_total_edges if n_total_edges else None,
            "multiplicity_2_count": mult_hist.get(2, 0),
            "multiplicity_2_fraction": mult_hist.get(2, 0) / n_total_edges if n_total_edges else None,
            "multiplicity_3plus_count": sum(v for k, v in mult_hist.items() if k >= 3),
            "multiplicity_3plus_fraction": sum(v for k, v in mult_hist.items() if k >= 3) / n_total_edges if n_total_edges else None,
            "max_observed_multiplicity": max_observed_multiplicity,
            "n_patterns_with_multiplicity_gt2": n_patterns_with_mult_gt2,
            "fraction_patterns_with_multiplicity_gt2": n_patterns_with_mult_gt2 / n_patterns if n_patterns else None,
            "full_histogram": dict(sorted(mult_hist.items())),
        },

        "B_node_degree": {
            "min": min(all_degrees) if all_degrees else None,
            "max": max(all_degrees) if all_degrees else None,
            "mean": statistics.mean(all_degrees) if all_degrees else None,
            "median": statistics.median(all_degrees) if all_degrees else None,
            "percentiles": _percentiles(all_degrees),
            "distribution": dict(sorted(Counter(all_degrees).items())),
        },

        "C_connectivity": {
            "mean_connected_components": statistics.mean(component_counts) if component_counts else None,
            "fraction_fully_connected": n_fully_connected / n_patterns if n_patterns else None,
            "n_fully_connected": n_fully_connected,
            "component_size_distribution": dict(sorted(component_size_dist.items())),
        },

        "D_edge_locality": {
            "edge_length_percentiles": _percentiles(all_edge_lengths),
            "edge_length_mean": statistics.mean(all_edge_lengths) if all_edge_lengths else None,
            "nearest_neighbor_distance_percentiles": _percentiles(nn_distances),
            "nearest_neighbor_distance_mean": statistics.mean(nn_distances) if nn_distances else None,
            "n_long_edges_gt_sqrt2": n_long_edges,
            "long_edge_fraction": n_long_edges / len(all_edge_lengths) if all_edge_lengths else None,
        },

        "E_dot_utilization": {
            "mean_utilization_fraction": statistics.mean(utilization_fractions) if utilization_fractions else None,
            "median_utilization_fraction": statistics.median(utilization_fractions) if utilization_fractions else None,
            "percentiles": _percentiles(utilization_fractions),
        },

        "F_symmetry": {
            "mean_coverage": statistics.mean(symmetry_coverages) if symmetry_coverages else None,
            "median_coverage": statistics.median(symmetry_coverages) if symmetry_coverages else None,
            "percentiles": _percentiles(symmetry_coverages),
            "fraction_high_symmetry_ge_0.5": sum(1 for c in symmetry_coverages if c >= 0.5) / len(symmetry_coverages) if symmetry_coverages else None,
        },

        "G_structural_complexity": {
            "n_nodes": {"mean": statistics.mean(n_nodes_list), "median": statistics.median(n_nodes_list), "percentiles": _percentiles(n_nodes_list)},
            "n_distinct_edges": {"mean": statistics.mean(n_distinct_edges_list), "median": statistics.median(n_distinct_edges_list), "percentiles": _percentiles(n_distinct_edges_list)},
            "n_edge_instances_multiplicity_weighted": {"mean": statistics.mean(n_edge_instances_list), "median": statistics.median(n_edge_instances_list), "percentiles": _percentiles(n_edge_instances_list)},
            "fraction_eulerian_circuit_closed_loop": n_eulerian_circuit / n_patterns if n_patterns else None,
            "fraction_eulerian_path_open_stroke": n_eulerian_path / n_patterns if n_patterns else None,
            "fraction_neither_hard_gate_failure": (n_patterns - n_eulerian_circuit - n_eulerian_path) / n_patterns if n_patterns else None,
        },

        "H_motifs": {
            "n_motif_induction_failures": motif_induction_failures,
            "n_distinct_motif_shapes_across_corpus": len(motif_shape_counter),
            "motif_shape_frequency_top20": [{"motif_edge_count": len(m), "count": c} for m, c in motif_shape_counter.most_common(20)],
            "motif_size_distribution": dict(sorted(Counter(motif_size_list).items())),
            "motif_size_mean": statistics.mean(motif_size_list) if motif_size_list else None,
            "n_motif_types_per_pattern": {
                "mean": statistics.mean(n_motif_types_per_pattern) if n_motif_types_per_pattern else None,
                "median": statistics.median(n_motif_types_per_pattern) if n_motif_types_per_pattern else None,
                "percentiles": _percentiles(n_motif_types_per_pattern),
            },
        },
    }
    return report


def write_markdown(report: dict) -> str:
    a = report["A_edge_multiplicity"]
    b = report["B_node_degree"]
    c = report["C_connectivity"]
    d = report["D_edge_locality"]
    e = report["E_dot_utilization"]
    f = report["F_symmetry"]
    g = report["G_structural_complexity"]
    h = report["H_motifs"]

    md = f"""# Structural dataset report -- real kolam19 + kolam29 corpus

{report['n_patterns']} patterns measured ({', '.join(report['collections'])}), analysis time {report['analysis_time_seconds']:.1f}s.
Generated by `experiments/m5_generation/analyze_structural_dataset.py`.

## A. Edge multiplicity

| multiplicity | count | fraction |
|---|---|---|
| 1 | {a['multiplicity_1_count']} | {a['multiplicity_1_fraction']:.4f} |
| 2 | {a['multiplicity_2_count']} | {a['multiplicity_2_fraction']:.4f} |
| 3+ | {a['multiplicity_3plus_count']} | {a['multiplicity_3plus_fraction']:.4f} |

**Maximum observed multiplicity in real data: {a['max_observed_multiplicity']}**
**Patterns containing any multiplicity > 2: {a['n_patterns_with_multiplicity_gt2']} / {report['n_patterns']} ({a['fraction_patterns_with_multiplicity_gt2']:.4f})**

## B. Node degree

min={b['min']}, max={b['max']}, mean={b['mean']:.3f}, median={b['median']}
Percentiles: {b['percentiles']}

## C. Connectivity

Mean connected components per pattern: {c['mean_connected_components']:.4f}
Fraction fully connected (single component): {c['fraction_fully_connected']:.4f} ({c['n_fully_connected']}/{report['n_patterns']})

## D. Edge locality (Euclidean length in lattice units)

Edge length percentiles: {d['edge_length_percentiles']}
Edge length mean: {d['edge_length_mean']:.4f}
Nearest-neighbor distance mean: {d['nearest_neighbor_distance_mean']:.4f}
Long edges (length > sqrt(2)): {d['n_long_edges_gt_sqrt2']} ({d['long_edge_fraction']:.4f} of all edges)

## E. Dot/lattice utilization

Mean utilization (dots used / bounding-box capacity): {e['mean_utilization_fraction']:.4f}
Median: {e['median_utilization_fraction']:.4f}

## F. Symmetry (D4 dominant-motif tile coverage)

Mean coverage: {f['mean_coverage']:.4f}
Median coverage: {f['median_coverage']:.4f}
Fraction "high symmetry" (coverage >= 0.5): {f['fraction_high_symmetry_ge_0.5']:.4f}

## G. Structural complexity

Nodes: mean={g['n_nodes']['mean']:.1f}, median={g['n_nodes']['median']}
Distinct edges: mean={g['n_distinct_edges']['mean']:.1f}, median={g['n_distinct_edges']['median']}
Multiplicity-weighted edge instances: mean={g['n_edge_instances_multiplicity_weighted']['mean']:.1f}, median={g['n_edge_instances_multiplicity_weighted']['median']}

Closed-loop (Eulerian circuit): {g['fraction_eulerian_circuit_closed_loop']:.4f}
Open single-stroke (Eulerian path): {g['fraction_eulerian_path_open_stroke']:.4f}
Neither (hard-gate failure -- should be ~0 for verified real data): {g['fraction_neither_hard_gate_failure']:.4f}

## H. Motifs

Distinct motif shapes across corpus: {h['n_distinct_motif_shapes_across_corpus']}
Motif size (edges per motif) mean: {h['motif_size_mean']:.3f}
Motif types per pattern: mean={h['n_motif_types_per_pattern']['mean']:.2f}, median={h['n_motif_types_per_pattern']['median']}
Motif induction failures: {h['n_motif_induction_failures']}
"""
    return md


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report = analyze()
    JSON_PATH.write_text(json.dumps(report, indent=2))
    md = write_markdown(report)
    MD_PATH.write_text(md)
    print(md)
    print(f"wrote {JSON_PATH}")
    print(f"wrote {MD_PATH}")


if __name__ == "__main__":
    main()
