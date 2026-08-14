"""M6 Phase 8: structural novelty measurement.

Explicitly NOT pixel/PNG-hash based (task's own instruction). Combines
several REAL, cheaply-computable structural distance terms rather than
claiming an exact graph-edit-distance solve (NP-hard in general --
faking an "exact" GED here would be dishonest, not merely
approximate). Reuses engine.novelty's exact/near-duplicate machinery
(D4+translation-canonical graph fingerprinting, coordinate-exact Jaccard
similarity) for the STRICT duplicate signal, and adds a bounded
COMBINED DISTANCE for the graded novelty_score, built from:

  - topology_distance   : normalized |dot count| and |edge count| deltas
  - degree_distance      : L1 distance between normalized degree-value
                            histograms (captures local connectivity
                            pattern shape, independent of absolute size)
  - symmetry_distance     : |D4 motif-tile coverage fraction| delta
                            (engine.symmetry.analyze_symmetry's own metric)
  - geometric_distance    : normalized |complexity| and |density| deltas
                            (same real, computed fields build_dataset.py
                            already stores per example)

Each term is in [0, 1]; combined_distance is their unweighted mean (a
simple, auditable combination -- not a learned/opaque one). novelty_score
= combined_distance against the NEAREST training example (1.0 = as
different as the scale allows from anything seen; 0.0 = structurally
identical stats to some training example, though NOT proof of identical
topology -- see duplicate detection below for that stronger claim).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import networkx as nx

from engine.novelty import coordinate_similarity, graph_fingerprint


@dataclass
class StructuralStats:
    n_dots: int
    n_distinct_edges: int
    n_edge_instances: int
    symmetry_coverage: float
    complexity: float
    density: float
    degree_histogram: "dict[int, float]"  # degree -> fraction of nodes with that degree

    @staticmethod
    def from_graph(graph: nx.MultiGraph, symmetry_coverage: float, complexity: float, density: float) -> "StructuralStats":
        n_dots = graph.number_of_nodes()
        degrees = [d for _, d in graph.degree()]
        hist: Counter = Counter(degrees)
        degree_histogram = {k: v / n_dots for k, v in hist.items()} if n_dots else {}
        return StructuralStats(
            n_dots=n_dots,
            n_distinct_edges=len({frozenset(e) for e in graph.edges()}),
            n_edge_instances=graph.number_of_edges(),
            symmetry_coverage=symmetry_coverage, complexity=complexity, density=density,
            degree_histogram=degree_histogram,
        )


def _saturating_ratio(a: float, b: float) -> float:
    """|a-b| / max(a,b,1) -- in [0, 1), 0 when equal."""
    denom = max(a, b, 1.0)
    return abs(a - b) / denom


def _degree_histogram_distance(a: "dict[int, float]", b: "dict[int, float]") -> float:
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    total = sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in keys)
    return min(1.0, total / 2.0)  # L1 distance between two probability distributions is in [0, 2]


def structural_distance(a: StructuralStats, b: StructuralStats) -> dict:
    topology_distance = (_saturating_ratio(a.n_dots, b.n_dots) + _saturating_ratio(a.n_distinct_edges, b.n_distinct_edges)) / 2
    degree_distance = _degree_histogram_distance(a.degree_histogram, b.degree_histogram)
    symmetry_distance = abs(a.symmetry_coverage - b.symmetry_coverage)
    geometric_distance = (_saturating_ratio(a.complexity, b.complexity) + _saturating_ratio(a.density, b.density)) / 2
    combined = (topology_distance + degree_distance + symmetry_distance + geometric_distance) / 4
    return {
        "topology_distance": topology_distance, "degree_distance": degree_distance,
        "symmetry_distance": symmetry_distance, "geometric_distance": geometric_distance,
        "combined_distance": combined,
    }


def nearest_training_novelty(
    candidate_graph: nx.MultiGraph,
    candidate_stats: StructuralStats,
    training_stats: "list[StructuralStats]",
    training_graphs: "list[nx.MultiGraph] | None" = None,
    near_duplicate_threshold: float = 0.9,
) -> dict:
    """Per-candidate novelty report (Phase 8's explicit output shape):
    nearest_training_distance, novelty_score (== that distance -- higher
    is more novel), plus the STRICT exact/near-duplicate signals reused
    from engine.novelty where a same-layout comparison is even possible.
    """
    if not training_stats:
        return {
            "nearest_training_distance": None, "novelty_score": None,
            "is_exact_topological_duplicate": None, "is_near_duplicate_coordinate": None,
        }

    distances = [structural_distance(candidate_stats, t)["combined_distance"] for t in training_stats]
    nearest_distance = min(distances)

    is_exact_topological_duplicate = None
    is_near_duplicate_coordinate = None
    if training_graphs:
        cand_fp = graph_fingerprint(candidate_graph)
        empty_fp = graph_fingerprint(nx.MultiGraph())
        is_exact_topological_duplicate = cand_fp != empty_fp and any(
            graph_fingerprint(g) == cand_fp for g in training_graphs
        )
        best_coord_sim = None
        for g in training_graphs:
            if set(g.nodes()) != set(candidate_graph.nodes()):
                continue
            e1 = Counter(frozenset(e) for e in candidate_graph.edges())
            e2 = Counter(frozenset(e) for e in g.edges())
            keys = set(e1) | set(e2)
            if not keys:
                continue
            inter = sum(min(e1.get(k, 0), e2.get(k, 0)) for k in keys)
            union = sum(max(e1.get(k, 0), e2.get(k, 0)) for k in keys)
            sim = inter / union if union else 1.0
            if best_coord_sim is None or sim > best_coord_sim:
                best_coord_sim = sim
        is_near_duplicate_coordinate = (
            best_coord_sim is not None and near_duplicate_threshold <= best_coord_sim
        )

    return {
        "nearest_training_distance": nearest_distance,
        "novelty_score": nearest_distance,
        "is_exact_topological_duplicate": is_exact_topological_duplicate,
        "is_near_duplicate_coordinate": is_near_duplicate_coordinate,
    }
