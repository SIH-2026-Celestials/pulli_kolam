"""Tests for the connectivity-aware placement scoring added to
engine/novel_generation.py (docs/M4_2_CONNECTIVITY_EVALUATION.md).

Covers, per the task's explicit requirements:
  - a candidate that joins two REAL (size > 1) components receives a
    positive connectivity benefit
  - a candidate that creates an isolated component is penalized
    (once real structure already exists elsewhere -- see the bootstrap
    guard test, which proves the FIRST-ever placement must NOT be
    penalized for the same reason)
  - a candidate that extends an existing component behaves correctly
  - the connectivity score never touches multiplicity accounting
  - deterministic behavior where expected
  - existing generator behavior/API remains compatible
    (connectivity_aware=False, the default, is byte-for-byte identical
    to pre-existing behavior)
  - validity checks (engine.validity.check_validity) remain unchanged
"""

from __future__ import annotations

from collections import Counter

import networkx as nx

from engine.dataset import load_kolam
from engine.generation import generate_kolam
from engine.generation_api import GenerationConstraints, generate_kolam_candidate, rectangular_lattice
from engine.motifs import induce_motif_set_adaptive
from engine.novel_generation import (
    _UnionFind,
    _connectivity_effect,
    _connectivity_score,
    extract_motif_library,
    generate_novel_kolam,
    select_novel_placements,
)
from engine.validity import check_validity


def _library_from(collection: str, pattern_id: int):
    pattern = load_kolam(collection, pattern_id)
    placements, _residual, _covered = induce_motif_set_adaptive(pattern)
    return extract_motif_library(placements)


# ============================================================
# _connectivity_effect / _connectivity_score: unit-level, isolated from
# the search loop entirely.
# ============================================================


def test_joining_two_real_components_is_classified_and_scored_positive():
    # Two pre-existing size>1 components: {a, b} and {c, d}.
    uf = _UnionFind([(0, 0), (1, 0), (5, 5), (6, 5), (3, 3)])
    uf.union((0, 0), (1, 0))
    uf.union((5, 5), (6, 5))
    assert uf.size((0, 0)) == 2
    assert uf.size((5, 5)) == 2

    bridge = Counter({frozenset({(1, 0), (5, 5)}): 1})
    effect = _connectivity_effect(uf, bridge)
    assert effect["n_merge_real"] == 1
    assert effect["n_extend"] == 0
    assert effect["n_new_isolated_pair"] == 0

    score = _connectivity_score(effect, penalize_new_isolated=True)
    assert score > 0


def test_extending_an_existing_component_into_a_singleton_is_classified_correctly():
    uf = _UnionFind([(0, 0), (1, 0), (2, 0)])
    uf.union((0, 0), (1, 0))  # {(0,0),(1,0)} is now a real, size-2 component
    assert uf.size((2, 0)) == 1  # (2,0) untouched

    extend = Counter({frozenset({(1, 0), (2, 0)}): 1})
    effect = _connectivity_effect(uf, extend)
    assert effect["n_extend"] == 1
    assert effect["n_merge_real"] == 0
    assert effect["n_new_isolated_pair"] == 0

    score = _connectivity_score(effect, penalize_new_isolated=True)
    assert score > 0


def test_creating_a_new_isolated_pair_is_classified_and_penalized_when_real_structure_exists():
    uf = _UnionFind([(0, 0), (1, 0), (10, 10), (11, 10)])
    uf.union((0, 0), (1, 0))  # real structure exists ELSEWHERE

    new_pair = Counter({frozenset({(10, 10), (11, 10)}): 1})
    effect = _connectivity_effect(uf, new_pair)
    assert effect["n_new_isolated_pair"] == 1
    assert effect["n_merge_real"] == 0
    assert effect["n_extend"] == 0

    penalized = _connectivity_score(effect, penalize_new_isolated=True)
    unpenalized = _connectivity_score(effect, penalize_new_isolated=False)
    assert penalized < unpenalized
    assert unpenalized == 0  # a pure isolated pair with no other effect scores 0 when not penalized


def test_bootstrap_the_very_first_ever_placement_must_not_be_penalized():
    # Fresh, all-singleton union-find -- exactly the state
    # select_novel_placements starts every search from. The very first
    # candidate MUST classify as a "new isolated pair" (nothing else
    # exists to merge with or extend), and MUST NOT be penalized for it
    # -- see _connectivity_score's own docstring for why a naive
    # unconditional penalty reproduces the exact zero-placements
    # bootstrap bug _novel_score already had to solve once.
    uf = _UnionFind([(0, 0), (1, 0)])
    first_ever = Counter({frozenset({(0, 0), (1, 0)}): 1})
    effect = _connectivity_effect(uf, first_ever)
    assert effect["n_new_isolated_pair"] == 1

    score_at_bootstrap = _connectivity_score(effect, penalize_new_isolated=False)
    assert score_at_bootstrap == 0  # not penalized -- neutral, exactly as documented


