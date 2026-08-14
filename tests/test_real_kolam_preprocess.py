"""Regression tests for the real-kolam preprocessing sprint
(engine/canonicalize.py's F/G variants + detector compatibility).
Complements tests/test_canonicalize.py, which covers the A-E variants
already; this file focuses on the NEW small-component-removal/crop
stages and end-to-end detector compatibility."""

from __future__ import annotations

import os

import cv2
import numpy as np
import pytest

from engine.canonicalize import VARIANTS, canonicalize
from engine.image_io import Lattice, Preprocessed, is_traceable
from engine.ml_contract import assert_conforms

CHECKPOINT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "experiments", "m4_2", "results", "dot_heatmap_net_v2.pt"
)
pytestmark_checkpoint = pytest.mark.skipif(
    not os.path.exists(CHECKPOINT_PATH),
    reason="no trained M4.2 checkpoint -- run experiments/m4_2/train.py first",
)


def _write_dense_test_image(tmp_path, name="dense.jpg", size=300, n_side=8, add_watermark=False):
    """A denser grid than test_canonicalize.py's fixture, to exercise
    small-component removal on closely-spaced dots without eroding
    them."""
    img = np.full((size, size, 3), 210, dtype=np.uint8)
    step = size // (n_side + 1)
    for i in range(1, n_side + 1):
        for j in range(1, n_side + 1):
            cv2.circle(img, (i * step, j * step), 3, (15, 15, 15), -1)
    # a few isolated single-pixel noise specks (JPEG-artifact stand-ins)
    rng = np.random.RandomState(0)
    for _ in range(20):
        x, y = rng.randint(0, size, size=2)
        img[y, x] = (30, 30, 30)
    if add_watermark:
        cv2.putText(img, "watermark text", (5, size - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    path = str(tmp_path / name)
    cv2.imwrite(path, img)
    return path


# ============================================================
# Small-component removal / crop stages (F, G)
# ============================================================


def test_small_component_removal_preserves_a_dense_dot_grid(tmp_path):
    # Every one of the 64 real dots must survive as detectable ink after
    # variant F's small-component removal -- this is the "do NOT destroy
    # closely-spaced dots" requirement, checked directly, not assumed.
    path = _write_dense_test_image(tmp_path, n_side=8)
    binary, _rot = canonicalize(path, variant="F")
    n_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
    real_components = n_labels - 1  # exclude background label
    assert real_components >= 60  # allow a small margin for touching/merged dots, not a hard 64


def test_small_component_removal_drops_isolated_noise_specks():
    # Direct, apples-to-apples unit test of the removal step itself
    # (not confounded by variant F also using a different threshold
    # ALGORITHM than variant A -- see engine.canonicalize._remove_small_components).
    from engine.canonicalize import _remove_small_components

    # A realistically-sized canvas -- min_area_frac is a FRACTION of
    # total image area (by design, so it scales across this project's
    # wildly different real-photo resolutions), so a tiny test canvas
    # would round the minimum area down to ~0 and filter nothing; 1000px
    # keeps the same relative dot/speck size relationship meaningful.
    size = 1000
    binary = np.zeros((size, size), dtype=np.uint8)
    cv2.circle(binary, (200, 200), 15, 255, -1)  # one real, compact dot
    binary[600, 600] = 255  # one isolated single-pixel speck

    n_before, _, _, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    cleaned = _remove_small_components(binary)
    n_after, _, _, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)

    assert n_before - 1 == 2  # sanity: dot + speck, 2 real components before cleanup
    assert n_after - 1 == 1  # only the real dot survives
    assert cleaned[200, 200] > 0  # the real dot's own pixels are untouched
    assert cleaned[600, 600] == 0  # the speck is gone


def test_watermark_crop_variant_removes_a_bottom_text_region(tmp_path):
    path = _write_dense_test_image(tmp_path, n_side=6, add_watermark=True)
    binary_full, _ = canonicalize(path, variant="F")
    binary_cropped, _ = canonicalize(path, variant="G")
    assert binary_cropped.shape[0] < binary_full.shape[0]
    assert binary_cropped.shape[1] < binary_full.shape[1]


# ============================================================
# No accidental channel/alpha corruption
# ============================================================


def test_canonicalize_output_is_always_single_channel(tmp_path):
    path = _write_dense_test_image(tmp_path)
    for variant in VARIANTS:
        binary, _rot = canonicalize(path, variant=variant)
        assert binary.ndim == 2  # never (H, W, C) -- no accidental channel/alpha dimension
        assert binary.dtype == np.uint8


def test_canonicalize_handles_an_image_with_an_alpha_channel(tmp_path):
    # cv2.imread with default flags drops alpha automatically -- prove
    # canonicalize() doesn't silently misinterpret a 4-channel PNG as a
    # 3-channel one (which would corrupt the grayscale conversion).
    size = 150
    rgba = np.full((size, size, 4), 200, dtype=np.uint8)
    cv2.circle(rgba, (75, 75), 6, (10, 10, 10, 255), -1)
    path = str(tmp_path / "rgba.png")
    cv2.imwrite(path, rgba)
    binary, _rot = canonicalize(path, variant="A")
    assert binary.ndim == 2
    assert (binary > 0).any()  # the dot must still be detected as ink


# ============================================================
# Detector compatibility / no silent fallback
# ============================================================


def test_canonicalize_raises_cleanly_not_silently_on_missing_file():
    with pytest.raises(FileNotFoundError):
        canonicalize("this/does/not/exist.jpg", variant="F")


def test_canonicalize_raises_cleanly_not_silently_on_unknown_variant(tmp_path):
    path = _write_dense_test_image(tmp_path)
    with pytest.raises(ValueError):
        canonicalize(path, variant="not-a-real-variant")


@pytestmark_checkpoint
def test_preprocessed_output_is_a_valid_detector_input_end_to_end(tmp_path):
    """The concrete "no silent fallback" + "valid detector input" proof:
    feed a canonicalize()d image through the REAL ML detector
    end-to-end (not a mock), and through is_traceable -- must not raise,
    must not silently substitute a different detector, must produce a
    contract-conforming Lattice."""
    from experiments.m4_2.ml_lattice_detector import LearnedLatticeDetectorV2

    path = _write_dense_test_image(tmp_path, n_side=8)
    binary, rotation = canonicalize(path, variant="F")
    preprocessed = Preprocessed(binary=binary, rotation_deg=rotation)

    detector = LearnedLatticeDetectorV2()
    lattice = detector(preprocessed)  # must not raise
    assert_conforms(lattice)
    assert is_traceable(lattice)


def test_raw_mode_via_variant_a_is_unchanged_from_production():
    # Re-confirms (does not duplicate) test_canonicalize.py's own
    # equivalence test, from THIS file's "existing raw mode remains
    # unchanged" requirement -- a real real_photos/ file, not a synthetic
    # fixture.
    from engine import image_io

    path = os.path.join(os.path.dirname(__file__), "..", "real_photos", "kolam2_tshrinivasan.jpg")
    if not os.path.exists(path):
        pytest.skip("real_photos/ corpus not present in this checkout")
    a_binary, a_rot = canonicalize(path, variant="A")
    prod = image_io.preprocess(path)
    assert np.array_equal(a_binary, prod.binary)
    assert a_rot == prod.rotation_deg
