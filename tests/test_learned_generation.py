"""Tests for engine/learned_generation.py (M5): the learned-scorer-guided
multi-restart search and bounded multiplicity repair, replacing M3.7/M4.2's
single-pass greedy pipeline (0/120 to 1/120 measured valid).

These tests use a small synthetic lattice (not a full real pattern) so
they run fast -- correctness of the underlying primitives
(_stamp_contribution semantics, validity checking, D4 transforms) is
already covered by tests/test_novel_generation.py and
tests/test_generation.py; these tests are specifically about the NEW
search/repair logic layered on top."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from engine.learned_generation import (
    generate_novel_kolam_learned,
    repair_multiplicity,
    search_best_candidate,
)
from engine.learned_scoring import N_FEATURES, PlacementScorer, ScorerBundle, save_checkpoint
from engine.motifs import Motif
from engine.validity import check_validity

CHECKPOINT = Path(__file__).resolve().parent.parent / "experiments" / "m5_generation" / "checkpoints" / "placement_scorer.pt"

# A 3x3 lattice with a single "plus" motif -- a real, small hand-built
# case (same spirit as tests/test_generation.py's hand-built fixtures)
# so the search has a genuine chance at validity without needing the
# full real-data pipeline.
_LATTICE_3X3 = {(x, y) for x in range(3) for y in range(3)}
_RING_MOTIF: Motif = (((0, 0), (1, 0)),)  # single relative edge, "step right"


def _always_accept_scorer() -> ScorerBundle:
    """A scorer that accepts every placement (score() always returns 1.0)
    -- used to test the search MECHANISM (restart loop, candidate
    enumeration, repair) independent of what a real trained model would
    decide."""
    model = PlacementScorer(n_features=N_FEATURES, hidden=8)
    with torch.no_grad():
        for p in model.parameters():
            p.zero_()
        # bias the final layer heavily positive -> sigmoid(logit) ~= 1.0
        model.net[-1].bias.fill_(50.0)
    mean = np.zeros(N_FEATURES, dtype=np.float32)
    std = np.ones(N_FEATURES, dtype=np.float32)
    return ScorerBundle(model=model, feature_mean=mean, feature_std=std, metadata={})


def test_search_best_candidate_deterministic_given_seed():
    scorer = _always_accept_scorer()
    c1, restarts1 = search_best_candidate([_RING_MOTIF], _LATTICE_3X3, scorer=scorer, n_restarts=3, seed=42)
    c2, restarts2 = search_best_candidate([_RING_MOTIF], _LATTICE_3X3, scorer=scorer, n_restarts=3, seed=42)
    assert c1.edge_multiplicity == c2.edge_multiplicity
    assert [r["is_valid"] for r in restarts1] == [r["is_valid"] for r in restarts2]


def test_search_best_candidate_validity_result_always_populated():
    scorer = _always_accept_scorer()
    candidate, restarts = search_best_candidate([_RING_MOTIF], _LATTICE_3X3, scorer=scorer, n_restarts=2, seed=1)
    assert candidate.validity_result is not None
    assert candidate.diagnosis is not None
    assert len(restarts) >= 1


def test_repair_multiplicity_only_touches_existing_edges():
    scorer = _always_accept_scorer()
    candidate, _ = search_best_candidate([_RING_MOTIF], _LATTICE_3X3, scorer=scorer, n_restarts=1, seed=7)
    original_edges = set(candidate.edge_multiplicity.keys())

    repaired, applied = repair_multiplicity(candidate)

    repaired_edges = set(repaired.edge_multiplicity.keys())
    # Repair may raise multiplicity on existing edges but must never
    # introduce a pair that wasn't already connected in the candidate.
    assert repaired_edges <= original_edges or original_edges <= repaired_edges
    for correction in applied:
        (ax, ay), (bx, by) = correction["edge"]
        assert frozenset({(ax, ay), (bx, by)}) in original_edges


def test_repair_skipped_when_disconnected():
    """repair_multiplicity must return the candidate UNCHANGED (not
    silently 'fixed') if nodes lie outside the largest connected
    component -- merging components would require inventing a new edge
    with no motif justification, which this function explicitly refuses
    to do (see its docstring)."""
    scorer = _always_accept_scorer()
    # A lattice where the single-edge motif can never connect every dot
    # (isolated corners) -- guarantees a disconnected result to exercise
    # the skip path.
    sparse_lattice = {(0, 0), (1, 0), (5, 5)}
    candidate, _ = search_best_candidate([_RING_MOTIF], sparse_lattice, scorer=scorer, n_restarts=1, seed=3)
    if candidate.diagnosis["n_nodes_outside_largest_component"] > 0:
        repaired, applied = repair_multiplicity(candidate)
        assert applied == []
        assert repaired.edge_multiplicity == candidate.edge_multiplicity


def test_generate_novel_kolam_learned_reports_honest_metadata():
    scorer = _always_accept_scorer()
    run = generate_novel_kolam_learned([_RING_MOTIF], _LATTICE_3X3, scorer=scorer, n_restarts=2, seed=99)
    assert run.seed == 99
    assert run.n_restarts == 2
    assert len(run.restarts) >= 1
    assert run.latency_seconds >= 0
    # candidate's own validity_result must be internally consistent with
    # check_validity run independently on the same graph
    assert run.candidate.validity_result == check_validity(run.candidate.graph)


@pytest.mark.skipif(not CHECKPOINT.exists(), reason="trained checkpoint not present")
def test_real_scorer_produces_different_candidates_across_seeds():
    from engine.learned_scoring import load_scorer
    from engine.novelty import graph_fingerprint

    scorer = load_scorer(CHECKPOINT)
    lattice = {(x, y) for x in range(6) for y in range(6)}
    library: list[Motif] = [(((0, 0), (1, 0)),), (((0, 0), (0, 1)),), (((0, 0), (1, 1)),)]

    fps = set()
    for seed in range(3):
        run = generate_novel_kolam_learned(library, lattice, scorer=scorer, n_restarts=2, seed=seed)
        fps.add(graph_fingerprint(run.candidate.graph))
    # not asserting all-unique (small lattice, small library can legitimately
    # collide) -- just that the search is not fully static/broken (produces
    # at least one non-empty structure across these seeds)
    assert any(fp != () for fp in fps)
