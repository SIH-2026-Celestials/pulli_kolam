"""Tests for engine/generation_contract.py (M5 OBJECTIVES 1 + 9):
StructuralRepresentation serialization and the framework-independent
generate_novel_kolams production entry point."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from engine.dataset import load_kolam
from engine.generation_contract import StructuralRepresentation, build_representation, generate_novel_kolams
from engine.learned_scoring import PlacementScorer, ScorerBundle, N_FEATURES
import numpy as np
import torch

CHECKPOINT = Path(__file__).resolve().parent.parent / "experiments" / "m5_generation" / "checkpoints" / "placement_scorer.pt"


def _always_accept_scorer() -> ScorerBundle:
    model = PlacementScorer(n_features=N_FEATURES, hidden=8)
    with torch.no_grad():
        for p in model.parameters():
            p.zero_()
        model.net[-1].bias.fill_(50.0)
    return ScorerBundle(model=model, feature_mean=np.zeros(N_FEATURES, dtype=np.float32),
                         feature_std=np.ones(N_FEATURES, dtype=np.float32), metadata={})


def test_build_representation_from_kolam_pattern():
    pattern = load_kolam("kolam19", 1)
    rep = build_representation(pattern)
    assert rep.n_nodes == pattern.n_dots
    assert rep.source_id == "kolam19#1"
    assert rep.is_valid_single_stroke is True  # real source data is verified single-stroke
    assert len(rep.dot_points) == rep.n_nodes


def test_representation_roundtrip_serialization():
    pattern = load_kolam("kolam19", 2)
    rep = build_representation(pattern)
    d = rep.to_dict()
    import json

    encoded = json.dumps(d)  # must be plain-JSON-serializable, no tuples/sets/numpy types
    decoded = json.loads(encoded)
    rep2 = StructuralRepresentation.from_dict(decoded)
    assert rep2.n_nodes == rep.n_nodes
    assert rep2.dot_points == rep.dot_points
    assert rep2.degree_distribution == rep.degree_distribution


def test_build_representation_from_raw_graph_requires_dot_points():
    g = nx.MultiGraph()
    g.add_edge((0, 0), (1, 0))
    with pytest.raises(TypeError):
        build_representation(g)

    rep = build_representation(g, dot_points={(0, 0), (1, 0)})
    assert rep.n_nodes == 2
    assert rep.n_distinct_edges == 1


def test_generate_novel_kolams_deterministic_given_seed():
    pattern = load_kolam("kolam19", 1)
    rep = build_representation(pattern)
    scorer = _always_accept_scorer()
    library = [(((0, 0), (1, 0)),)]

    r1 = generate_novel_kolams(rep, num_candidates=2, seed=5, motif_library=library, scorer=scorer, n_restarts=1)
    r2 = generate_novel_kolams(rep, num_candidates=2, seed=5, motif_library=library, scorer=scorer, n_restarts=1)
    assert [c["representation"]["n_distinct_edges"] for c in r1] == [c["representation"]["n_distinct_edges"] for c in r2]


def test_generate_novel_kolams_is_ranked_and_never_drops_invalid():
    pattern = load_kolam("kolam19", 3)
    rep = build_representation(pattern)
    scorer = _always_accept_scorer()
    library = [(((0, 0), (1, 0)),)]

    results = generate_novel_kolams(rep, num_candidates=3, seed=1, motif_library=library, scorer=scorer, n_restarts=1)
    assert len(results) == 3
    assert [r["rank"] for r in results] == [0, 1, 2]
    # ranking is sorted descending by validity_score then novelty_score
    scores = [(r["validity_score"], r["novelty_score"]) for r in results]
    assert scores == sorted(scores, reverse=True)
    # every candidate reported, including invalid ones (never silently dropped)
    for r in results:
        assert "is_valid" in r and "candidate_id" in r


def test_generate_novel_kolams_requires_edges_or_explicit_library():
    empty_rep = StructuralRepresentation(
        dot_points=[[0, 0], [1, 0]], lattice_width=2, lattice_height=1, lattice_spacing=None,
        rotation_deg=None, edges=[], n_nodes=2, n_distinct_edges=0, n_edge_instances=0,
        connected_components=2, largest_component_covers_all_nodes=False, degree_distribution={"0": 2},
        n_odd_degree_nodes=0, is_eulerian_circuit=False, has_eulerian_path=False,
        is_valid_single_stroke=False, symmetry_coverage=None, dot_trace=None,
    )
    with pytest.raises(ValueError):
        generate_novel_kolams(empty_rep, num_candidates=1, scorer=_always_accept_scorer())
