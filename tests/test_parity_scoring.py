"""Tests for the parity-aware placement scoring added to
engine/novel_generation.py (docs/M4_2_PARITY_EVALUATION.md).

Covers, per the task's explicit numbered requirements:
  1. a placement that reduces odd-degree nodes gets a positive parity effect
  2. a placement that leaves parity unchanged gets a neutral effect
  3. a placement that increases odd-degree nodes gets a negative effect
  4. multi-edge / repeated-strand placement handles parity correctly
  5. empty/bootstrap graph does not crash
  6. existing connectivity-aware behavior is unchanged when parity_aware=False
  7. existing default behavior is unchanged when both flags are False
  8. parity-aware generation is deterministic
  9. engine.validity.check_validity is untouched
  10. multiplicity correctness remains preserved
"""

from __future__ import annotations

from collections import Counter

from engine.dataset import load_kolam
from engine.generation import generate_kolam
from engine.generation_api import GenerationConstraints, generate_kolam_candidate
from engine.motifs import MotifPlacement, induce_motif_set_adaptive
from engine.novel_generation import (
    _parity_effect,
    _parity_score,
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
# _parity_effect / _parity_score: unit-level, isolated from the search loop.
# ============================================================


def test_1_placement_that_reduces_odd_degree_nodes_scores_positive():
    # (0,0) and (1,0) are both already odd-degree (degree 1) in the
    # accumulated graph. A NEW edge between them makes both degree 2
    # (even) -- both flip odd -> even, delta_odd = -2.
    degree_before = Counter({(0, 0): 1, (1, 0): 1})
    contribution = Counter({frozenset({(0, 0), (1, 0)}): 1})
    effect = _parity_effect(degree_before, contribution)
    assert effect["odd_before"] == 2
    assert effect["odd_after"] == 0
    assert effect["delta_odd"] == -2

    score = _parity_score(effect, neutral=False)
    assert score > 0


def test_2_placement_that_leaves_parity_unchanged_is_neutral():
    # (0,0) has degree 2 (even); adding 2 more (a doubled edge) keeps it
    # even -- delta_odd == 0.
    degree_before = Counter({(0, 0): 2, (1, 0): 2})
    contribution = Counter({frozenset({(0, 0), (1, 0)}): 2})  # doubled strand
    effect = _parity_effect(degree_before, contribution)
    assert effect["delta_odd"] == 0

    score = _parity_score(effect, neutral=False)
    assert score == 0


def test_3_placement_that_increases_odd_degree_nodes_scores_negative():
    # Both (0,0) and (1,0) start at degree 0 (even). A single new edge
    # makes both degree 1 (odd) -- delta_odd = +2, a WORSENING placement.
    degree_before = Counter()
    contribution = Counter({frozenset({(0, 0), (1, 0)}): 1})
    effect = _parity_effect(degree_before, contribution)
    assert effect["odd_before"] == 0
    assert effect["odd_after"] == 2
    assert effect["delta_odd"] == 2

    score = _parity_score(effect, neutral=False)
    assert score < 0


def test_4_multi_strand_placement_handles_parity_via_true_multiplicity():
    # A node with degree 1 (odd) gets THREE more parallel strands to a
    # neighbor (odd count of new strands) -> degree 4 (even): parity
    # flips, matching "an odd number of parallel strands toggles parity".
    degree_before = Counter({(0, 0): 1})
    contribution = Counter({frozenset({(0, 0), (1, 0)}): 3})
    effect = _parity_effect(degree_before, contribution)
    # (0,0): 1 -> 4, odd -> even (flips). (1,0): 0 -> 3, even -> odd (flips).
    assert effect["odd_before"] == 1  # only (0,0) was already odd
    assert effect["odd_after"] == 1  # only (1,0) ends up odd
    assert effect["delta_odd"] == 0  # one flip cancels the other, net neutral

    # An EVEN number of new parallel strands must preserve parity exactly.
    degree_before2 = Counter({(0, 0): 1})
    contribution2 = Counter({frozenset({(0, 0), (1, 0)}): 2})
    effect2 = _parity_effect(degree_before2, contribution2)
    assert effect2["odd_before"] == 1  # (0,0) odd
    assert effect2["odd_after"] == 1  # (0,0): 1->3 still odd; (1,0): 0->2 still even
    assert effect2["delta_odd"] == 0


def test_5_empty_bootstrap_graph_does_not_crash():
    degree_before = Counter()  # completely empty accumulated graph
    contribution = Counter({frozenset({(0, 0), (1, 0)}): 1})
    effect = _parity_effect(degree_before, contribution)
    assert effect["odd_before"] == 0
    # neutral=True (the bootstrap guard select_novel_placements applies
    # before any real structure exists) must not raise and must score 0.
    assert _parity_score(effect, neutral=True) == 0.0
    # even without the guard, this specific case must not crash/NaN --
    # it's a well-defined negative score (delta_odd=+2, worsening), just
    # not what the search loop actually uses at bootstrap (see docstring).
    assert _parity_score(effect, neutral=False) == -8.0  # -PARITY_IMPROVEMENT_WEIGHT(4) * delta_odd(2)


# ============================================================
# select_novel_placements / generate_novel_kolam integration
# ============================================================


def test_6_connectivity_aware_behavior_unchanged_when_parity_aware_false():
    library = _library_from("kolam19", 1)
    target = load_kolam("kolam19", 15).dot_points

    without_param = select_novel_placements(library, target, max_multiplicity=2, connectivity_aware=True)
    with_explicit_false = select_novel_placements(
        library, target, max_multiplicity=2, connectivity_aware=True, parity_aware=False
    )

    def edge_multiset(placements):
        g = generate_kolam(placements, target)
        return Counter(frozenset(e) for e in g.graph.edges())

    assert edge_multiset(without_param) == edge_multiset(with_explicit_false)


def test_7_default_behavior_unchanged_with_both_flags_false():
    library = _library_from("kolam19", 1)
    target = load_kolam("kolam19", 15).dot_points

    default_call = select_novel_placements(library, target, max_multiplicity=2)
    explicit_false = select_novel_placements(
        library, target, max_multiplicity=2, connectivity_aware=False, parity_aware=False
    )

    def edge_multiset(placements):
        g = generate_kolam(placements, target)
        return Counter(frozenset(e) for e in g.graph.edges())

    assert edge_multiset(default_call) == edge_multiset(explicit_false)


def test_bootstrap_does_not_collapse_search_to_zero_placements():
    # The exact regression this task's bootstrap guard exists for: an
    # earlier, unguarded version of this scorer produced ZERO placements
    # on every tested input (verified during development, not
    # theorized) -- this proves the shipped version does not.
    library = _library_from("kolam19", 1)
    target = load_kolam("kolam19", 15).dot_points
    candidate = generate_novel_kolam(library, target, max_multiplicity=2, parity_aware=True)
    assert len(candidate.placements) > 0


def test_8_parity_aware_generation_is_deterministic():
    library = _library_from("kolam19", 3)
    target = load_kolam("kolam19", 15).dot_points
    a = generate_novel_kolam(library, target, max_multiplicity=2, connectivity_aware=True, parity_aware=True)
    b = generate_novel_kolam(library, target, max_multiplicity=2, connectivity_aware=True, parity_aware=True)
    assert a.edge_multiplicity == b.edge_multiplicity
    assert a.dot_trace == b.dot_trace


def test_9_check_validity_is_not_bypassed_for_parity_aware_candidates():
    library = _library_from("kolam19", 1)
    target = load_kolam("kolam19", 15).dot_points
    candidate = generate_novel_kolam(library, target, max_multiplicity=2, connectivity_aware=True, parity_aware=True)
    assert candidate.validity_result == check_validity(candidate.graph)


def test_10_multiplicity_cap_is_preserved_with_parity_aware_scoring():
    library = _library_from("kolam19", 1) + _library_from("kolam19", 2)
    target = load_kolam("kolam19", 15).dot_points
    for cap in (1, 2):
        candidate = generate_novel_kolam(
            library, target, max_multiplicity=cap, connectivity_aware=True, parity_aware=True
        )
        strand_counts = Counter(frozenset(e) for e in candidate.graph.edges())
        assert not strand_counts or max(strand_counts.values()) <= cap


def test_parity_measurably_reduces_odd_degree_count_on_a_real_layout():
    # The concrete, measured claim this feature exists for.
    library = _library_from("kolam19", 1)
    target = load_kolam("kolam19", 15).dot_points

    without_parity = generate_novel_kolam(library, target, max_multiplicity=2, connectivity_aware=True)
    with_parity = generate_novel_kolam(
        library, target, max_multiplicity=2, connectivity_aware=True, parity_aware=True
    )

    def odd_count(candidate):
        return sum(1 for _n, d in candidate.graph.degree() if d % 2 == 1)

    assert odd_count(with_parity) < odd_count(without_parity)


def test_generation_api_wires_parity_aware_through():
    library = _library_from("kolam19", 1)
    target = load_kolam("kolam19", 15).dot_points
    off = generate_kolam_candidate(GenerationConstraints(lattice=target, motif_library=library, parity_aware=False))
    on = generate_kolam_candidate(
        GenerationConstraints(lattice=target, motif_library=library, connectivity_aware=True, parity_aware=True)
    )

    def odd_count(result):
        return sum(1 for _n, d in result.candidate.graph.degree() if d % 2 == 1)

    assert odd_count(on) < odd_count(off)


def test_generation_api_default_constraints_default_to_parity_unaware():
    library = _library_from("kolam19", 1)
    constraints = GenerationConstraints(lattice=load_kolam("kolam19", 15).dot_points, motif_library=library)
    assert constraints.parity_aware is False
