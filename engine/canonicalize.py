"""EXPERIMENTAL alternative preprocessing for the ML detector ONLY.

Does NOT modify or replace `engine.image_io.preprocess()`, which remains
the classical detector's untouched, frozen preprocessing path, and
remains what `detector=ml` (ungated, production) receives by default
per `docs/ML_CONTRACT.md` ("An ML detector receives the SAME
Preprocessed object every current caller receives"). This module is a
NEW, opt-in preprocessing variant, built to test whether closing the
illumination/contrast gap between synthetic renders and real photos
(the domain-gap finding in `docs/M4_1_ML_COMPLETION_REPORT.md` Section 7
— real no-dot photos reach ML confidence 0.93-0.98, i.e. the model is
confidently wrong, not merely under-confident) improves the EXISTING
`DotHeatmapNetV2` checkpoint's real-photo behavior. No model change, no
retraining, no new checkpoint.

Deterministic and geometry-preserving only: no dot positions are
invented, no generative/image-to-image model is used, no
topology-altering operation is applied. Every variant ends in a
single-channel uint8 foreground mask (0 = background, 255 = ink) in the
SAME format `engine.image_io.preprocess()` already produces, so the
same downstream resize/model-input path
(`experiments/m4_2/model.py`'s `MODEL_INPUT_SIZE`) works unchanged.

The rotation-deskew step below intentionally MIRRORS
`engine.image_io.preprocess()`'s own minAreaRect-based logic (NOT
imported) -- this experimental module must not import from or modify
`engine/image_io.py`, the untouched, frozen classical-detector path.
Duplicating this small block is the same discipline
`engine/novel_generation.py::_stamp_contribution`'s docstring already
documents for an analogous situation elsewhere in this project.
"""

from __future__ import annotations

import cv2
import numpy as np

VARIANTS = ("A", "B", "C", "D", "E", "F", "G")

VARIANT_DESCRIPTIONS = {
    "A": "grayscale + global Otsu threshold (== current production engine.image_io.preprocess() behavior, the baseline)",
    "B": "grayscale + CLAHE (local contrast) + global Otsu threshold",
    "C": "grayscale + illumination normalization (flat-field background division) + global Otsu threshold",
    "D": "grayscale + CLAHE + adaptive (local) threshold + light morphological opening",
    "E": "grayscale + illumination normalization + adaptive (local) threshold + light morphological opening",
    "F": "grayscale + illumination normalization + adaptive threshold + SMALL-COMPONENT removal "
         "(area-based, not morphological opening -- deliberately gentler on closely-spaced dots, "
         "see _remove_small_components docstring)",
    "G": "border/watermark crop + variant F's recipe -- for images with a non-kolam text/border region",
}


