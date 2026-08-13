"""M4.1 Phase 6: focused tests for the contract adapter
(experiments/m4_1/ml_lattice_detector.py). Tests that need a trained
checkpoint are skipped (not failed) if one doesn't exist yet, matching
the established skip-if-fixture-missing pattern already used in
tests/test_image_io.py for synthetic_photos/.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from engine.image_io import Preprocessed, Lattice  # noqa: E402
from engine.ml_contract import MLLatticeDetector, assert_conforms  # noqa: E402
from experiments.m4_1.ml_lattice_detector import (  # noqa: E402
    LearnedLatticeDetector, MalformedOutputError, load_model, CHECKPOINT_PATH,
)

pytestmark_checkpoint = pytest.mark.skipif(
    not os.path.exists(CHECKPOINT_PATH),
    reason="no trained checkpoint -- run experiments/m4_1/train.py first",
)


def _blob_binary(centers, size=400, radius=8):
    binary = np.zeros((size, size), dtype=np.uint8)
    yy, xx = np.mgrid[0:size, 0:size]
    for cx, cy in centers:
        mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius**2
        binary[mask] = 255
    return binary


# ============================================================
# 1. Model output shape (no checkpoint needed -- random-init weights are
#    fine for a pure shape check)
# ============================================================


def test_model_output_shape():
    import torch
    from experiments.m4_1.model import DotHeatmapNet, MODEL_INPUT_SIZE, STRIDE

    model = DotHeatmapNet()
    model.eval()
    x = torch.zeros((1, 1, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE))
    with torch.no_grad():
        out = model(x)
    assert out.shape == (1, 1, MODEL_INPUT_SIZE // STRIDE, MODEL_INPUT_SIZE // STRIDE)


# ============================================================
# 6. Malformed prediction / missing checkpoint rejection (no trained
#    checkpoint needed -- this specifically tests the ABSENCE case)
# ============================================================


def test_load_model_raises_on_missing_checkpoint():
    with pytest.raises(MalformedOutputError):
        load_model(checkpoint_path="experiments/m4_1/results/does_not_exist.pt")


def test_detector_raises_on_malformed_binary_input():
    if not os.path.exists(CHECKPOINT_PATH):
        pytest.skip("no trained checkpoint -- run experiments/m4_1/train.py first")
    detector = LearnedLatticeDetector()
    bad_preprocessed = Preprocessed(binary=np.zeros((10, 10, 3), dtype=np.uint8), rotation_deg=0.0)  # 3D, invalid
    with pytest.raises(MalformedOutputError):
        detector(bad_preprocessed)


# ============================================================
# 2-5, 7-8: full adapter behavior -- requires a trained checkpoint
# ============================================================


@pytestmark_checkpoint
def test_detector_satisfies_frozen_protocol():
    detector = LearnedLatticeDetector()
    assert isinstance(detector, MLLatticeDetector)


@pytestmark_checkpoint
def test_deterministic_inference_same_input_same_output():
    detector = LearnedLatticeDetector()
    binary = _blob_binary([(100, 100), (300, 100), (300, 300), (100, 300), (200, 200)])
    preprocessed = Preprocessed(binary=binary, rotation_deg=0.0)

    lattice_a = detector(preprocessed)
    lattice_b = detector(preprocessed)

    assert lattice_a.pixel_positions == lattice_b.pixel_positions
    assert lattice_a.lattice_coords == lattice_b.lattice_coords


@pytestmark_checkpoint
def test_empty_prediction_on_blank_image():
    detector = LearnedLatticeDetector()
    preprocessed = Preprocessed(binary=np.zeros((400, 400), dtype=np.uint8), rotation_deg=0.0)
    lattice = detector(preprocessed)
    assert lattice.pixel_positions == []
    assert lattice.lattice_coords == []


@pytestmark_checkpoint
def test_output_conforms_to_frozen_contract_on_a_real_dot_pattern():
    detector = LearnedLatticeDetector()
    binary = _blob_binary([(100, 100), (300, 100), (300, 300), (100, 300), (200, 200)])
    preprocessed = Preprocessed(binary=binary, rotation_deg=0.0)
    lattice = detector(preprocessed)
    assert_conforms(lattice)  # must not raise
    # coordinate normalization: pixel positions stay within image bounds
    for (x, y) in lattice.pixel_positions:
        assert 0 <= x <= 400 and 0 <= y <= 400


@pytestmark_checkpoint
def test_output_survives_trace_path_without_crashing():
    """Downstream compatibility smoke test, mirroring
    tests/test_ml_contract.py's mock-detector test but with the REAL
    learned detector this time. Per M4.1's own architectural rule, this
    must work with ZERO changes to trace_path."""
    from engine import image_io

    detector = LearnedLatticeDetector()
    binary = _blob_binary([(100, 100), (300, 100), (300, 300), (100, 300), (200, 200)])
    preprocessed = Preprocessed(binary=binary, rotation_deg=0.0)
    lattice = detector(preprocessed)

    edges = image_io.trace_path(preprocessed, lattice)  # must not raise
    assert isinstance(edges, list)


@pytestmark_checkpoint
def test_sparse_detection_collapses_to_empty_not_the_known_blocker_shape():
    """If the model finds 1-2 candidate peaks on a near-blank image, the
    adapter must collapse to fully empty (per docs/ML_CONTRACT.md's
    recommended convention) rather than reproducing the asymmetric
    Lattice shape known to crash trace_path (PROJECT_STATE.md's
    documented, unfixed blocker)."""
    detector = LearnedLatticeDetector()
    # a single tiny blob -- too sparse for a real detection
    binary = _blob_binary([(200, 200)], radius=3)
    preprocessed = Preprocessed(binary=binary, rotation_deg=0.0)
    lattice = detector(preprocessed)
    # either nothing detected, or (if >=3 somehow triggered) a valid fit --
    # never the 1-2-points-with-empty-coords shape
    assert len(lattice.lattice_coords) in (0, len(lattice.pixel_positions))
    if 1 <= len(lattice.pixel_positions) <= 2:
        assert lattice.lattice_coords == []
        assert lattice.pixel_positions == []  # adapter's stricter convention: collapse fully
