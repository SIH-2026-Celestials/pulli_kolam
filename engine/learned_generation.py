"""M5: learned-scorer-guided structural generation.

Replaces engine.novel_generation.select_novel_placements's single
deterministic greedy pass (measured 0/120 to 1/120 valid, see
docs/M4_2_GENERATION.md) with:

  1. MULTI-RESTART GUIDED SEARCH: `DEFAULT_N_RESTARTS` independent
     greedy passes over the SAME candidate space (point x motif x D4
     transform), each in a different deterministic shuffled order, each
     accepting a candidate iff engine.learned_scoring's imitation-trained
     MLP scores it above threshold (instead of the old hand-tuned linear
     score). Different orders explore different local optima of the same
     greedy structure -- a cheap, honest stand-in for a real beam search
     that needs no new search infrastructure and stays within this
     project's existing "single accept/reject pass" discipline per
     restart. The restart with the best resulting structural quality
     (valid first, then least fragmented, then fewest odd-degree nodes)
     is kept; every restart's outcome is reported, not just the winner.

  2. BOUNDED, GEOMETRY-SAFE REPAIR: if the best restart is connected
     (largest component already covers every dot) but not Eulerian, the
     remaining odd-degree nodes are closed by INCREASING THE MULTIPLICITY
     OF EDGES THAT ALREADY EXIST in the candidate, along the same
     shortest paths engine.validity.diagnose_validity already computes
     (standard Chinese-Postman route doubling). This never invents new
     lattice geometry -- see repair_multiplicity's docstring for why
     multiplicity-only repair is structurally consistent with real kolam
     data. If the candidate is still fragmented across multiple
     components, repair is skipped and the result is reported honestly
     as still invalid -- this module does not merge components by
     inventing an edge with no motif/geometry justification.

Every step reuses existing, tested primitives (engine.generation.generate_kolam,
engine.validity.check_validity/diagnose_validity, engine.novel_generation's
private helpers for candidate stamping/scoring bookkeeping) -- nothing
here reimplements graph construction, validity checking, or trace
reconstruction.
"""

from __future__ import annotations

import random
import time
from collections import Counter
from dataclasses import dataclass

from engine.generated_kolam import GeneratedKolam
from engine.generation import build_candidate_graph, reconstruct_dot_trace
from engine.learned_scoring import ScorerBundle, extract_features, load_scorer
from engine.motifs import Motif, MotifPlacement, interior_points
from engine.novel_generation import (
    DEFAULT_MAX_MULTIPLICITY,
    DEFAULT_MAX_PLACEMENTS,
    _UnionFind,
    _connectivity_effect,
    _parity_effect,
)
from engine.symmetry import D4_TRANSFORMS
from engine.validity import check_validity, diagnose_validity

Point = tuple[int, int]

DEFAULT_N_RESTARTS = 6
ACCEPT_THRESHOLD = 0.5
DEFAULT_REPAIR_MAX_MULTIPLICITY = 3  # bounded override for CLOSING repair only, see repair_multiplicity


def _precompute_rel_edges(motif_library: list[Motif]) -> dict:
    """(motif, transform) -> transformed relative-edge tuple, computed
    ONCE per distinct pair rather than once per (point, motif, transform)
    candidate. `apply_transform`'s result depends only on (motif,
    transform), never on the stamping point -- profiling the guided
    search (which evaluates tens of thousands of candidates per restart)
    showed re-deriving this per point was a large fraction of per-restart
    time for no reason, since a lattice interior routinely has 100+
    points sharing the same (motif, transform) pair."""
    from engine.symmetry import apply_transform

    cache = {}
    for motif in motif_library:
        for transform in sorted(D4_TRANSFORMS):
            cache[(motif, transform)] = motif if transform == "identity" else apply_transform(transform, motif)
    return cache


def _stamp_with_cache(rel_edges, point: Point, dots: set[Point]) -> Counter:
    """Same semantics as engine.novel_generation._stamp_contribution, but
    takes already-transformed `rel_edges` (from _precompute_rel_edges)
    instead of re-deriving them from (motif, transform) every call."""
    contribution: Counter = Counter()
    cx, cy = point
    for (dx1, dy1), (dx2, dy2) in rel_edges:
        a = (cx + dx1, cy + dy1)
        b = (cx + dx2, cy + dy2)
        if a in dots and b in dots:
            contribution[frozenset({a, b})] += 1
    return contribution