def _deskew(binary: np.ndarray) -> tuple[np.ndarray, float]:
    """Mirrors engine.image_io.preprocess()'s rotation-correction logic
    exactly (see module docstring for why this is duplicated, not
    imported): fit a minAreaRect to the ink mask's nonzero pixels,
    correct toward the nearest multiple of 45 degrees (kolams are
    typically drawn diamond- or axis-aligned), warp-affine with
    nearest-neighbor interpolation (preserves the binary 0/255 range
    exactly, no gray fringing)."""
    ys, xs = np.nonzero(binary)
    if len(xs) < 10:
        return binary, 0.0
    pts = np.column_stack([xs, ys]).astype(np.float32)
    (_, _), (_, _), angle = cv2.minAreaRect(pts)
    candidates = [0.0, 45.0, -45.0, 90.0, -90.0]
    target = min(candidates, key=lambda c: abs(((angle - c) + 45) % 90 - 45))
    rotation = angle - target
    h, w = binary.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), rotation, 1.0)
    deskewed = cv2.warpAffine(binary, M, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
    return deskewed, rotation


def _illumination_normalize(gray: np.ndarray, blur_frac: float = 0.05) -> np.ndarray:
    """Flat-field / background-subtraction normalization: divide by a
    heavily-blurred version of itself (the estimated local illumination
    field), rescaled to [0, 255]. Removes large-scale shadows/gradients
    while preserving fine ink-vs-background contrast -- real photos'
    dominant documented failure mode (low, UNEVEN contrast, e.g.
    kolam2_tshrinivasan.jpg: gray mean 62.5) is exactly this kind of
    illumination unevenness, which a purely global brightness/contrast
    synthetic-degradation pass never fully models."""
    h, w = gray.shape
    ksize = max(3, int(min(h, w) * blur_frac) | 1)  # force odd
    background = cv2.GaussianBlur(gray, (ksize, ksize), 0)
    normalized = cv2.divide(gray.astype(np.float32), background.astype(np.float32) + 1e-3, scale=255.0)
    return np.clip(normalized, 0, 255).astype(np.uint8)


def _clahe(gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def _global_otsu(gray: np.ndarray) -> np.ndarray:
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary


def _adaptive_threshold(gray: np.ndarray) -> np.ndarray:
    block = max(11, (min(gray.shape) // 20) | 1)  # force odd, >= 11 (cv2 requirement)
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block, 5)


def _morphological_cleanup(binary: np.ndarray) -> np.ndarray:
    """Light opening only -- removes isolated single-pixel noise specks
    without eroding real dot/stroke structure (kernel deliberately tiny,
    3x3, one iteration; never closing/dilating, which could invent
    structure that was not in the image)."""
    kernel = np.ones((3, 3), np.uint8)
    return cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)


def _remove_small_components(binary: np.ndarray, min_area_frac: float = 2e-5) -> np.ndarray:
    """Connected-component AREA filtering: drop foreground components
    smaller than `min_area_frac` of the total image area. Deliberately
    NOT morphological opening/erosion -- opening can merge or erase
    tightly-packed dots in a dense pattern (kernel touches every
    component indiscriminately by shape); this instead removes
    components by TOTAL SIZE only, so a real dot (a compact blob, even
    a small one) survives as long as it's not sub-pixel noise, while
    isolated single/few-pixel specks (JPEG artifacts, dust, grain) are
    dropped without touching any surviving component's shape or
    boundary at all. `min_area_frac` is scaled to image area (not a
    fixed pixel count) so this behaves consistently across the wildly
    different real-photo resolutions in this project's corpus (293px to
    9248px on a side)."""
    n_labels, labels, stats, _centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
    total_area = binary.shape[0] * binary.shape[1]
    min_area = max(1, int(total_area * min_area_frac))
    keep = np.zeros_like(binary)
    for label in range(1, n_labels):  # label 0 is background
        if stats[label, cv2.CC_STAT_AREA] >= min_area:
            keep[labels == label] = 255
    return keep


def _crop_border(gray: np.ndarray, margin_frac: float = 0.08) -> np.ndarray:
    """Crop a fixed fractional margin from every edge -- a simple,
    deterministic heuristic for removing a border/watermark/caption
    region near the image edges (per this task's "dense kolam with a
    watermark/text region near the bottom" description) WITHOUT
    attempting content-aware watermark detection (out of scope for this
    sprint, and risks cropping real kolam structure on an image where
    the watermark assumption doesn't hold). `margin_frac` intentionally
    small and applied to ALL four edges symmetrically, not just the
    bottom, so this stays a safe, geometry-preserving crop rather than a
    targeted (and therefore fragile) watermark detector."""
    h, w = gray.shape
    my, mx = int(h * margin_frac), int(w * margin_frac)
    return gray[my : h - my, mx : w - mx]


def canonicalize(image_path: str, variant: str = "E") -> tuple[np.ndarray, float]:
    """image path -> (deskewed binary uint8 ink mask, rotation_deg).
    Same return SHAPE as engine.image_io.Preprocessed's two fields
    (.binary, .rotation_deg), so a caller can build
    `engine.image_io.Preprocessed(binary, rotation_deg)` directly and
    hand it to any MLLatticeDetector unchanged -- this function does not
    construct a Preprocessed itself, to avoid importing engine.image_io
    (see module docstring)."""
    if variant not in VARIANTS:
        raise ValueError(f"unknown canonicalization variant {variant!r}, must be one of {VARIANTS}")
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"could not read image: {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if variant == "G":
        gray = _crop_border(gray)

    if variant == "A":
        binary = _global_otsu(gray)
    elif variant == "B":
        binary = _global_otsu(_clahe(gray))
    elif variant == "C":
        binary = _global_otsu(_illumination_normalize(gray))
    elif variant == "D":
        binary = _morphological_cleanup(_adaptive_threshold(_clahe(gray)))
    elif variant == "E":
        binary = _morphological_cleanup(_adaptive_threshold(_illumination_normalize(gray)))
    else:  # "F" or "G"
        binary = _remove_small_components(_adaptive_threshold(_illumination_normalize(gray)))

    return _deskew(binary)
