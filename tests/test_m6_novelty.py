"""Tests for experiments/m6_generation/novelty.py's structural distance
combination -- must NOT be pixel-hash-based, must be zero for identical
stats and positive for different ones."""

from __future__ import annotations

import networkx as nx

from experiments.m6_generation.novelty import StructuralStats, nearest_training_novelty, structural_distance


def _stats(n_dots=10, n_edges=12, sym=0.3, complexity=0.5, density=0.5, degree_hist=None):
    return StructuralStats(
        n_dots=n_dots, n_distinct_edges=n_edges, n_edge_instances=n_edges,
        symmetry_coverage=sym, complexity=complexity, density=density,
        degree_histogram=degree_hist or {},
    )


def test_identical_stats_have_zero_distance():
    a = _stats()
    b = _stats()
    d = structural_distance(a, b)
    assert d["combined_distance"] == 0.0
    assert d["topology_distance"] == 0.0
    assert d["symmetry_distance"] == 0.0


def test_different_stats_have_positive_distance():
    a = _stats(n_dots=10, n_edges=12)
    b = _stats(n_dots=40, n_edges=60)
    d = structural_distance(a, b)
    assert d["combined_distance"] > 0.0
    assert d["topology_distance"] > 0.0


def test_distance_is_bounded_in_zero_one():
    a = _stats(n_dots=5, n_edges=3, sym=0.0, complexity=0.0, density=0.0)
    b = _stats(n_dots=1000, n_edges=2000, sym=1.0, complexity=1.0, density=1.0)
    d = structural_distance(a, b)
    for v in d.values():
        assert 0.0 <= v <= 1.0


def test_nearest_training_novelty_picks_minimum_distance():
    cand_stats = _stats(n_dots=10, n_edges=12)
    close = _stats(n_dots=11, n_edges=13)
    far = _stats(n_dots=100, n_edges=150)
    g = nx.MultiGraph()
    g.add_edge((0, 0), (1, 0))
    report = nearest_training_novelty(g, cand_stats, [far, close])
    expected = structural_distance(cand_stats, close)["combined_distance"]
    assert abs(report["nearest_training_distance"] - expected) < 1e-9
    assert report["novelty_score"] == report["nearest_training_distance"]


def test_no_training_stats_reports_none_not_fabricated_zero():
    g = nx.MultiGraph()
    report = nearest_training_novelty(g, _stats(), [])
    assert report["nearest_training_distance"] is None
    assert report["novelty_score"] is None
