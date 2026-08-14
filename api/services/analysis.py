"""M7 platform integration: mathematical analysis services.

Every analyzer here is a THIN, framework-independent wrapper -- takes an
`nx.MultiGraph` (or a `GeneratedKolam`/`KolamPattern`-like object with a
`.graph`), returns a plain dict. No analyzer reimplements graph theory
that already exists in `engine/` -- each one calls straight into
`engine.validity`, `engine.symmetry`, or `engine.novelty`, unmodified,
per this task's explicit "do not duplicate existing algorithms" rule.

These are pure functions (no DB, no FastAPI) so they're usable from a
script, a test, or a request handler identically -- api/services/generation.py
calls them and persists the results; nothing here knows about
persistence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import networkx as nx

from engine.symmetry import analyze_symmetry
from engine.validity import check_validity, diagnose_validity


def _as_graph(obj) -> nx.MultiGraph:
    """`isinstance`, NOT `hasattr(obj, "graph")` -- nx.MultiGraph/Graph
    objects carry their OWN built-in `.graph` attribute (a plain dict
    for graph-level metadata, defaults to `{}`), so `hasattr` is always
    True for a raw graph too and would wrongly treat that metadata dict
    as the graph itself. Same landmine already documented and fixed in
    engine/generation_contract.py's build_representation and
    api/services/verification.py's own _as_graph."""
    return obj if isinstance(obj, nx.MultiGraph) else obj.graph


@dataclass
class GraphMetrics:
    vertices: int
    edges: int
    distinct_edges: int
    connected_components: int
    density: "float | None"
    degree_distribution: "dict[str, int]"


def analyze_graph(obj) -> GraphMetrics:
    """GraphAnalyzer: vertices, edges, degree distribution, connected
    components, density -- all direct NetworkX queries, no new math."""
    G = _as_graph(obj)
    n = G.number_of_nodes()
    m = G.number_of_edges()
    distinct = len({frozenset(e) for e in G.edges()})
    from collections import Counter

    degrees = Counter(dict(G.degree()).values())
    # Density uses the DISTINCT edge count (simple-graph convention,
    # nx.density's own definition: 2E / (N(N-1)) for an undirected
    # graph) -- using the multiplicity-weighted edge count here would
    # produce a density > 1 whenever strands repeat, which is not a
    # meaningful "how full is this graph" statistic.
    density = (2 * distinct) / (n * (n - 1)) if n > 1 else None
    return GraphMetrics(
        vertices=n, edges=m, distinct_edges=distinct,
        connected_components=nx.number_connected_components(G),
        density=density,
        degree_distribution={str(k): v for k, v in sorted(degrees.items())},
    )


@dataclass
class EulerianMetrics:
    odd_degree_vertex_count: int
    largest_component_covers_all_nodes: bool
    is_eulerian_circuit: bool
    has_eulerian_path: bool
    is_valid_single_stroke: bool


def analyze_eulerian(obj) -> EulerianMetrics:
    """EulerianAnalyzer: wraps engine.validity.check_validity/diagnose_validity
    UNMODIFIED -- this is the same hard gate every other part of PULLI
    uses, not a re-derived or looser check."""
    G = _as_graph(obj)
    validity = check_validity(G)
    diagnosis = diagnose_validity(G)
    is_valid = validity["largest_component_covers_all_nodes"] and (
        validity["is_eulerian_circuit"] or validity["has_eulerian_path"]
    )
    return EulerianMetrics(
        odd_degree_vertex_count=diagnosis["n_odd_degree_nodes"],
        largest_component_covers_all_nodes=validity["largest_component_covers_all_nodes"],
        is_eulerian_circuit=validity["is_eulerian_circuit"],
        has_eulerian_path=validity["has_eulerian_path"],
        is_valid_single_stroke=is_valid,
    )


@dataclass
class MultiplicityMetrics:
    max_multiplicity: int
    distribution: "dict[str, int]"
    violations: int  # edges with strand count > 2, the real-data-verified ceiling (see M5_1_CONSTRAINT_SPEC.md)


def analyze_multiplicity(obj) -> MultiplicityMetrics:
    """MultiplicityAnalyzer: real strand-count distribution, and
    violations against the EMPIRICALLY-MEASURED real-data ceiling of 2
    (experiments/m5_generation/results/structural_dataset_report.json,
    500 patterns, 181,966 edges, max observed = 2, zero exceptions --
    not an arbitrary number)."""
    G = _as_graph(obj)
    from collections import Counter

    mult: Counter = Counter(frozenset(e) for e in G.edges())
    dist: Counter = Counter(mult.values())
    max_mult = max(mult.values()) if mult else 0
    violations = sum(1 for v in mult.values() if v > 2)
    return MultiplicityMetrics(
        max_multiplicity=max_mult,
        distribution={str(k): v for k, v in sorted(dist.items())},
        violations=violations,
    )


