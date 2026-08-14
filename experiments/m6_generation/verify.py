"""M6 Phase 7: frozen-recognizer self-consistency verification.

Reuses api.detectors (unmodified -- the FROZEN DotHeatmapNetV2
checkpoint, see ARCHITECTURE.md Phase 1/section 8) and the SAME
ground-truth-pixel-position technique
experiments/m5_generation/run_generation_benchmark.py already
established: because the renderer is deterministic and the generator's
own dot_points are exactly known, "ground truth" here is not a human
label -- it is the generator's own output, compared against what a
FROZEN, previously-trained detector reads back off the rendered image.

This is NOT real-photo evaluation and is never reported as one -- no
precision/recall claim from this module ever gets described as
real-photo accuracy (see ARCHITECTURE.md's real-photo section / M5's
own explicit real-photo honesty rules, which this module inherits by
citing them, not by re-deriving new ones).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

MATCH_TOLERANCE_PX = 8.0


@dataclass
class VerificationResult:
    detector: str
    available: bool
    n_expected: int
    n_detected: int
    recall: "float | None"
    precision: "float | None"
    mean_localization_error_px: "float | None"
    error: "str | None" = None

    def to_dict(self) -> dict:
        return {
            "detector": self.detector, "available": self.available, "n_expected": self.n_expected,
            "n_detected": self.n_detected, "recall": self.recall, "precision": self.precision,
            "mean_localization_error_px": self.mean_localization_error_px, "error": self.error,
        }


def _ground_truth_pixels(dot_points: "list[tuple[int, int]]", scale: float, margin: float) -> list:
    if not dot_points:
        return []
    xs = [p[0] for p in dot_points]
    ys = [p[1] for p in dot_points]
    min_x, min_y = min(xs), min(ys)
    return [(margin + (p[0] - min_x) * scale, margin + (p[1] - min_y) * scale) for p in dot_points]


def verify_with_recognizer(
    png_path: str, dot_points: "list[tuple[int, int]]", scale: float, margin: float,
    detector_name: str = "ml-gated",
) -> VerificationResult:
    """Run ONE frozen detector against a rendered candidate image and
    compare its detections to the generator's own exact ground truth
    (same to_px transform engine.render used to draw them)."""
    from api.detectors import get_detector

    gt_px = _ground_truth_pixels(dot_points, scale, margin)
    n_gt = len(gt_px)

    try:
        detector = get_detector(detector_name)
        result = detector.detect(png_path)
    except Exception as e:  # noqa: BLE001
        return VerificationResult(
            detector=detector_name, available=False, n_expected=n_gt, n_detected=0,
            recall=None, precision=None, mean_localization_error_px=None,
            error=f"{type(e).__name__}: {e}",
        )

    detected = result.dots
    n_det = len(detected)
    if n_gt == 0:
        return VerificationResult(detector_name, True, 0, n_det, None, None, None)
    if n_det == 0:
        return VerificationResult(detector_name, True, n_gt, 0, 0.0, None, None)

    gt_arr = np.array(gt_px)
    det_arr = np.array(detected)
    tree = cKDTree(det_arr)
    dist, _idx = tree.query(gt_arr)
    matched = dist < MATCH_TOLERANCE_PX
    n_matched = int(matched.sum())
    errors = dist[matched]

    return VerificationResult(
        detector=detector_name, available=True, n_expected=n_gt, n_detected=n_det,
        recall=n_matched / n_gt, precision=n_matched / n_det,
        mean_localization_error_px=float(errors.mean()) if len(errors) else None,
    )
