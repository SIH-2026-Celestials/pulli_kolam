"""Tests for experiments/m6_generation/validate.py's assemble_and_validate:
must never call a structure valid just because tokens were emitted, and
must reuse engine.validity's hard gate unmodified."""

from __future__ import annotations

import networkx as nx

from engine.dataset import load_kolam
from engine.motifs import induce_motif_set_adaptive, interior_points
from engine.validity import check_validity
from experiments.m6_generation.representation import MotifVocabulary, sequence_from_placements
from experiments.m6_generation.validate import assemble_and_validate


def _real_pattern_tokens_and_vocab():
    """sequence_from_placements requires origin-normalized, non-negative
    coordinates (real KolamPattern.dot_points are centered near (0,0)
    with negative values) -- normalize first, same as build_dataset.py's
    own _normalize_to_origin, so `pattern` here is a NORMALIZED
    KolamPattern-shaped stand-in (graph + dot_points only, the two
    fields assemble_and_validate/induce_motif_set_adaptive need)."""
    raw = load_kolam("kolam19", 1)
    min_x = min(p[0] for p in raw.dot_points)
    min_y = min(p[1] for p in raw.dot_points)
    dots = {(x - min_x, y - min_y) for x, y in raw.dot_points}
    G = nx.MultiGraph()
    G.add_nodes_from(dots)
    for a, b in raw.graph.edges():
        G.add_edge((a[0] - min_x, a[1] - min_y), (b[0] - min_x, b[1] - min_y))

    interior = interior_points(dots, radius=1)
    placements, _residual, _full = induce_motif_set_adaptive(G, interior_points=interior, dots_set=dots)
    vocab = MotifVocabulary.build([p.motif for p in placements])
    tokens = sequence_from_placements(placements, vocab)

    class _NormalizedPattern:
        graph = G
        dot_points = dots

    return _NormalizedPattern(), tokens, vocab


def test_assemble_and_validate_reconstructs_real_pattern_structure():
    pattern, tokens, vocab = _real_pattern_tokens_and_vocab()
    raw = [(t.motif_id, t.x, t.y, t.transform_id) for t in tokens]
    result = assemble_and_validate(raw, vocab, pattern.dot_points)
    # Real pattern's own induced motifs should reconstruct SOMETHING with
    # real edges -- not necessarily bit-identical (induce_motif_set_adaptive
    # itself may not reach fully_covered), but a real, non-empty structure.
    assert result.candidate.graph.number_of_edges() > 0
    assert result.n_placements_used == len(tokens)


def test_empty_token_sequence_is_invalid_not_silently_accepted():
    _pattern, _tokens, vocab = _real_pattern_tokens_and_vocab()
    dots = {(0, 0), (1, 0), (0, 1), (1, 1)}
    result = assemble_and_validate([], vocab, dots)
    assert result.candidate.is_valid is False
    assert result.candidate.validity_result == check_validity(result.candidate.graph)


def test_unk_only_sequence_produces_no_placements():
    _pattern, _tokens, vocab = _real_pattern_tokens_and_vocab()
    dots = {(0, 0), (1, 0), (0, 1), (1, 1)}
    raw = [(2, 0, 0, 0), (2, 1, 1, 0)]  # UNK_MOTIF_ID == 2
    result = assemble_and_validate(raw, vocab, dots)
    assert result.n_placements_used == 0
    assert result.candidate.is_valid is False


def test_validity_result_matches_independent_check_validity_call():
    pattern, tokens, vocab = _real_pattern_tokens_and_vocab()
    raw = [(t.motif_id, t.x, t.y, t.transform_id) for t in tokens]
    result = assemble_and_validate(raw, vocab, pattern.dot_points, allow_repair=False)
    assert result.candidate.validity_result == check_validity(result.candidate.graph)