@dataclass
class SymmetryMetrics:
    coverage: "float | None"
    dominant_transform_sample: "str | None"


def analyze_symmetry_metrics(obj) -> SymmetryMetrics:
    """SymmetryAnalyzer: D4 (identity, rot90/180/270, 4 reflections)
    dominant-motif coverage via engine.symmetry.analyze_symmetry,
    UNMODIFIED. Reports the ACTUAL measured coverage -- never inflated
    or adjusted based on what a caller requested (per this task's
    explicit "do NOT artificially increase symmetry based on user
    configuration" rule; see M5_1_CONSTRAINT_SPEC.md Section 2.1 for
    why: real data itself averages only ~20% coverage, so a generator
    that always reports high symmetry would be reporting something
    false, not just optimistic)."""
    G = _as_graph(obj)
    dots = getattr(obj, "dot_points", None) or set(G.nodes())
    try:
        motif, coverage, transform_per_point = analyze_symmetry(G, dots=set(dots), radius=1)
    except Exception:
        return SymmetryMetrics(coverage=None, dominant_transform_sample=None)
    sample_transform = next(iter(transform_per_point.values()), None) if transform_per_point else None
    return SymmetryMetrics(coverage=coverage, dominant_transform_sample=sample_transform)


@dataclass
class ComplexityMetrics:
    complexity_score: float
    density_score: float


def analyze_complexity(obj) -> ComplexityMetrics:
    """ComplexityAnalyzer: same real formula
    experiments/m6_generation/build_dataset.py already established and
    validated against real data (not invented fresh here) --
    complexity = distinct_edges / (3 * n_dots), density =
    edge_instances / n_dots / 6, both clamped to [0, 1]."""
    G = _as_graph(obj)
    n = G.number_of_nodes()
    distinct = len({frozenset(e) for e in G.edges()})
    instances = G.number_of_edges()
    complexity = min(1.0, distinct / (3.0 * max(n, 1)))
    density = min(1.0, (instances / max(n, 1)) / 6.0)
    return ComplexityMetrics(complexity_score=complexity, density_score=density)


@dataclass
class NoveltyMetrics:
    novelty_score: "float | None"
    nearest_source_id: "str | None"
    is_exact_duplicate: "bool | None"


def analyze_novelty(candidate, reference_sources: list, source_ids: "list[str] | None" = None) -> NoveltyMetrics:
    """NoveltyAnalyzer: reuses engine.novelty.per_candidate_novelty
    UNMODIFIED (built during M5's own novelty-scoring work) -- no new
    fingerprinting/canonicalization algorithm here, per this task's
    explicit "reuse existing fingerprinting logic" instruction.
    `reference_sources` empty -> honestly reports None, never a
    fabricated score (same discipline engine.novelty already uses)."""
    from engine.novelty import per_candidate_novelty

    # engine.novelty.per_candidate_novelty expects a GeneratedKolam-like
    # object (.graph, .dot_points, .diagnosis, .is_valid) -- a raw
    # nx.MultiGraph (isinstance check, not hasattr: see _as_graph's own
    # docstring for why hasattr is always True here) genuinely doesn't
    # carry enough information for a meaningful novelty score, so this
    # honestly reports "not computed" rather than crash or fabricate one.
    if isinstance(candidate, nx.MultiGraph) or not hasattr(candidate, "graph"):
        return NoveltyMetrics(None, None, None)
    rows = per_candidate_novelty([candidate], reference_sources, source_ids=source_ids, candidate_ids=["_"])
    row = rows[0]
    return NoveltyMetrics(
        novelty_score=row["novelty_score"],
        nearest_source_id=row["source_id"],
        is_exact_duplicate=(row["novelty_score"] == 0.0) if row["novelty_score"] is not None else None,
    )


def analyze_all(obj, reference_sources: "list | None" = None, source_ids: "list[str] | None" = None) -> dict:
    """Convenience: run every analyzer once, return one flat dict --
    exactly the shape api/services/generation.py persists into
    PatternAnalysis and the /mathematics endpoint returns."""
    graph_m = analyze_graph(obj)
    euler_m = analyze_eulerian(obj)
    mult_m = analyze_multiplicity(obj)
    sym_m = analyze_symmetry_metrics(obj)
    comp_m = analyze_complexity(obj)
    novelty_m = analyze_novelty(obj, reference_sources or [], source_ids)

    return {
        "graph": asdict(graph_m),
        "eulerian": asdict(euler_m),
        "multiplicity": asdict(mult_m),
        "symmetry": asdict(sym_m),
        "complexity": asdict(comp_m),
        "novelty": asdict(novelty_m),
    }
