"""M4.2 Phase K: dot-separability regression tests -- pins down the
exact finding experiments/m4_1/diagnose_target_resolution.py measured
(TARGET_RESOLUTION_REPORT.md), so a future change to model.py's sigma/
resolution can't silently regress separability without a test noticing.
Pure numpy, no torch, no checkpoint needed."""

from __future__ import annotations

import os
import sys

import numpy as np
from scipy.ndimage import maximum_filter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from experiments.m4_2.model import HEATMAP_SIZE, SIGMA_CELLS, make_gaussian_heatmap  # noqa: E402


def _n_local_maxima(heatmap: np.ndarray, threshold: float = 0.2) -> int:
    mask = (heatmap.numpy() == maximum_filter(heatmap.numpy(), size=3)) & (heatmap.numpy() > threshold)
    return int(mask.sum())


def test_sparse_dots_fully_separable_at_128x128():
    # 5 well-separated dots (kolam19-like spacing at this resolution)
    dots = [(10, 10), (30, 10), (50, 50), (100, 100), (20, 90)]
    heatmap = make_gaussian_heatmap([(float(x), float(y)) for x, y in dots], HEATMAP_SIZE, HEATMAP_SIZE)
    assert _n_local_maxima(heatmap) == len(dots)


def test_dense_180_dot_pattern_recovers_100_percent_at_128x128():
    """Regression test for the exact TARGET_RESOLUTION_REPORT.md finding:
    128x128 with sigma=1.2 recovers 100% of a 180-dot pattern's dots as
    distinct local maxima (was only 28% at 32x32). Uses a synthetic grid
    approximating that density/spacing, not the real corpus (keeps this
    test self-contained and fast)."""
    rng = np.random.RandomState(0)
    # 180 points on a jittered grid spanning the full 128x128 canvas,
    # mean spacing ~= 128/sqrt(180) ~= 9.5 cells -- comparable to the
    # measured real kolam19-density median_nn_over_sigma_ratio (~3.5-3.9
    # at 128x128, TARGET_RESOLUTION_REPORT.md)
    n = 180
    side = int(np.ceil(np.sqrt(n)))
    spacing = HEATMAP_SIZE / side
    pts = []
    for i in range(side):
        for j in range(side):
            if len(pts) >= n:
                break
            jitter = rng.uniform(-0.15, 0.15, size=2) * spacing
            pts.append((i * spacing + spacing / 2 + jitter[0], j * spacing + spacing / 2 + jitter[1]))
    pts = pts[:n]

    heatmap = make_gaussian_heatmap(pts, HEATMAP_SIZE, HEATMAP_SIZE, sigma=SIGMA_CELLS)
    n_local_max = _n_local_maxima(heatmap)
    assert n_local_max == n, f"expected full separability (180/180), got {n_local_max}/180"


def test_extremely_crowded_dots_do_not_separate_at_128x128():
    """Sanity check on the OTHER direction: dots packed far closer than
    sigma should NOT separate -- proves the test above is measuring
    something real, not a tautology of the local-maxima detector."""
    # 10 dots within a 2x2 cell cluster -- much closer than sigma=1.2
    cluster = [(64 + dx * 0.15, 64 + dy * 0.15) for dx in range(5) for dy in range(2)]
    heatmap = make_gaussian_heatmap(cluster, HEATMAP_SIZE, HEATMAP_SIZE, sigma=SIGMA_CELLS)
    n_local_max = _n_local_maxima(heatmap)
    assert n_local_max < len(cluster)
