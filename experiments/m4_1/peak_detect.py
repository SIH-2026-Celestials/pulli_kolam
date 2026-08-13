"""M4.1 Phase 5 helper: turn a probability heatmap into a list of
distinct peak coordinates. Separated from ml_lattice_detector.py so it
has its own focused, model-independent tests (Phase 6's "duplicate
suppression" test target) -- pure numpy, no torch dependency, testable
on a hand-built array."""

from __future__ import annotations

import numpy as np


def detect_peaks(heatmap: np.ndarray, threshold: float, min_distance_px: float) -> tuple[list, list]:
    """Simple greedy non-max suppression: repeatedly take the highest
    remaining value above `threshold`, record it, then zero out every
    pixel within `min_distance_px` of it (in heatmap-array units) before
    picking the next one. Deterministic (no randomness, stable order via
    np.argmax's own tie-breaking on a copied array).

    Returns (peaks, confidences) where peaks is a list of (row, col)
    float tuples in HEATMAP-array space (caller rescales to image
    pixels) and confidences is the heatmap value at each peak, same
    order. Both lists are empty if nothing clears `threshold`."""
    work = heatmap.copy()
    peaks: list[tuple[float, float]] = []
    confidences: list[float] = []
    h, w = work.shape
    yy, xx = np.mgrid[0:h, 0:w]

    while True:
        idx = np.argmax(work)
        val = work.flat[idx]
        if val < threshold:
            break
        r, c = divmod(int(idx), w)
        peaks.append((float(r), float(c)))
        confidences.append(float(val))

        dist = np.sqrt((yy - r) ** 2 + (xx - c) ** 2)
        work[dist <= min_distance_px] = -np.inf

    return peaks, confidences
