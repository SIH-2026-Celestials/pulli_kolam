"""M5 OBJECTIVES 1 + 9: a canonical, serializable structural
representation for a kolam, and a clean, framework-independent production
entry point for novel generation.

Deliberately has ZERO import of fastapi, api.*, or any web framework --
`generate_novel_kolams` is safe to call from a script, a notebook, a test,
or (if wired up) an API handler, without coupling this module to any of
them (OBJECTIVE 9's explicit requirement).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

import networkx as nx

from engine.symmetry import analyze_symmetry
from engine.validity import check_validity, diagnose_validity

if TYPE_CHECKING:
    from engine.generated_kolam import GeneratedKolam
    from engine.kolam_pattern import KolamPattern
    from engine.learned_scoring import ScorerBundle
    from engine.motifs import Motif

Point = tuple[int, int]


@dataclass
class StructuralRepresentation:
    """Canonical, JSON-serializable structural description of one kolam
    (real or generated). Every field is either directly observable
    (dots, edges) or a cheap deterministic derivation of the graph
    (degree distribution, Eulerian validity, symmetry coverage) -- no
    field here is a model output or a fabricated statistic.

    Fields intentionally track the exact list OBJECTIVE 1 specified:
    dot coordinates, lattice dimensions, graph nodes/edges, connected
    components, degree distribution, Eulerian validity, motifs,
    symmetry, stroke/path topology. `lattice_spacing`/`rotation` are
    included as explicit `None` (rather than omitted) when not
    applicable to a lattice-coordinate structure -- see their field
    docstrings -- so a caller can tell "not measured" from "measured as
    zero"."""

    dot_points: "list[list[int]]"  # [[x, y], ...] -- JSON has no tuple type
    lattice_width: int
    lattice_height: int
    lattice_spacing: "float | None"  # None: lattice-coordinate structures have unit spacing by construction, not a measured photo-pixel spacing (see engine.image_quality for that measurement on a real photo)
    rotation_deg: "float | None"  # None: not applicable to a lattice-coordinate structure; a real photo's estimated rotation is engine.image_quality.ImageQuality.estimated_rotation_deg
    edges: "list[list[list[int]]]"  # [[[ax,ay],[bx,by]], ...], one entry per EDGE INSTANCE (multiplicity preserved)
    n_nodes: int
    n_distinct_edges: int
    n_edge_instances: int
    connected_components: int
    largest_component_covers_all_nodes: bool
    degree_distribution: "dict[str, int]"  # {"degree": count}, keys are strings for JSON compatibility
    n_odd_degree_nodes: int
    is_eulerian_circuit: bool
    has_eulerian_path: bool
    is_valid_single_stroke: bool
    symmetry_coverage: "float | None"  # engine.symmetry.analyze_symmetry's dominant-motif D4 coverage fraction
    dot_trace: "list[list[int]] | None"  # ordered stroke/path topology, None if not Eulerian (see engine.generation.reconstruct_dot_trace)
    source_id: "str | None" = None  # "<collection>#<pattern_id>" if this came from a real pattern, else None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "StructuralRepresentation":
        return StructuralRepresentation(**d)


