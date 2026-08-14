"""M4.0 contract test: proves an ML dot-lattice detector satisfying
engine.ml_contract.MLLatticeDetector can drive trace_path -> graph
construction -> downstream engine calls with ZERO changes to any of
those functions -- the exact claim docs/ML_CONTRACT.md makes. This is a
contract test, not a model: the "ML detector" here is a hand-built mock
returning literal, hardcoded Lattice data, never running any detection
algorithm at all.

Also documents (not fixes -- see docs/ML_CONTRACT.md Section 5 and
PROJECT_STATE.md's M4.0 report "remaining blockers") one concrete,
reproduced pre-existing contract violation discovered while writing this
freeze: a Lattice with 1-2 pixel_positions but 0 lattice_coords crashes
trace_path with IndexError. STRICT RULE for this session: do not modify
trace_path -- these tests characterize the crash and the safe
workaround, they do not patch it.
"""

from __future__ import annotations

import cv2
import networkx as nx
import numpy as np
import pytest

from engine import image_io, motifs, validity
from engine.ml_contract import MLLatticeDetector, assert_conforms


def _square_binary_with_perimeter_strokes(size=400, centers=None, radius=10):
    """A minimal synthetic ink mask: 4 dot blobs at `centers`, joined by
    straight-line perimeter strokes -- independent of and much simpler
    than engine.image_io's own dot-detection machinery, so a test built
    on it genuinely exercises trace_path/graph construction against
    ARBITRARY Lattice input, not against image_io's own algorithm."""
    if centers is None:
        centers = [(100, 100), (300, 100), (300, 300), (100, 300)]
    binary = np.zeros((size, size), dtype=np.uint8)
    yy, xx = np.mgrid[0:size, 0:size]
    for cx, cy in centers:
        mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius**2
        binary[mask] = 255
    for i in range(len(centers)):
        a, b = centers[i], centers[(i + 1) % len(centers)]
        cv2.line(binary, a, b, 255, 3)
    return binary, centers


def _mock_ml_detector(preprocessed: image_io.Preprocessed) -> image_io.Lattice:
    """A stand-in ML detector: ignores the actual pixel content entirely
    and returns hardcoded detections. Satisfies MLLatticeDetector's
    signature exactly -- proof that ANY conforming callable can occupy
    this slot, not just engine.image_io.detect_lattice itself."""
    centers = [(100.0, 100.0), (300.0, 100.0), (300.0, 300.0), (100.0, 300.0)]
    lattice_coords = [(0, 0), (1, 0), (1, 1), (0, 1)]
    return image_io.Lattice(centers, lattice_coords, dot_radius=10.0)


def _build_graph_with_detector(preprocessed, detector) -> nx.MultiGraph:
    """Mirrors engine.image_io.build_graph's own three lines exactly, but
    with the detection stage swapped for an injected `detector`. Lives
    HERE, in the test, not in engine/ -- engine.image_io.build_graph
    itself is intentionally not modified this session (see module
    docstring's strict rule). This function IS the drop-in-replacement
    claim, made concrete."""
    lattice = detector(preprocessed)
    edges = image_io.trace_path(preprocessed, lattice)
    G = nx.MultiGraph()
    G.add_nodes_from(lattice.lattice_coords)
    for a, b in edges:
        G.add_edge(a, b)
    return G


def test_mock_detector_satisfies_the_frozen_protocol():
    assert isinstance(_mock_ml_detector, MLLatticeDetector)
    assert isinstance(image_io.detect_lattice, MLLatticeDetector)


def test_mock_detector_output_conforms_structurally():
    binary, centers = _square_binary_with_perimeter_strokes()
    preprocessed = image_io.Preprocessed(binary=binary, rotation_deg=0.0)
    lattice = _mock_ml_detector(preprocessed)
    assert_conforms(lattice)  # must not raise


def test_mock_detector_drives_trace_path_and_graph_construction_unmodified():
    """The core substitutability claim: swap detect_lattice for an
    unrelated mock, and trace_path / graph construction -- completely
    unmodified functions -- still produce a correct, engine-compatible
    MultiGraph."""
    binary, centers = _square_binary_with_perimeter_strokes()
    preprocessed = image_io.Preprocessed(binary=binary, rotation_deg=0.0)

    G = _build_graph_with_detector(preprocessed, _mock_ml_detector)

    assert isinstance(G, nx.MultiGraph)
    assert set(G.nodes()) == {(0, 0), (1, 0), (1, 1), (0, 1)}
    # perimeter square -> exactly the 4 adjacent-corner edges, no diagonals
    edge_set = {frozenset(e) for e in G.edges()}
    assert edge_set == {
        frozenset({(0, 0), (1, 0)}),
        frozenset({(1, 0), (1, 1)}),
        frozenset({(1, 1), (0, 1)}),
        frozenset({(0, 1), (0, 0)}),
    }

    # zero-change downstream compatibility, matching
    # test_image_io.py::test_build_graph_produces_engine_compatible_multigraph
    result = validity.check_validity(G)
    assert "is_eulerian_circuit" in result
    dots = set(G.nodes())
    interior = motifs.interior_points(dots, radius=1)
    placements, residual, _fully_covered = motifs.induce_motif_set_adaptive(
        G, interior, dots, max_radius=2, max_motifs_per_radius=50
    )
    assert isinstance(placements, list)


