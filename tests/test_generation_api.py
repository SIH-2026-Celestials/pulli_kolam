"""Tests for engine/generation_api.py: the M4.2-A constraint-based
generation entry point. Verifies it is a genuine thin wrapper --
identical output to calling engine.novel_generation directly -- plus
its own added behavior (rectangular_lattice, multi-source library
pooling, and the require_single_stroke satisfied/reasons report)."""

from __future__ import annotations

import pytest

from engine.dataset import load_kolam
from engine.generation_api import (
    GenerationConstraints,
    generate_kolam_candidate,
    motif_library_from_sources,
    rectangular_lattice,
)
from engine.motifs import induce_motif_set_adaptive
from engine.novel_generation import extract_motif_library, generate_novel_kolam


def test_rectangular_lattice_shape_and_bounds():
    lattice = rectangular_lattice(4, 3)
    assert len(lattice) == 12
    xs = [p[0] for p in lattice]
    ys = [p[1] for p in lattice]
    assert min(xs) == 0 and max(xs) == 3
    assert min(ys) == 0 and max(ys) == 2


def test_rectangular_lattice_rejects_nonpositive_dimensions():
    with pytest.raises(ValueError):
        rectangular_lattice(0, 5)
    with pytest.raises(ValueError):
        rectangular_lattice(5, -1)


def test_motif_library_from_single_source_matches_extract_motif_library_directly():
    pattern = load_kolam("kolam19", 1)
    placements, _residual, _covered = induce_motif_set_adaptive(pattern)
    expected = set(extract_motif_library(placements))

    got = set(motif_library_from_sources([("kolam19", 1)]))
    assert got == expected


def test_motif_library_from_multiple_sources_is_a_deduplicated_union():
    lib_a = set(motif_library_from_sources([("kolam19", 1)]))
    lib_b = set(motif_library_from_sources([("kolam19", 2)]))
    combined = set(motif_library_from_sources([("kolam19", 1), ("kolam19", 2)]))

    assert combined == lib_a | lib_b


def test_generate_kolam_candidate_matches_generate_novel_kolam_directly():
    # Same constraints, expressed two ways -- generation_api must not
    # reimplement placement logic, only wrap it.
    lattice = rectangular_lattice(8, 8)
    library = motif_library_from_sources([("kolam19", 1)])

    constraints = GenerationConstraints(lattice=lattice, motif_library=library, max_multiplicity=2)
    result = generate_kolam_candidate(constraints)

    direct = generate_novel_kolam(library, lattice, max_multiplicity=2)

    assert result.candidate.edge_multiplicity == direct.edge_multiplicity
    assert result.candidate.is_valid == direct.is_valid
    assert set(result.candidate.graph.edges()) == set(direct.graph.edges())


def test_generate_kolam_candidate_accepts_dimension_tuple_lattice():
    library = motif_library_from_sources([("kolam19", 1)])
    constraints = GenerationConstraints(lattice=(6, 6), motif_library=library)
    result = generate_kolam_candidate(constraints)
    assert result.candidate.dot_points == rectangular_lattice(6, 6)


def test_generate_kolam_candidate_resolves_motif_sources_when_no_library_given():
    constraints = GenerationConstraints(lattice=(6, 6), motif_sources=[("kolam19", 1)])
    result = generate_kolam_candidate(constraints)
    expected_library = set(motif_library_from_sources([("kolam19", 1)]))
    used_motifs = {p.motif for p in result.candidate.placements}
    assert used_motifs <= expected_library


def test_generate_kolam_candidate_requires_a_library_source():
    constraints = GenerationConstraints(lattice=(4, 4))
    with pytest.raises(ValueError):
        generate_kolam_candidate(constraints)


def test_satisfied_is_false_and_explained_for_an_invalid_candidate():
    # An empty motif library can never produce any edges at all --
    # guaranteed invalid (disconnected, unless the lattice is 1 dot).
    constraints = GenerationConstraints(lattice=(5, 5), motif_library=[], require_single_stroke=True)
    result = generate_kolam_candidate(constraints)
    assert result.candidate.is_valid is False
    assert result.satisfied is False
    assert len(result.reasons_unsatisfied) == 1
    assert "Eulerian" in result.reasons_unsatisfied[0]


def test_require_single_stroke_false_does_not_penalize_an_invalid_candidate():
    constraints = GenerationConstraints(lattice=(5, 5), motif_library=[], require_single_stroke=False)
    result = generate_kolam_candidate(constraints)
    assert result.candidate.is_valid is False
    assert result.satisfied is True
    assert result.reasons_unsatisfied == []


def test_max_multiplicity_is_actually_enforced_through_the_wrapper():
    library = motif_library_from_sources([("kolam19", 1), ("kolam19", 2)])
    constraints = GenerationConstraints(lattice=(10, 10), motif_library=library, max_multiplicity=1)
    result = generate_kolam_candidate(constraints)
    from collections import Counter

    strand_counts = Counter(frozenset(e) for e in result.candidate.graph.edges())
    assert not strand_counts or max(strand_counts.values()) <= 1


def test_deterministic_across_repeated_calls():
    library = motif_library_from_sources([("kolam19", 3)])
    constraints = GenerationConstraints(lattice=(8, 8), motif_library=library, max_multiplicity=2)
    a = generate_kolam_candidate(constraints)
    b = generate_kolam_candidate(constraints)
    assert a.candidate.edge_multiplicity == b.candidate.edge_multiplicity
    assert a.candidate.dot_trace == b.candidate.dot_trace