def build_representation(
    source: "KolamPattern | GeneratedKolam | nx.MultiGraph",
    dot_points: "set[Point] | None" = None,
) -> StructuralRepresentation:
    """Build a StructuralRepresentation from any of this project's
    existing structural types -- KolamPattern (real data), GeneratedKolam
    (a generation candidate), or a raw nx.MultiGraph (`dot_points`
    required in that case, since a bare graph doesn't carry a dot set
    distinct from its node set the way the other two types do)."""
    source_id = None
    if isinstance(source, nx.MultiGraph):
        # NOTE: nx.Graph objects have their OWN unrelated `.graph` attribute
        # (networkx's built-in graph-level metadata dict) -- an
        # isinstance check, not hasattr(source, "graph"), is required to
        # tell a raw graph apart from KolamPattern/GeneratedKolam, both of
        # which store this project's dot graph under that same attribute
        # name.
        graph = source
        if dot_points is None:
            raise TypeError("dot_points is required when source is a raw nx.MultiGraph")
        dots = dot_points
    else:
        graph: nx.MultiGraph = source.graph
        dots = getattr(source, "dot_points", set(graph.nodes()))
        if hasattr(source, "collection") and hasattr(source, "pattern_id"):
            source_id = f"{source.collection}#{source.pattern_id}"

    validity = check_validity(graph) if graph.number_of_nodes() else {
        "connected_components": 0, "is_eulerian_circuit": False, "has_eulerian_path": False,
        "largest_component_covers_all_nodes": False,
    }
    is_valid = validity["largest_component_covers_all_nodes"] and (
        validity["is_eulerian_circuit"] or validity["has_eulerian_path"]
    )

    degree_counts: Counter = Counter(dict(graph.degree()).values())
    n_odd = sum(count for degree, count in degree_counts.items() if degree % 2 == 1)

    symmetry_coverage = None
    if dots:
        try:
            _motif, coverage, _tp = analyze_symmetry(graph, dots=set(dots), radius=1)
            symmetry_coverage = coverage
        except Exception:
            symmetry_coverage = None

    dot_trace = None
    trace_attr = getattr(source, "dot_trace", None)
    if trace_attr is not None:
        dot_trace = [[int(x), int(y)] for x, y in trace_attr]
    elif is_valid:
        from engine.generation import reconstruct_dot_trace

        trace = reconstruct_dot_trace(graph)
        dot_trace = [[int(x), int(y)] for x, y in trace] if trace else None

    xs = [p[0] for p in dots] if dots else [0]
    ys = [p[1] for p in dots] if dots else [0]

    return StructuralRepresentation(
        dot_points=[[int(x), int(y)] for x, y in sorted(dots)],
        lattice_width=int(max(xs) - min(xs) + 1) if dots else 0,
        lattice_height=int(max(ys) - min(ys) + 1) if dots else 0,
        lattice_spacing=None,
        rotation_deg=None,
        edges=[[[int(a[0]), int(a[1])], [int(b[0]), int(b[1])]] for a, b in graph.edges()],
        n_nodes=graph.number_of_nodes(),
        n_distinct_edges=len({frozenset(e) for e in graph.edges()}),
        n_edge_instances=graph.number_of_edges(),
        connected_components=validity["connected_components"],
        largest_component_covers_all_nodes=validity["largest_component_covers_all_nodes"],
        degree_distribution={str(k): v for k, v in sorted(degree_counts.items())},
        n_odd_degree_nodes=n_odd,
        is_eulerian_circuit=validity["is_eulerian_circuit"],
        has_eulerian_path=validity["has_eulerian_path"],
        is_valid_single_stroke=is_valid,
        symmetry_coverage=symmetry_coverage,
        dot_trace=dot_trace,
        source_id=source_id,
    )


def generate_novel_kolams(
    representation: StructuralRepresentation,
    num_candidates: int = 100,
    seed: "int | None" = None,
    motif_library: "list[Motif] | None" = None,
    scorer: "ScorerBundle | None" = None,
    n_restarts: int = 6,
    reference_sources: "list[KolamPattern] | None" = None,
) -> "list[dict]":
    """OBJECTIVE 9's production contract: representation in, ranked
    structured candidates out. Framework-independent (see module
    docstring) -- api/main.py's /api/v1/generate endpoint calls this
    same function rather than reimplementing generation, and so does
    experiments/m5_generation/run_benchmark.py's benchmark loop.

    `motif_library` defaults to a library induced from `representation`
    itself (self-consistent: generate variations of the SAME pattern's
    own motif grammar) if not given -- requires `representation` to carry
    real edges to induce from (an empty/edgeless representation raises).

    Each returned dict contains: candidate_id, seed, structural
    representation (`.to_dict()`), validity_score, novelty_score,
    source_id (nearest comparable source, if any), rank (0 = best, sorted
    validity_score desc then novelty_score desc). Invalid candidates are
    NOT dropped from the list (the caller can filter on `is_valid`
    themselves) -- OBJECTIVE 2 says "reject invalid candidates" for what
    the caller treats as usable output; this function reports everything
    it tried, honestly, rather than hiding failures.
    """
    from engine.learned_generation import generate_novel_kolam_learned
    from engine.learned_scoring import load_scorer
    from engine.novelty import per_candidate_novelty

    if scorer is None:
        scorer = load_scorer()

    dots = {(p[0], p[1]) for p in representation.dot_points}

    if motif_library is None:
        from engine.motifs import induce_motif_set_adaptive, interior_points
        from engine.novel_generation import extract_motif_library

        edges_as_pairs = [((a[0], a[1]), (b[0], b[1])) for a, b in representation.edges]
        if not edges_as_pairs:
            raise ValueError("representation has no edges to induce a motif library from; pass motif_library explicitly")
        g = nx.MultiGraph()
        g.add_nodes_from(dots)
        for a, b in edges_as_pairs:
            g.add_edge(a, b)
        interior = interior_points(dots, radius=1)
        placements, _residual, _full = induce_motif_set_adaptive(g, interior_points=interior, dots_set=dots)
        motif_library = extract_motif_library(placements)

    base_seed = 0 if seed is None else seed
    candidates_gk: "list[GeneratedKolam]" = []
    runs = []
    for i in range(num_candidates):
        run = generate_novel_kolam_learned(
            motif_library, dots, scorer=scorer, n_restarts=n_restarts, seed=base_seed + i,
        )
        candidates_gk.append(run.candidate)
        runs.append(run)

    novelty_rows = per_candidate_novelty(
        candidates_gk,
        reference_sources or [],
        candidate_ids=[str(i) for i in range(len(candidates_gk))],
    )

    results = []
    for i, (gk, run, nrow) in enumerate(zip(candidates_gk, runs, novelty_rows)):
        rep = build_representation(gk)
        results.append(
            {
                "candidate_id": str(i),
                "seed": run.seed,
                "representation": rep.to_dict(),
                "is_valid": gk.is_valid,
                "validity_score": nrow["validity_score"],
                "novelty_score": nrow["novelty_score"],
                "source_id": nrow["source_id"],
                "generation_latency_seconds": run.latency_seconds,
                "n_restarts_used": len(run.restarts),
                "repair_edges_applied": len(run.repair_applied),
            }
        )

    results.sort(key=lambda r: (-r["validity_score"], -r["novelty_score"]))
    for rank, r in enumerate(results):
        r["rank"] = rank

    return results


