"""Real-photograph quality/normalization diagnostics -- OBJECTIVE 5 of
the M5 real-photo pipeline: measure what makes a photo hard to recognize
BEFORE handing it to a detector, so a failure can be attributed to "the
photo is low quality" rather than silently blamed on the detector (or
worse, silently ignored).

Pure measurement module: nothing here fabricates a pass/fail verdict --
every field is a real, directly computed statistic. `assess_quality`
returns the numbers; callers (e.g. the real-photo experiment script)
decide what to do with them.

NORMALIZATION: `normalize_for_recognition` reuses engine.image_io.preprocess
UNMODIFIED (rotation-only deskew + Otsu binarization, the same pipeline
every detector already runs against) -- this module does not reimplement
or replace it, only measures the INPUT before that pipeline runs and
saves the intermediate outputs for debugging, per the "keep the original
image untouched, save every transformed intermediate" requirement.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

from engine.image_io import Preprocessed, preprocess


@dataclass
class ImageQuality:
    path: str
    width: int
    height: int
    aspect_ratio: float
    brightness_mean: float  # grayscale mean, 0-255
    contrast_std: float  # grayscale std, 0-255
    blur_score: float  # variance of Laplacian -- lower = blurrier
    estimated_rotation_deg: float  # from engine.image_io.preprocess's minAreaRect estimate
    background_complexity: float  # Canny edge-pixel fraction, 0-1 -- higher = busier background
    foreground_ink_fraction: float  # fraction of pixels classified as ink by Otsu binarization
    estimated_crop_quality: float  # fraction of the frame the ink bounding box actually occupies, 0-1

    def to_dict(self) -> dict:
        return asdict(self)


def _blur_score(gray: np.ndarray) -> float:
    """Variance of the Laplacian -- a standard, simple focus-quality proxy
    (sharp edges produce high-variance second derivatives; blur smooths
    them out). Not a learned metric, does not require any model/checkpoint."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _background_complexity(gray: np.ndarray) -> float:
    """Fraction of pixels flagged as an edge by Canny -- a rough proxy for
    how busy/cluttered the background is (a clean floor/mat has far fewer
    edges than a patterned surface or cluttered scene)."""
    edges = cv2.Canny(gray, 50, 150)
    return float(np.count_nonzero(edges)) / edges.size


def assess_quality(image_path: str) -> ImageQuality:
    """Compute every quality statistic directly from the ORIGINAL image
    (not a detector's internal representation) -- this function never
    calls a detector and never requires a trained checkpoint."""
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"could not read image: {image_path}")
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    pre: Preprocessed = preprocess(image_path)
    ink_fraction = float(np.count_nonzero(pre.binary)) / pre.binary.size

    ys, xs = np.nonzero(pre.binary)
    if len(xs) >= 2:
        bbox_area = (xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1)
        crop_quality = float(bbox_area) / (pre.binary.shape[0] * pre.binary.shape[1])
    else:
        crop_quality = 0.0

    return ImageQuality(
        path=image_path,
        width=w,
        height=h,
        aspect_ratio=w / h if h else 0.0,
        brightness_mean=float(gray.mean()),
        contrast_std=float(gray.std()),
        blur_score=_blur_score(gray),
        estimated_rotation_deg=pre.rotation_deg,
        background_complexity=_background_complexity(gray),
        foreground_ink_fraction=ink_fraction,
        estimated_crop_quality=crop_quality,
    )


def normalize_for_recognition(image_path: str, debug_dir: "str | Path | None" = None) -> Preprocessed:
    """Run engine.image_io.preprocess (unmodified) and, if `debug_dir` is
    given, save every intermediate it produces -- grayscale, the
    deskewed binary mask -- as separate files, WITHOUT touching or
    overwriting the original image, so a failure can be visually
    inspected after the fact."""
    pre = preprocess(image_path)
    if debug_dir is not None:
        debug_dir = Path(debug_dir)
        debug_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(image_path).stem
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cv2.imwrite(str(debug_dir / f"{stem}_gray.png"), gray)
        cv2.imwrite(str(debug_dir / f"{stem}_binary_deskewed.png"), pre.binary)
    return pre
