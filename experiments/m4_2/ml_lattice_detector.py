"""M4.2 Phase F: contract adapter for DotHeatmapNetV2 (native 128x128
output). Structurally identical in role to
experiments/m4_1/ml_lattice_detector.py -- same frozen
engine.ml_contract.MLLatticeDetector Protocol, same
engine.image_io._fit_lattice_coords reuse, same collapse-to-empty
convention for the documented (never fixed this session or any prior
one) trace_path IndexError blocker -- pointed at the NEW model/
checkpoint instead. engine/ml_contract.py itself is untouched.

Reuses experiments/m4_1/peak_detect.py UNMODIFIED -- that module's
detect_peaks() is resolution-agnostic (operates on whatever 2D array
it's given), so there is nothing 128x128-specific to change there.
"""

from __future__ import annotations

import os
import sys

import cv2
import numpy as np
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from engine.image_io import Lattice, Preprocessed, _fit_lattice_coords  # noqa: E402
from engine.ml_contract import assert_conforms  # noqa: E402
from experiments.m4_1.peak_detect import detect_peaks  # noqa: E402 -- reused unmodified, see module docstring
from experiments.m4_2.model import DotHeatmapNetV2, MODEL_INPUT_SIZE, OUTPUT_STRIDE  # noqa: E402

CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "results", "dot_heatmap_net_v2.pt")
MODEL_VERSION = "m4.2-128"

# Selected via Phase E's validation-only parameter sweep (25-point grid,
# experiments/m4_2/peak_sweep.py, run against experiments/m4_2/data/val
# -- NEVER the test set): best F1 (0.9993) at threshold=0.6,
# min_distance=2.0 -- see experiments/m4_2/results/peak_sweep.json for
# the full table and docs/M4_2_MODEL.md for the documented selection.
CONFIDENCE_THRESHOLD = 0.6
MIN_PEAK_DISTANCE_HEATMAP_CELLS = 2.0


class MalformedOutputError(RuntimeError):
    """Same purpose as M4.1's -- refuse to silently repair invalid
    model output into something that merely looks like a valid Lattice."""


def load_model(checkpoint_path: str = CHECKPOINT_PATH) -> DotHeatmapNetV2:
    if not os.path.exists(checkpoint_path):
        raise MalformedOutputError(
            f"no trained checkpoint at {checkpoint_path} -- run experiments/m4_2/train.py first."
        )
    model = DotHeatmapNetV2()
    state_dict = torch.load(checkpoint_path, map_location="cpu")
    model.load_state_dict(state_dict)
    model.eval()
    return model


class LearnedLatticeDetectorV2:
    """Callable object satisfying engine.ml_contract.MLLatticeDetector.
    __call__(self, preprocessed: Preprocessed) -> Lattice."""

    def __init__(self, checkpoint_path: str = CHECKPOINT_PATH):
        self.model = load_model(checkpoint_path)
        self.model_version = MODEL_VERSION

    def __call__(self, preprocessed: Preprocessed) -> Lattice:
        binary = preprocessed.binary
        if binary is None or binary.ndim != 2:
            raise MalformedOutputError(f"expected a 2D binary mask, got shape {getattr(binary, 'shape', None)}")

        h, w = binary.shape
        resized = cv2.resize(binary, (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE), interpolation=cv2.INTER_AREA)
        img_t = torch.from_numpy(resized.astype(np.float32) / 255.0).unsqueeze(0).unsqueeze(0)

        with torch.no_grad():
            logits = self.model(img_t)

        if torch.isnan(logits).any() or torch.isinf(logits).any():
            raise MalformedOutputError("model produced NaN/Inf logits -- refusing to convert to a Lattice")

        heatmap = torch.sigmoid(logits)[0, 0].numpy()

        fx, fy = w / MODEL_INPUT_SIZE, h / MODEL_INPUT_SIZE
        peaks_heatmap_space, confidences = detect_peaks(
            heatmap, threshold=CONFIDENCE_THRESHOLD, min_distance_px=MIN_PEAK_DISTANCE_HEATMAP_CELLS,
        )

        pixel_positions: list[tuple[float, float]] = []
        for (hy, hx) in peaks_heatmap_space:
            px = hx * OUTPUT_STRIDE * fx
            py = hy * OUTPUT_STRIDE * fy
            pixel_positions.append((float(px), float(py)))

        order = sorted(range(len(pixel_positions)), key=lambda i: (pixel_positions[i][1], pixel_positions[i][0]))
        pixel_positions = [pixel_positions[i] for i in order]

        if not pixel_positions or len(pixel_positions) < 3:
            # empty OR sparse (<3 points): collapse to fully empty, per
            # docs/ML_CONTRACT.md's recommended convention -- avoids the
            # documented trace_path IndexError blocker (see
            # PROJECT_STATE.md, M4.0/M4.1 sessions -- still not fixed
            # this session either, per this task's explicit rule 1).
            lattice = Lattice([], [], 0.0)
            assert_conforms(lattice)
            return lattice

        dot_radius = _estimate_dot_radius(pixel_positions)
        lattice_coords, _M, _t = _fit_lattice_coords(np.array(pixel_positions))
        lattice = Lattice(pixel_positions, lattice_coords, dot_radius)
        assert_conforms(lattice)
        return lattice


def _estimate_dot_radius(pixel_positions: list[tuple[float, float]]) -> float:
    if len(pixel_positions) < 2:
        return 5.0
    pts = np.array(pixel_positions)
    dists = []
    for i in range(len(pts)):
        d = np.sqrt(((pts - pts[i]) ** 2).sum(axis=1))
        d[i] = np.inf
        dists.append(d.min())
    return float(np.median(dists)) * 0.3