def generate_kolam(
    motif_library: "list[Motif]",
    dots: "set[Point]",
    seed: "int | None" = None,
    n_restarts: int = 6,
    scorer: "ScorerBundle | None" = None,
    max_multiplicity: int = 2,
    novelty_sources: "list[KolamPattern] | None" = None,
) -> dict:
    """Single-candidate production entry point: one seed in, one
    generated structure + validity + novelty + SVG render out. Lower-level
    than generate_novel_kolams (which sweeps num_candidates and ranks
    them) -- this is the one-shot call a caller with a specific seed and
    a specific target lattice/motif library actually wants (e.g.
    experiments/m5_generation/generate_and_render.py's per-attempt loop),
    without paying for a batch of candidates it doesn't need.

    Returns a plain dict (JSON-serializable except for `render.svg`,
    which is a string):
      success        : bool, same as candidate.is_valid -- whether the
                       structure passed engine.validity's hard gate
                       (after bounded multiplicity repair, same as
                       generate_novel_kolam_learned).
      metrics        : diagnose_validity's fields (connected_components,
                       n_nodes_outside_largest_component,
                       n_odd_degree_nodes, total_correction_cost) plus
                       edge_multiplicity_max, n_placements,
                       n_restarts_used, repair_edges_applied,
                       latency_seconds, seed.
      validity       : engine.validity.check_validity's raw dict.
      novelty        : engine.novelty.novelty_report's dict, computed
                       against `novelty_sources` (empty list if none
                       given -- reported honestly as all-None rates,
                       never fabricated).
      render         : {"svg": <str>} -- engine.render.render_generated_kolam_svg's
                       output, always present (even for an invalid
                       candidate, which renders dots-only + an "INVALID"
                       label -- see engine.render's own module docstring).
    """
    from engine.learned_generation import generate_novel_kolam_learned
    from engine.learned_scoring import load_scorer
    from engine.novelty import novelty_report
    from engine.render import render_generated_kolam_svg

    if scorer is None:
        scorer = load_scorer()

    run = generate_novel_kolam_learned(
        motif_library, dots, scorer=scorer, max_multiplicity=max_multiplicity,
        n_restarts=n_restarts, seed=seed,
    )
    candidate = run.candidate
    diag = candidate.diagnosis
    edge_mult_max = max(candidate.edge_multiplicity.values()) if candidate.edge_multiplicity else 0

    metrics = {
        "connected_components": diag["connected_components"],
        "n_nodes_outside_largest_component": diag["n_nodes_outside_largest_component"],
        "n_odd_degree_nodes": diag["n_odd_degree_nodes"],
        "total_correction_cost": diag["total_correction_cost"],
        "edge_multiplicity_max": edge_mult_max,
        "n_placements": len(candidate.placements),
        "n_restarts_used": len(run.restarts),
        "repair_edges_applied": len(run.repair_applied),
        "latency_seconds": run.latency_seconds,
        "seed": run.seed,
    }

    novelty = novelty_report([candidate], novelty_sources or [])

    return {
        "success": candidate.is_valid,
        "metrics": metrics,
        "validity": candidate.validity_result,
        "novelty": novelty,
        "render": {"svg": render_generated_kolam_svg(candidate)},
    }
