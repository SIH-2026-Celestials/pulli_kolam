"""Tests for engine/canonicalize.py: the experimental, opt-in ML-only
preprocessing variants. Does not touch engine.image_io.preprocess() or
any classical-detector code -- these tests exist to prove that
independently."""

from __future__ import annotations

import os

import cv2
import numpy as np
import pytest

from engine import image_io
from engine.canonicalize import VARIANTS, canonicalize

SYNTHETIC_DIR = os.path.join(os.path.dirname(__file__), "..", "synthetic_photos")


def _write_test_image(tmp_path, name="test.jpg", size=200):
    """A simple synthetic dot-grid image, real ink on a real background
    -- not a hand-built binary array, so canonicalize()'s own
    cv2.imread/cvtColor path is genuinely exercised."""
    img = np.full((size, size, 3), 200, dtype=np.uint8)
    for cx in (50, 100, 150):
        for cy in (50, 100, 150):
            cv2.circle(img, (cx, cy), 6, (20, 20, 20), -1)
    path = str(tmp_path / name)
    cv2.imwrite(path, img)
    return path


def test_all_variants_produce_a_valid_binary_uint8_mask(tmp_path):
    path = _write_test_image(tmp_path)
    for variant in VARIANTS:
        binary, rotation = canonicalize(path, variant=variant)
        assert binary.dtype == np.uint8
        assert binary.ndim == 2
        assert set(np.unique(binary)).issubset({0, 255})
        assert isinstance(rotation, float)


def test_canonicalize_rejects_unknown_variant(tmp_path):
    path = _write_test_image(tmp_path)
    with pytest.raises(ValueError):
        canonicalize(path, variant="Z")


def test_canonicalize_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        canonicalize("does/not/exist.jpg", variant="A")


def test_canonicalize_is_deterministic(tmp_path):
    path = _write_test_image(tmp_path)
    for variant in VARIANTS:
        a_binary, a_rot = canonicalize(path, variant=variant)
        b_binary, b_rot = canonicalize(path, variant=variant)
        assert np.array_equal(a_binary, b_binary)
        assert a_rot == b_rot


def test_canonicalize_preserves_image_dimensions(tmp_path):
    # Variant G intentionally crops a border margin (see
    # engine.canonicalize._crop_border) -- excluded here on purpose,
    # covered by its own dedicated crop test below.
    path = _write_test_image(tmp_path, size=300)
    for variant in VARIANTS:
        if variant == "G":
            continue
        binary, _rot = canonicalize(path, variant=variant)
        assert binary.shape == (300, 300)


def test_variant_g_crops_a_border_margin(tmp_path):
    path = _write_test_image(tmp_path, size=300)
    binary, _rot = canonicalize(path, variant="G")
    assert binary.shape[0] < 300
    assert binary.shape[1] < 300
    # margin_frac=0.08 on each side -> ~84% of original dimension remains
    assert 0.75 < binary.shape[0] / 300 < 0.95


def test_variant_a_matches_image_io_preprocess_exactly(tmp_path):
    # Variant A is explicitly documented as "== current production
    # engine.image_io.preprocess() behavior" -- prove that claim, not
    # just assert it in a docstring.
    path = _write_test_image(tmp_path)
    a_binary, a_rot = canonicalize(path, variant="A")
    prod = image_io.preprocess(path)
    assert np.array_equal(a_binary, prod.binary)
    assert a_rot == prod.rotation_deg


def test_illumination_normalized_variants_reduce_foreground_fraction_on_uneven_lighting(tmp_path):
    # The concrete, measured claim this module exists for: on an image
    # with a strong illumination gradient (simulating real-photo uneven
    # lighting), global-Otsu (variant A) should misclassify much more of
    # the image as "ink" than the illumination-normalized variants (C, E).
    size = 300
    img = np.zeros((size, size, 3), dtype=np.uint8)
    # a left-to-right brightness gradient background (simulates uneven lighting)
    for x in range(size):
        img[:, x, :] = int(40 + 180 * (x / size))
    for cx in (75, 150, 225):
        for cy in (75, 150, 225):
            cv2.circle(img, (cx, cy), 6, (0, 0, 0), -1)
    path = str(tmp_path / "gradient.jpg")
    cv2.imwrite(path, img)

    frac = {}
    for variant in VARIANTS:
        binary, _rot = canonicalize(path, variant=variant)
        frac[variant] = (binary > 0).mean()

    # illumination-normalized variants must produce a SMALLER (more
    # plausible) foreground fraction than the naive global-Otsu baseline
    assert frac["C"] < frac["A"]
    assert frac["E"] < frac["A"]


def test_canonicalize_module_does_not_import_image_io():
    # Sanity guard: engine.canonicalize must not import engine.image_io
    # at all (the rotation-deskew logic is intentionally duplicated, not
    # shared -- see module docstring) -- checked via the module's actual
    # namespace, not a naive text search (which would also match the
    # module's own docstring prose referencing image_io.preprocess()).
    from engine import canonicalize as canon_mod

    assert "image_io" not in vars(canon_mod)


@pytest.mark.skipif(
    not os.path.isdir(SYNTHETIC_DIR) or not os.listdir(SYNTHETIC_DIR),
    reason="synthetic_photos/ not generated -- run generate_synthetic_photos.py first",
)
def test_canonicalize_runs_on_a_real_synthetic_photo_without_crashing():
    sample = sorted(os.listdir(SYNTHETIC_DIR))
    jpgs = [f for f in sample if f.endswith(".jpg")]
    assert jpgs, "expected at least one synthetic photo"
    path = os.path.join(SYNTHETIC_DIR, jpgs[0])
    for variant in VARIANTS:
        binary, _rot = canonicalize(path, variant=variant)
        assert binary.ndim == 2