def _single_restart_placements(
    motif_library: list[Motif],
    dots: set[Point],
    scorer: ScorerBundle,
    rng: random.Random,
    max_multiplicity: int,
    max_placements: int,
) -> list[MotifPlacement]:
    """One guided greedy pass: same accept/reject structure as
    engine.novel_generation.select_novel_placements, but the accept
    decision is the learned scorer's probability instead of a fixed
    hand-tuned score, and the candidate order is shuffled per-restart."""
    interior = interior_points(dots, radius=1)
    rel_edges_cache = _precompute_rel_edges(motif_library)
    candidate_keys = [
        (point, motif, transform)
        for point in sorted(interior)
        for motif in motif_library
        for transform in sorted(D4_TRANSFORMS)
    ]
    rng.shuffle(candidate_keys)

    accumulated: Counter = Counter()
    degree: Counter = Counter()
    uf = _UnionFind(dots)
    touched_dots: set = set()
    any_real_structure_exists = False
    n_dots = len(dots)
    selected: dict[tuple[Motif, str], dict] = {}
    n_placed = 0

    for point, motif, transform in candidate_keys:
        if n_placed >= max_placements:
            break
        contribution = _stamp_with_cache(rel_edges_cache[(motif, transform)], point, dots)
        if not contribution:
            continue
        if any(accumulated.get(e, 0) + c > max_multiplicity for e, c in contribution.items()):
            continue

        conn_effect = _connectivity_effect(uf, contribution)
        parity_effect = _parity_effect(degree, contribution)
        progress_frac = len(touched_dots) / n_dots if n_dots else 0.0
        n_odd = sum(1 for d in degree.values() if d % 2 == 1)
        global_odd_frac = n_odd / n_dots if n_dots else 0.0

        feats = extract_features(
            motif_len=len(motif),
            contribution=contribution,
            degree_before=degree,
            connectivity_effect=conn_effect,
            parity_effect=parity_effect,
            any_real_structure_exists=any_real_structure_exists,
            progress_frac=progress_frac,
            global_odd_frac=global_odd_frac,
        )
        if scorer.score(feats) <= ACCEPT_THRESHOLD:
            continue

        for edge, count in contribution.items():
            accumulated[edge] += count
            a, b = tuple(edge)
            degree[a] += count
            degree[b] += count
            touched_dots.add(a)
            touched_dots.add(b)
            uf.union(a, b)
        key = (motif, transform)
        entry = selected.setdefault(key, {"points": [], "edges": set()})
        entry["points"].append(point)
        entry["edges"] |= set(contribution.keys())
        n_placed += 1
        any_real_structure_exists = True

    placements = []
    for (motif, transform), entry in selected.items():
        transforms = {} if transform == "identity" else {p: transform for p in entry["points"]}
        placements.append(
            MotifPlacement(motif=motif, points=entry["points"], transforms=transforms, new_edges=entry["edges"])
        )
    return placements


def _build_candidate(placements: list[MotifPlacement], dots: set[Point]) -> GeneratedKolam:
    """Same pipeline engine.generation.generate_kolam runs, inlined here
    only to avoid importing that module's public entry point twice with
    identical semantics -- validity/diagnosis/trace all come from the
    same unmodified functions every other generation path uses."""
    graph = build_candidate_graph(placements, dots)
    validity_result = check_validity(graph)
    diagnosis = diagnose_validity(graph)
    is_valid = validity_result["largest_component_covers_all_nodes"] and (
        validity_result["is_eulerian_circuit"] or validity_result["has_eulerian_path"]
    )
    dot_trace = reconstruct_dot_trace(graph) if is_valid else None
    edge_multiplicity = dict(Counter(frozenset(e) for e in graph.edges()))
    return GeneratedKolam(
        dot_points=set(dots),
        graph=graph,
        placements=list(placements),
        edge_multiplicity=edge_multiplicity,
        validity_result=validity_result,
        diagnosis=diagnosis,
        dot_trace=dot_trace,
    )


def _candidate_quality(candidate: GeneratedKolam) -> tuple:
    """Sort key, ascending = better: valid candidates always beat invalid
    ones; among invalid candidates, fewer nodes stranded outside the
    largest component beats more, then fewer odd-degree nodes, then lower
    total Chinese-Postman correction cost."""
    d = candidate.diagnosis
    return (
        0 if candidate.is_valid else 1,
        d["n_nodes_outside_largest_component"],
        d["n_odd_degree_nodes"],
        d["total_correction_cost"],
    )


def search_best_candidate(
    motif_library: list[Motif],
    dot_points: set[Point],
    scorer: ScorerBundle | None = None,
    n_restarts: int = DEFAULT_N_RESTARTS,
    max_multiplicity: int = DEFAULT_MAX_MULTIPLICITY,
    max_placements: int = DEFAULT_MAX_PLACEMENTS,
    seed: int | None = None,
) -> tuple[GeneratedKolam, list[dict]]:
    """Run `n_restarts` independent guided passes (different deterministic
    shuffles of the same candidate space, same seed -> same outcome) and
    keep the structurally best result (see _candidate_quality). Stops
    early the moment any restart is already fully valid -- no reason to
    keep searching once the hard gate is met."""
    if scorer is None:
        scorer = load_scorer()
    dots = set(dot_points)
    base_seed = 0 if seed is None else seed

    best: GeneratedKolam | None = None
    best_key = None
    restarts_info = []
    for i in range(n_restarts):
        rng = random.Random(f"{base_seed}:{i}")
        placements = _single_restart_placements(motif_library, dots, scorer, rng, max_multiplicity, max_placements)
        candidate = _build_candidate(placements, dots)
        key = _candidate_quality(candidate)
        restarts_info.append(
            {
                "restart": i,
                "is_valid": candidate.is_valid,
                "connected_components": candidate.diagnosis["connected_components"],
                "n_odd_degree_nodes": candidate.diagnosis["n_odd_degree_nodes"],
                "n_placements": len(candidate.placements),
            }
        )
        if best is None or key < best_key:
            best, best_key = candidate, key
        if candidate.is_valid:
            break

    return best, restarts_info