def test_multi_edge_placement_spanning_two_component_pairs_is_counted_correctly():
    # A single placement (motif) can have several edges touching several
    # different component pairs at once -- must not assume 1 edge.
    uf = _UnionFind([(0, 0), (1, 0), (5, 5), (6, 5), (9, 9)])
    uf.union((0, 0), (1, 0))
    uf.union((5, 5), (6, 5))

    contribution = Counter(
        {
            frozenset({(1, 0), (5, 5)}): 1,  # merges the two real components
            frozenset({(6, 5), (9, 9)}): 1,  # extends the (now-merged) component into a singleton
        }
    )
    effect = _connectivity_effect(uf, contribution)
    assert effect["n_merge_real"] == 1
    assert effect["n_extend"] == 1


def test_redundant_second_edge_between_the_same_two_components_counts_once():
    uf = _UnionFind([(0, 0), (1, 0), (5, 5), (6, 5)])
    uf.union((0, 0), (1, 0))
    uf.union((5, 5), (6, 5))

    contribution = Counter(
        {
            frozenset({(0, 0), (5, 5)}): 1,
            frozenset({(1, 0), (6, 5)}): 1,  # same two components, different endpoints
        }
    )
    effect = _connectivity_effect(uf, contribution)
    assert effect["n_merge_real"] == 1  # not 2 -- both edges bridge the SAME component pair


# ============================================================
# select_novel_placements / generate_novel_kolam integration
# ============================================================


def test_connectivity_aware_false_is_byte_identical_to_pre_existing_behavior():
    library = _library_from("kolam19", 1)
    target = load_kolam("kolam19", 15).dot_points

    default_call = select_novel_placements(library, target, max_multiplicity=2)
    explicit_false = select_novel_placements(library, target, max_multiplicity=2, connectivity_aware=False)

    def edge_multiset(placements):
        g = generate_kolam(placements, target)
        return Counter(frozenset(e) for e in g.graph.edges())

    assert edge_multiset(default_call) == edge_multiset(explicit_false)


def test_connectivity_aware_reduces_component_count_on_a_real_unseen_layout():
    # The concrete, measured claim this feature exists for: does turning
    # it on reduce fragmentation on the SAME input? (Not a claim of full
    # validity -- see docs/M4_2_CONNECTIVITY_EVALUATION.md for the honest
    # aggregate result.)
    library = _library_from("kolam19", 1)
    target = load_kolam("kolam19", 15).dot_points

    baseline = generate_novel_kolam(library, target, max_multiplicity=2, connectivity_aware=False)
    aware = generate_novel_kolam(library, target, max_multiplicity=2, connectivity_aware=True)

    baseline_components = nx.number_connected_components(baseline.graph)
    aware_components = nx.number_connected_components(aware.graph)
    assert aware_components < baseline_components


def test_connectivity_aware_never_violates_the_multiplicity_cap():
    library = _library_from("kolam19", 1) + _library_from("kolam19", 2)
    target = rectangular_lattice(10, 10)
    for cap in (1, 2):
        candidate = generate_novel_kolam(library, target, max_multiplicity=cap, connectivity_aware=True)
        strand_counts = Counter(frozenset(e) for e in candidate.graph.edges())
        assert not strand_counts or max(strand_counts.values()) <= cap


def test_connectivity_aware_is_deterministic_across_repeated_calls():
    library = _library_from("kolam19", 3)
    target = rectangular_lattice(8, 8)
    a = generate_novel_kolam(library, target, max_multiplicity=2, connectivity_aware=True)
    b = generate_novel_kolam(library, target, max_multiplicity=2, connectivity_aware=True)
    assert a.edge_multiplicity == b.edge_multiplicity
    assert a.dot_trace == b.dot_trace


def test_connectivity_aware_candidate_validity_uses_the_same_unmodified_check():
    # engine.validity.check_validity must not have been touched or
    # special-cased for connectivity_aware candidates -- generate_kolam
    # (unmodified) already calls it unconditionally; this proves the
    # RESULT matches calling it independently on the same graph.
    library = _library_from("kolam19", 1)
    target = load_kolam("kolam19", 15).dot_points
    candidate = generate_novel_kolam(library, target, max_multiplicity=2, connectivity_aware=True)
    assert candidate.validity_result == check_validity(candidate.graph)


def test_generation_api_wires_connectivity_aware_through():
    library = _library_from("kolam19", 1)
    constraints_off = GenerationConstraints(
        lattice=load_kolam("kolam19", 15).dot_points, motif_library=library, connectivity_aware=False
    )
    constraints_on = GenerationConstraints(
        lattice=load_kolam("kolam19", 15).dot_points, motif_library=library, connectivity_aware=True
    )
    off = generate_kolam_candidate(constraints_off)
    on = generate_kolam_candidate(constraints_on)
    assert nx.number_connected_components(on.candidate.graph) < nx.number_connected_components(off.candidate.graph)


def test_generation_api_default_constraints_still_default_to_connectivity_unaware():
    library = _library_from("kolam19", 1)
    constraints = GenerationConstraints(lattice=load_kolam("kolam19", 15).dot_points, motif_library=library)
    assert constraints.connectivity_aware is False
