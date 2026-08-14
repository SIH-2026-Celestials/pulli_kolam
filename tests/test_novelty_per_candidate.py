"""Tests for engine/novelty.py's per_candidate_novelty (M5 OBJECTIVE 3)."""

from __future__ import annotations

from engine.dataset import load_kolam
from engine.generation import generate_kolam
from engine.motifs import MotifPlacement
from engine.novelty import per_candidate_novelty


def test_exact_reconstruction_scores_zero_novelty():
    """A candidate built to EXACTLY reproduce a source pattern's own
    edges (same layout, same edge multiset) must score novelty_score
    near 0 against that source -- this is the sanity floor: the metric
    must not call a literal copy 'novel'."""
    source = load_kolam("kolam19", 1)
    placement = MotifPlacement(motif=(), points=[], transforms={})
    # Build a candidate graph identical to the source by stamping every
    # source edge as a trivial single-relative-edge motif at its own
    # location -- simplest way to get an EXACT copy without depending on
    # motif induction quality.
    from engine.generation import build_candidate_graph

    placements = []
    for a, b in source.graph.edges():
        dx, dy = b[0] - a[0], b[1] - a[1]
        motif = (((0, 0), (dx, dy)),)
        placements.append(MotifPlacement(motif=motif, points=[a], transforms={}))
    candidate = generate_kolam(placements, source.dot_points)

    rows = per_candidate_novelty([candidate], [source], source_ids=["kolam19#1"], candidate_ids=["c0"])
    assert len(rows) == 1
    assert rows[0]["source_id"] == "kolam19#1"
    assert rows[0]["novelty_score"] == 0.0


def test_empty_candidate_against_no_sources_has_no_source_id():
    from engine.generation import build_candidate_graph

    candidate = generate_kolam([], {(0, 0), (1, 0)})
    rows = per_candidate_novelty([candidate], [])
    assert rows[0]["source_id"] is None
    assert rows[0]["novelty_score"] == 1.0  # no comparable/matching source -> treated as novel, not penalized


def test_validity_score_is_1_for_valid_and_less_than_1_for_invalid():
    source = load_kolam("kolam19", 1)
    valid_candidate = generate_kolam(
        [MotifPlacement(motif=(((0, 0), (b[0] - a[0], b[1] - a[1])),), points=[a], transforms={})
         for a, b in source.graph.edges()],
        source.dot_points,
    )
    invalid_candidate = generate_kolam([], source.dot_points)  # no edges at all -> disconnected, invalid

    rows = per_candidate_novelty([valid_candidate, invalid_candidate], [source], source_ids=["kolam19#1"] * 1)
    assert rows[0]["validity_score"] == 1.0
    assert rows[0]["is_valid"] is True
    assert rows[1]["validity_score"] < 1.0
    assert rows[1]["is_valid"] is False
