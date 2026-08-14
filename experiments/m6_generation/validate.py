"""M6 Phase 5: structural validation + assembly for a raw generated
token sequence. Thin wrapper -- every actual check/repair is
engine.validity / engine.learned_generation, reused unmodified (per
ARCHITECTURE.md section 7).

"Do NOT call a generated structure valid just because the neural model
emitted it. Do NOT call it valid just because it renders." -- neither
happens here: `assemble_and_validate` always runs the SAME hard gate
(engine.validity.check_validity) every other structure in this
repository is judged by, on the ACTUAL assembled graph, after bounded
repair, never on the raw token sequence's say-so.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.generated_kolam import GeneratedKolam
from engine.generation import build_candidate_graph, reconstruct_dot_trace
from engine.learned_generation import repair_multiplicity
from engine.validity import check_validity, diagnose_validity

from experiments.m6_generation.representation import MotifVocabulary, PlacementToken, placements_from_sequence

Point = tuple[int, int]


@dataclass
class AssembledCandidate:
    candidate: GeneratedKolam
    n_raw_tokens: int
    n_placements_used: int
    n_tokens_dropped_unk_or_pad: int
    repair_applied: list
    hit_max_len_without_eos: bool


def assemble_and_validate(
    raw_tokens: "list[tuple[int, int, int, int]]",
    vocab: MotifVocabulary,
    dot_points: "set[Point]",
    hit_max_len_without_eos: bool = False,
    allow_repair: bool = True,
) -> AssembledCandidate:
    """raw_tokens: (motif_id, x, y, transform_id) tuples from
    KolamSequenceGenerator.generate (EOS already excluded by that
    method). Builds a real nx.MultiGraph via
    engine.generation.build_candidate_graph (the SAME assembly path
    M5's own generation uses -- no second graph-construction method),
    runs the hard validity gate, and -- only if still invalid -- applies
    the SAME bounded, geometry-safe multiplicity repair M5 uses (never
    invents new edges)."""
    tokens = [PlacementToken(m, x, y, t) for m, x, y, t in raw_tokens]
    placements = placements_from_sequence(tokens, vocab)
    n_dropped = len(tokens) - len(placements)

    graph = build_candidate_graph(placements, dot_points)
    validity_result = check_validity(graph)
    diagnosis = diagnose_validity(graph)
    is_valid = validity_result["largest_component_covers_all_nodes"] and (
        validity_result["is_eulerian_circuit"] or validity_result["has_eulerian_path"]
    )
    dot_trace = reconstruct_dot_trace(graph) if is_valid else None

    from collections import Counter

    edge_multiplicity = dict(Counter(frozenset(e) for e in graph.edges()))
    candidate = GeneratedKolam(
        dot_points=set(dot_points), graph=graph, placements=list(placements),
        edge_multiplicity=edge_multiplicity, validity_result=validity_result,
        diagnosis=diagnosis, dot_trace=dot_trace,
    )

    applied = []
    if allow_repair and not candidate.is_valid:
        candidate, applied = repair_multiplicity(candidate)

    return AssembledCandidate(
        candidate=candidate, n_raw_tokens=len(raw_tokens), n_placements_used=len(placements),
        n_tokens_dropped_unk_or_pad=n_dropped, repair_applied=applied,
        hit_max_len_without_eos=hit_max_len_without_eos,
    )
