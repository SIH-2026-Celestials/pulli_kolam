"""M4.2 Phase K: contract adapter tests for
experiments/m4_2/ml_lattice_detector.py. Mirrors
experiments/m4_1/tests/test_ml_lattice_detector.py's structure exactly
-- same frozen contract, same conventions, new model underneath.
Checkpoint-dependent tests skip cleanly if training hasn't produced one
yet (established skip-if-fixture-missing pattern)."""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from engine.image_io import Preprocessed  # noqa: E402
from engine.ml_contract import MLLatticeDetector, assert_conforms  # noqa: E402
from experiments.m4_2.ml_lattice_detector import (  # noqa: E402
    LearnedLatticeDetectorV2, MalformedOutputError, load_model, CHECKPOINT_PATH,
)

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


def test_load_model_raises_on_missing_checkpoint():
    with pytest.raises(MalformedOutputError):
        load_model(checkpoint_path="experiments/m4_2/results/does_not_exist.pt")


@pytestmark_checkpoint
def test_detector_raises_on_malformed_binary_input():
    detector = LearnedLatticeDetectorV2()
    bad_preprocessed = Preprocessed(binary=np.zeros((10, 10, 3), dtype=np.uint8), rotation_deg=0.0)
    with pytest.raises(MalformedOutputError):
        detector(bad_preprocessed)


@pytestmark_checkpoint
def test_detector_satisfies_frozen_protocol():
    detector = LearnedLatticeDetectorV2()
    assert isinstance(detector, MLLatticeDetector)


@pytestmark_checkpoint
def test_deterministic_inference_same_input_same_output():
    detector = LearnedLatticeDetectorV2()
    binary = _blob_binary([(100, 100), (300, 100), (300, 300), (100, 300), (200, 200)])
    preprocessed = Preprocessed(binary=binary, rotation_deg=0.0)
    a = detector(preprocessed)
    b = detector(preprocessed)
    assert a.pixel_positions == b.pixel_positions
    assert a.lattice_coords == b.lattice_coords


@pytestmark_checkpoint
def test_empty_prediction_on_blank_image():
    detector = LearnedLatticeDetectorV2()
    preprocessed = Preprocessed(binary=np.zeros((400, 400), dtype=np.uint8), rotation_deg=0.0)
    lattice = detector(preprocessed)
    assert lattice.pixel_positions == []
    assert lattice.lattice_coords == []


@pytestmark_checkpoint
def test_output_conforms_to_frozen_contract():
    detector = LearnedLatticeDetectorV2()
    binary = _blob_binary([(100, 100), (300, 100), (300, 300), (100, 300), (200, 200)])
    preprocessed = Preprocessed(binary=binary, rotation_deg=0.0)
    lattice = detector(preprocessed)
    assert_conforms(lattice)
    for (x, y) in lattice.pixel_positions:
        assert 0 <= x <= 400 and 0 <= y <= 400


@pytestmark_checkpoint
def test_output_survives_trace_path_without_crashing():
    from engine import image_io
    detector = LearnedLatticeDetectorV2()
    binary = _blob_binary([(100, 100), (300, 100), (300, 300), (100, 300), (200, 200)])
    preprocessed = Preprocessed(binary=binary, rotation_deg=0.0)
    lattice = detector(preprocessed)
    edges = image_io.trace_path(preprocessed, lattice)
    assert isinstance(edges, list)


@pytestmark_checkpoint
def test_sparse_detection_collapses_to_empty():
    detector = LearnedLatticeDetectorV2()
    binary = _blob_binary([(200, 200)], radius=3)
    preprocessed = Preprocessed(binary=binary, rotation_deg=0.0)
    lattice = detector(preprocessed)
    if 1 <= len(lattice.pixel_positions) <= 2:
        assert lattice.lattice_coords == []
        assert lattice.pixel_positions == []