def test_mock_detector_recommended_empty_convention_matches_deterministic_detector():
    """A conforming detector finding zero dots must behave identically to
    detect_lattice's own zero-detection convention (Lattice([], [], _)),
    proven by feeding both through trace_path and getting the same
    (empty) result."""
    preprocessed = image_io.Preprocessed(binary=np.zeros((400, 400), dtype=np.uint8), rotation_deg=0.0)

    deterministic_lattice = image_io.detect_lattice(preprocessed)
    mock_empty_lattice = image_io.Lattice([], [], 0.0)

    assert image_io.trace_path(preprocessed, deterministic_lattice) == []
    assert image_io.trace_path(preprocessed, mock_empty_lattice) == []


# ============================================================
# Documented pre-existing blocker (discovered this session, NOT fixed --
# see docs/ML_CONTRACT.md Section 5 and PROJECT_STATE.md M4.0 report).
# ============================================================


def test_asymmetric_lattice_shape_is_a_documented_unfixed_blocker():
    """detect_lattice's own existing convention for 1-2 detected points
    (return them in pixel_positions, but lattice_coords=[] since a lattice
    fit needs >=3 points -- see tests/test_image_io.py's
    test_detect_lattice_handles_{one,two}_candidate_dots_without_crashing)
    produces a Lattice shape that CRASHES trace_path outright. Both facts
    are independently tested and true today; this test makes the
    interaction between them explicit rather than leaving it undiscovered.
    STRICT RULE this session: do not modify trace_path -- this is a
    documentation test, not a regression guard for a fix.

    Needs actual ink (a connecting stroke) in the binary mask -- an
    all-zero mask short-circuits at trace_path's own
    `if len(sk_pixels) == 0: return []` before ever reaching the crash,
    which is why _square_binary_with_perimeter_strokes-style ink is used
    here rather than a blank canvas."""
    binary, _centers = _square_binary_with_perimeter_strokes(
        centers=[(100, 100), (300, 300)], radius=8
    )
    preprocessed = image_io.Preprocessed(binary=binary, rotation_deg=0.0)
    asymmetric_lattice = image_io.Lattice([(100.0, 100.0), (300.0, 300.0)], [], 8.0)

    # assert_conforms's structural check does NOT catch this -- 0 coords
    # is a legal value of the "0 or n_pixels" invariant. This is called
    # out explicitly (both here and in engine/ml_contract.py's
    # docstring) so nobody mistakes assert_conforms for a complete guard.
    assert_conforms(asymmetric_lattice)  # does not raise -- shape "passes"

    with pytest.raises(IndexError):
        image_io.trace_path(preprocessed, asymmetric_lattice)


def test_contract_recommended_collapse_to_fully_empty_avoids_the_blocker():
    """docs/ML_CONTRACT.md's recommendation for detectors -- collapse a
    1-2-point degenerate detection to FULLY empty (Lattice([], [], 0.0))
    rather than reproducing the asymmetric shape -- actually avoids the
    crash proven above."""
    preprocessed = image_io.Preprocessed(binary=np.zeros((400, 400), dtype=np.uint8), rotation_deg=0.0)
    safely_collapsed_lattice = image_io.Lattice([], [], 0.0)
    assert image_io.trace_path(preprocessed, safely_collapsed_lattice) == []


# ============================================================
# Regression coverage for the upstream gate (engine.image_io.is_traceable)
# added alongside these tests -- NOT a change to trace_path itself (the
# test above still proves trace_path crashes on a direct, ungated call).
# The gate is applied by engine.image_io.build_graph and by
# validate_real_photos.py; this section proves both the gate function
# itself and build_graph's real (not test-local) behavior on an image
# that organically produces the asymmetric shape.
# ============================================================


def test_is_traceable_flags_the_asymmetric_shape_false():
    asymmetric_lattice = image_io.Lattice([(100.0, 100.0), (300.0, 300.0)], [], 8.0)
    assert image_io.is_traceable(asymmetric_lattice) is False


def test_is_traceable_true_for_empty_and_well_formed_lattices():
    assert image_io.is_traceable(image_io.Lattice([], [], 0.0)) is True
    well_formed = image_io.Lattice([(1.0, 1.0), (2.0, 2.0)], [(0, 0), (1, 1)], 1.0)
    assert image_io.is_traceable(well_formed) is True


def test_build_graph_no_longer_crashes_on_an_image_that_naturally_triggers_the_asymmetric_shape(tmp_path):
    """Regression test for the fix: an image whose detect_lattice output
    organically lands in the documented asymmetric shape (2 detected dot
    blobs, too few to fit a lattice -- the same real-world shape that
    crashed on kolam_india12_mckaysavage.jpg, see PROJECT_STATE.md M4.0
    report) no longer raises IndexError through build_graph, the
    project's single public image->graph entry point. It collapses to an
    empty graph (0 nodes, 0 edges), matching docs/ML_CONTRACT.md's
    recommended empty-detection convention -- NOT a silently repaired/
    invented graph."""
    binary, _centers = _square_binary_with_perimeter_strokes(centers=[(100, 100), (300, 300)], radius=8)
    img_path = tmp_path / "two_dot_image.png"
    cv2.imwrite(str(img_path), binary)

    G = image_io.build_graph(str(img_path))  # must not raise

    assert isinstance(G, nx.MultiGraph)
    assert G.number_of_nodes() == 0
    assert G.number_of_edges() == 0
