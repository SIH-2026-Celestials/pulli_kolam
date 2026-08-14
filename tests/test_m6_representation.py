"""Tests for experiments/m6_generation/representation.py: the sequence-
of-placements representation the M6 generator predicts/consumes."""

from __future__ import annotations

import networkx as nx

from engine.dataset import load_kolam
from engine.motifs import induce_motif_set_adaptive, interior_points
from experiments.m6_generation.representation import (
    EOS_MOTIF_ID,
    GenerationConfig,
    MotifVocabulary,
    PlacementToken,
    placements_from_sequence,
    sequence_from_placements,
)


def test_vocabulary_roundtrip_serialization():
    pattern = load_kolam("kolam19", 1)
    placements, _residual, _full = induce_motif_set_adaptive(pattern)
    motifs = [p.motif for p in placements]
    vocab = MotifVocabulary.build(motifs)

    d = vocab.to_dict()
    vocab2 = MotifVocabulary.from_dict(d)
    assert vocab2.size == vocab.size
    assert vocab2.id_to_motif == vocab.id_to_motif
    for m in motifs:
        assert vocab2.encode(m) == vocab.encode(m)


def test_vocabulary_unk_for_unseen_motif():
    vocab = MotifVocabulary.build([(((0, 0), (1, 0)),)])
    unseen = (((0, 0), (0, 1)),)
    assert vocab.encode(unseen) == 2  # UNK_MOTIF_ID


def test_vocabulary_max_size_truncates():
    motifs = [(((0, 0), (i, 0)),) for i in range(1, 20)]
    vocab = MotifVocabulary.build(motifs, max_size=10)
    assert vocab.size == 10  # 3 reserved + 7 real


def _normalize_to_origin(dots: set):
    """Real KolamPattern.dot_points are centered near (0,0) with negative
    coordinates -- sequence_from_placements requires origin-normalized,
    non-negative input (see its own docstring); this mirrors
    build_dataset.py's _normalize_to_origin for test purposes."""
    min_x = min(p[0] for p in dots)
    min_y = min(p[1] for p in dots)
    return {(x - min_x, y - min_y) for x, y in dots}, (min_x, min_y)


def test_sequence_roundtrip_preserves_placement_count():
    pattern = load_kolam("kolam19", 2)
    dots, (min_x, min_y) = _normalize_to_origin(pattern.dot_points)
    G = nx.MultiGraph()
    G.add_nodes_from(dots)
    for a, b in pattern.graph.edges():
        G.add_edge((a[0] - min_x, a[1] - min_y), (b[0] - min_x, b[1] - min_y))
    interior = interior_points(dots, radius=1)
    placements, _residual, _full = induce_motif_set_adaptive(G, interior_points=interior, dots_set=dots)
    motifs = [p.motif for p in placements]
    vocab = MotifVocabulary.build(motifs)

    tokens = sequence_from_placements(placements, vocab)
    n_expected_tokens = sum(len(p.points) for p in placements)
    assert len(tokens) == n_expected_tokens

    back = placements_from_sequence(tokens, vocab)
    assert len(back) == len(tokens)  # one MotifPlacement per token (single-point placements)


def test_placements_from_sequence_stops_at_eos():
    vocab = MotifVocabulary.build([(((0, 0), (1, 0)),)])
    tokens = [
        PlacementToken(motif_id=3, x=0, y=0, transform_id=0),
        PlacementToken.eos(),
        PlacementToken(motif_id=3, x=5, y=5, transform_id=0),  # must be ignored -- after EOS
    ]
    placements = placements_from_sequence(tokens, vocab)
    assert len(placements) == 1


def test_placements_from_sequence_skips_unk():
    vocab = MotifVocabulary.build([(((0, 0), (1, 0)),)])
    tokens = [PlacementToken(motif_id=2, x=0, y=0, transform_id=0)]  # UNK_MOTIF_ID
    placements = placements_from_sequence(tokens, vocab)
    assert placements == []


def test_generation_config_roundtrip():
    cfg = GenerationConfig(grid_width=7, grid_height=7, symmetry="rotational4", complexity=0.7, density=0.6, seed=42)
    cfg2 = GenerationConfig.from_dict(cfg.to_dict())
    assert cfg2 == cfg
