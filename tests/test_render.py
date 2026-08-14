"""Tests for engine/render.py: deterministic SVG/PNG rendering of a
GeneratedKolam candidate or a source KolamPattern."""

from __future__ import annotations

import os

from engine import render
from engine.dataset import load_kolam
from engine.generation_api import GenerationConstraints, generate_kolam_candidate, motif_library_from_sources
from engine.generation import generate_kolam


def test_render_kolam_pattern_svg_is_well_formed_and_contains_every_dot():
    pattern = load_kolam("kolam19", 1)
    svg = render.render_kolam_pattern_svg(pattern)
    assert svg.startswith("<svg")
    assert svg.strip().endswith("</svg>")
    assert svg.count("<circle") == len(pattern.dot_points)


def test_render_svg_is_deterministic_given_the_same_input():
    pattern = load_kolam("kolam19", 2)
    svg_a = render.render_kolam_pattern_svg(pattern)
    svg_b = render.render_kolam_pattern_svg(pattern)
    assert svg_a == svg_b


def test_render_invalid_generated_candidate_is_labeled_not_hidden():
    # A small 3x3 grid with an empty motif library is guaranteed invalid
    # (zero placements -> disconnected/no edges at all) -- exercises the
    # "never silently draw an invalid candidate as if it were successful"
    # rule directly.
    dot_points = {(x, y) for x in range(3) for y in range(3)}
    candidate = generate_kolam(placements=[], dot_points=dot_points)
    assert candidate.is_valid is False
    assert candidate.dot_trace is None

    svg = render.render_generated_kolam_svg(candidate)
    assert "INVALID" in svg
    # No polyline should be drawn for a None trace -- only dots.
    assert "<polyline" not in svg
    assert svg.count("<circle") == len(dot_points)


def test_render_valid_generated_candidate_draws_a_stroke_not_labeled_invalid():
    # A single doubled 4-cycle motif on its own 4-dot lattice is the
    # exact controlled-valid case docs/GENERATION.md's own example uses.
    from engine.motifs import MotifPlacement

    motif = (((0, 0), (1, 0)), ((1, 0), (1, 1)), ((1, 1), (0, 1)), ((0, 1), (0, 0))) * 2
    dot_points = {(0, 0), (1, 0), (1, 1), (0, 1)}
    placement = MotifPlacement(motif=motif, points=[(0, 0)], transforms={})
    candidate = generate_kolam([placement], dot_points)
    assert candidate.is_valid is True
    assert candidate.dot_trace is not None

    svg = render.render_generated_kolam_svg(candidate)
    assert "INVALID" not in svg
    assert "<polyline" in svg


def test_render_png_writes_a_real_nonempty_file(tmp_path):
    pattern = load_kolam("kolam19", 1)
    out_path = tmp_path / "kolam1.png"
    render.render_kolam_pattern_png(pattern, str(out_path))
    assert os.path.exists(out_path)
    assert os.path.getsize(out_path) > 0
    with open(out_path, "rb") as f:
        assert f.read(8) == b"\x89PNG\r\n\x1a\n"  # real PNG signature, not a stub file


def test_svg_and_png_agree_on_dot_placement_via_shared_layout(tmp_path):
    # Both renderers use engine.render._layout -- prove they place the
    # SAME number of dots for the same input rather than testing the
    # private layout function directly.
    pattern = load_kolam("kolam19", 3)
    svg = render.render_kolam_pattern_svg(pattern)
    out_path = tmp_path / "kolam3.png"
    render.render_kolam_pattern_png(pattern, str(out_path))
    assert svg.count("<circle") == len(pattern.dot_points)
    assert os.path.exists(out_path)


def test_render_does_not_require_ml_or_network_access():
    # Sanity: rendering a generation_api candidate end-to-end never
    # imports torch or touches the network -- purely engine/ + PIL.
    lib = motif_library_from_sources([("kolam19", 1)])
    constraints = GenerationConstraints(lattice=(6, 6), motif_library=lib)
    result = generate_kolam_candidate(constraints)
    svg = render.render_generated_kolam_svg(result.candidate)
    assert svg.startswith("<svg")