def repair_multiplicity(
    candidate: GeneratedKolam, max_repair_multiplicity: int = DEFAULT_REPAIR_MAX_MULTIPLICITY
) -> tuple[GeneratedKolam, list[dict]]:
    """Bounded closing repair: only increases the multiplicity of edges
    ALREADY PRESENT in `candidate.graph`, along the shortest paths between
    remaining odd-degree nodes that engine.validity.diagnose_validity
    already computes (standard Chinese-Postman / Route Inspection route
    doubling on the largest component). This never adds an edge whose
    endpoints weren't already connected by the placed motif structure --
    it is not "inventing geometry," it is the same multi-strand mechanism
    real kolam data legitimately uses (docs/DATA_FORMAT.md: verified
    strand multiplicity of 1 or 2 occurs in real patterns).

    Does NOT merge separate connected components -- doing so would
    require a genuinely new edge with no motif/geometry justification, so
    if the candidate has nodes outside its largest component, this
    returns it UNCHANGED (still invalid), reported honestly rather than
    silently "fixed." Also bounded by `max_repair_multiplicity`: a
    correction that would push an edge's strand count past the cap is
    skipped, not forced through.
    """
    if candidate.is_valid:
        return candidate, []
    diagnosis = candidate.diagnosis
    if diagnosis["n_nodes_outside_largest_component"] > 0:
        return candidate, []

    graph = candidate.graph.copy()
    existing_mult = Counter(frozenset(e) for e in graph.edges())
    applied = []
    for correction in diagnosis["corrections"]:
        for u, v in correction["path_edges"]:
            e = frozenset({u, v})
            cur = existing_mult.get(e, 0)
            if cur >= max_repair_multiplicity:
                continue
            graph.add_edge(u, v)
            existing_mult[e] = cur + 1
            applied.append({"edge": [list(u), list(v)], "new_multiplicity": cur + 1})

    validity_result = check_validity(graph)
    new_diagnosis = diagnose_validity(graph)
    is_valid = validity_result["largest_component_covers_all_nodes"] and (
        validity_result["is_eulerian_circuit"] or validity_result["has_eulerian_path"]
    )
    dot_trace = reconstruct_dot_trace(graph) if is_valid else None
    edge_multiplicity = dict(Counter(frozenset(e) for e in graph.edges()))

    repaired = GeneratedKolam(
        dot_points=set(candidate.dot_points),
        graph=graph,
        placements=list(candidate.placements),
        edge_multiplicity=edge_multiplicity,
        validity_result=validity_result,
        diagnosis=new_diagnosis,
        dot_trace=dot_trace,
    )
    return repaired, applied


@dataclass
class GenerationRun:
    candidate: GeneratedKolam
    seed: int
    n_restarts: int
    restarts: list[dict]
    repair_applied: list[dict]
    scorer_metadata: dict
    latency_seconds: float


def generate_novel_kolam_learned(
    motif_library: list[Motif],
    dot_points: set[Point],
    scorer: ScorerBundle | None = None,
    max_multiplicity: int = DEFAULT_MAX_MULTIPLICITY,
    n_restarts: int = DEFAULT_N_RESTARTS,
    allow_repair: bool = True,
    repair_max_multiplicity: int = DEFAULT_REPAIR_MAX_MULTIPLICITY,
    seed: int | None = None,
) -> GenerationRun:
    """The full M5 pipeline: motif library + target lattice -> learned-
    scorer-guided multi-restart search -> bounded multiplicity repair ->
    GenerationRun. Deterministic given the same seed; different seeds
    explore different restart orderings and can produce different valid
    (or differently-invalid) candidates."""
    t0 = time.time()
    if scorer is None:
        scorer = load_scorer()
    candidate, restarts_info = search_best_candidate(
        motif_library, dot_points, scorer=scorer, n_restarts=n_restarts,
        max_multiplicity=max_multiplicity, seed=seed,
    )
    applied = []
    if allow_repair and not candidate.is_valid:
        candidate, applied = repair_multiplicity(candidate, repair_max_multiplicity)

    return GenerationRun(
        candidate=candidate,
        seed=0 if seed is None else seed,
        n_restarts=n_restarts,
        restarts=restarts_info,
        repair_applied=applied,
        scorer_metadata=scorer.metadata,
        latency_seconds=time.time() - t0,
    )
