"""M4.1 gating experiment: contract adapter tests for
experiments/m4_2/gated_ml_lattice_detector.py. Mirrors
test_ml_lattice_detector.py's structure and conventions exactly -- same
frozen contract, same checkpoint-skip pattern -- plus tests specific to
the gate itself: deterministic behavior, no-dot rejection, malformed
input, and end-to-end lattice/graph safety."""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from engine.image_io import Preprocessed, is_traceable, trace_path  # noqa: E402
from engine.ml_contract import MLLatticeDetector, assert_conforms  # noqa: E402
from experiments.m4_2.gated_ml_lattice_detector import (  # noqa: E402
    GatedLearnedLatticeDetectorV2,
    _lattice_residual_px,
)
from experiments.m4_2.ml_lattice_detector import CHECKPOINT_PATH, MalformedOutputError  # noqa: E402

pytestmark_checkpoint = pytest.mark.skipif(
    not os.path.exists(CHECKPOINT_PATH),
    reason="no trained M4.2 checkpoint -- run experiments/m4_2/train.py first",
)


def _blob_binary(centers, size=400, radius=8):
    binary = np.zeros((size, size), dtype=np.uint8)
    yy, xx = np.mgrid[0:size, 0:size]
    for cx, cy in centers:
        mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius**2
        binary[mask] = 255
    return binary


# ============================================================
# _lattice_residual_px: unit-level, isolated from the detector.
# ============================================================


def test_lattice_residual_is_none_below_three_points():
    assert _lattice_residual_px(np.array([[0.0, 0.0]])) is None
    assert _lattice_residual_px(np.array([[0.0, 0.0], [1.0, 1.0]])) is None


def test_lattice_residual_is_near_zero_for_a_perfect_grid():
    grid = np.array([[x * 20.0, y * 20.0] for x in range(5) for y in range(5)])
    resid = _lattice_residual_px(grid)
    assert resid is not None
    assert resid < 1e-6


def test_lattice_residual_is_large_for_scattered_points():
    rng_points = np.array(
        [[3.0, 91.0], [77.0, 12.0], [140.0, 205.0], [9.0, 300.0], [250.0, 40.0], [190.0, 260.0]]
    )
    scattered_resid = _lattice_residual_px(rng_points)
    grid = np.array([[x * 20.0, y * 20.0] for x in range(3) for y in range(3)])
    grid_resid = _lattice_residual_px(grid)
    assert scattered_resid > grid_resid


# ============================================================
# GatedLearnedLatticeDetectorV2
# ============================================================


def test_load_checkpoint_raises_on_missing_file():
    with pytest.raises(MalformedOutputError):
        GatedLearnedLatticeDetectorV2(checkpoint_path="experiments/m4_2/results/does_not_exist.pt")


@pytestmark_checkpoint
def test_gated_detector_satisfies_frozen_protocol():
    detector = GatedLearnedLatticeDetectorV2()
    assert isinstance(detector, MLLatticeDetector)


@pytestmark_checkpoint
def test_gated_detector_raises_on_malformed_binary_input():
    detector = GatedLearnedLatticeDetectorV2()
    bad_preprocessed = Preprocessed(binary=np.zeros((10, 10, 3), dtype=np.uint8), rotation_deg=0.0)
    with pytest.raises(MalformedOutputError):
        detector(bad_preprocessed)


@pytestmark_checkpoint
def test_gated_detector_deterministic_inference():
    detector = GatedLearnedLatticeDetectorV2()
    binary = _blob_binary([(100, 100), (300, 100), (300, 300), (100, 300), (200, 200)])
    preprocessed = Preprocessed(binary=binary, rotation_deg=0.0)
    a = detector(preprocessed)
    b = detector(preprocessed)
    assert a.pixel_positions == b.pixel_positions
    assert a.lattice_coords == b.lattice_coords


@pytestmark_checkpoint
def test_gated_detector_empty_prediction_on_blank_image():
    detector = GatedLearnedLatticeDetectorV2()
    preprocessed = Preprocessed(binary=np.zeros((400, 400), dtype=np.uint8), rotation_deg=0.0)
    lattice = detector(preprocessed)
    assert lattice.pixel_positions == []
    assert lattice.lattice_coords == []


@pytestmark_checkpoint
def test_gated_detector_output_conforms_to_frozen_contract():
    detector = GatedLearnedLatticeDetectorV2()
    binary = _blob_binary([(100, 100), (300, 100), (300, 300), (100, 300), (200, 200)])
    preprocessed = Preprocessed(binary=binary, rotation_deg=0.0)
    lattice = detector(preprocessed)
    assert_conforms(lattice)  # must not raise


@pytestmark_checkpoint
def test_gated_detector_rejects_a_geometrically_implausible_detection_set():
    # A tighter residual threshold than the default forces the gate to
    # reject even a plausible-looking small grid, proving the rejection
    # PATH itself (not just its trigger condition) is exercised: it
    # must collapse to the SAME safe empty convention as a genuinely
    # sparse detection, not a different failure shape.
    detector = GatedLearnedLatticeDetectorV2(lattice_residual_threshold_px=0.0)
    binary = _blob_binary([(100, 100), (300, 100), (300, 300), (100, 300), (200, 200)])
    preprocessed = Preprocessed(binary=binary, rotation_deg=0.0)
    lattice = detector(preprocessed)
    assert lattice.pixel_positions == []
    assert lattice.lattice_coords == []
    assert_conforms(lattice)


@pytestmark_checkpoint
def test_gated_detector_output_survives_the_is_traceable_boundary_without_crashing():
    # engine.image_io.trace_path is NEVER modified by this experiment --
    # this proves the gated detector's output (both the accept and the
    # reject path) is safe to hand to the EXISTING is_traceable gate
    # (Session 17) and trace_path unmodified.
    detector = GatedLearnedLatticeDetectorV2()
    binary = _blob_binary([(100, 100), (300, 100), (300, 300), (100, 300), (200, 200)])
    preprocessed = Preprocessed(binary=binary, rotation_deg=0.0)
    lattice = detector(preprocessed)
    assert is_traceable(lattice)  # a conforming detector's output must always be traceable
    edges = trace_path(preprocessed, lattice)  # must not raise
    assert isinstance(edges, list)


@pytestmark_checkpoint
def test_gated_detector_on_a_real_no_dot_photo_produces_empty_or_reduced_detections():
    # Integration check against the actual documented false-positive
    # case (docs/M4_1_ML_COMPLETION_REPORT.md) -- not a synthetic
    # fixture. Skips cleanly if the real-photo corpus isn't present in
    # this checkout, matching this project's established fixture-missing
    # skip convention.
    from engine import image_io

    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "real_photos", "kolam_india09_mckaysavage.jpg"
    )
    if not os.path.exists(path):
        pytest.skip("real_photos/ corpus not present in this checkout")

    detector = GatedLearnedLatticeDetectorV2()
    preprocessed = image_io.preprocess(path)
    lattice = detector(preprocessed)
    assert_conforms(lattice)
    assert is_traceable(lattice)
    # Not asserting n==0 unconditionally -- the gate is a measured,
    # partial mitigation (see docs/M4_1_ML_COMPLETION_REPORT.md), not a
    # guarantee for every no-dot image. This specific file IS one of the
    # cases the gate's own evaluation (gating_experiment.py) measured as
    # correctly rejected at the default threshold.
    assert lattice.pixel_positions == []
