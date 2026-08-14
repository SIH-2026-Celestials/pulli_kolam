"""M4.1 gating experiment: an EXPERIMENTAL, opt-in wrapper around
LearnedLatticeDetectorV2 that adds a lattice-geometric-consistency gate
on top of its raw output, per the evidence and rationale in
experiments/m4_2/gating_experiment.py and
docs/M4_1_ML_COMPLETION_REPORT.md.

STATUS: experimental, NOT wired into api/main.py or api/detectors.py.
Production behavior is unchanged by this file's existence -- `detector=ml`
via the API still uses the ungated LearnedLatticeDetectorV2 exactly as
before. This class exists so the gate can be evaluated end-to-end
(image -> lattice -> trace_path -> graph) with real code, not just
aggregate statistics, and so a future session has a concrete, tested
starting point if the gate is adopted -- see the completion report's
"Next milestone" section for why this was not wired into the live API
this session.

CONTRACT: satisfies engine.ml_contract.MLLatticeDetector exactly like
LearnedLatticeDetectorV2 does -- same Preprocessed -> Lattice signature,
same collapse-to-empty convention for sparse/rejected detections (never
the documented asymmetric-shape blocker, see docs/ML_CONTRACT.md
Section 5). The gate's rejection path is IMPLEMENTED AS that same
convention (Lattice([], [], 0.0)) -- not a new failure mode, not a
silent repair, not a fabricated detection.
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from engine.image_io import Lattice, Preprocessed, _fit_lattice_coords  # noqa: E402
from engine.ml_contract import assert_conforms  # noqa: E402
from experiments.m4_2.ml_lattice_detector import (  # noqa: E402
    CHECKPOINT_PATH,
    MalformedOutputError,
    load_model,
)
from experiments.m4_2.model import MODEL_INPUT_SIZE, OUTPUT_STRIDE  # noqa: E402
from experiments.m4_1.peak_detect import detect_peaks  # noqa: E402

MODEL_VERSION = "m4.2-128-gated-v1"

# Selected from the empirical residual distribution measured in
# experiments/m4_2/gating_experiment.py (18 real no-dot photos + 4
# in-scope photos, threshold=0.6): the value that removes the most
# no-dot false positives (18/18 -> 10/18, a 44-point reduction) while
# 0/18 synthetic validation points were ever incorrectly rejected (see
# docs/M4_1_ML_COMPLETION_REPORT.md Section 10 for the full tradeoff
# table across residual thresholds 5-50px -- this is NOT the only
# defensible choice, it is the one that maximizes no-dot FP reduction
# without any measured synthetic cost).
DEFAULT_LATTICE_RESIDUAL_THRESHOLD_PX = 10.0
DEFAULT_CONFIDENCE_THRESHOLD = 0.6  # unchanged from M4.2's own validation-selected value
DEFAULT_MIN_PEAK_DISTANCE_HEATMAP_CELLS = 2.0  # unchanged from M4.2's own validation-selected value


def _lattice_residual_px(pixel_positions: np.ndarray) -> "float | None":
    """None if too few points to fit (< 3). Otherwise the mean L2 pixel
    distance between an affine-lattice fit's PREDICTED positions and the
    actual detected positions -- see gating_experiment.py's identical
    function, duplicated here (not imported) only to keep this small
    production-shaped module free of a dependency on the experiment
    script."""
    if len(pixel_positions) < 3:
        return None
    coords, M, t = _fit_lattice_coords(pixel_positions)
    pred = (M @ np.array(coords).T).T + t
    return float(np.sqrt(((pred - pixel_positions) ** 2).sum(axis=1)).mean())


class GatedLearnedLatticeDetectorV2:
    """Callable object satisfying engine.ml_contract.MLLatticeDetector.
    Runs the same forward pass as LearnedLatticeDetectorV2, then adds ONE
    additional check: does the raw detection set fit a plausible affine
    lattice? If not (residual > lattice_residual_threshold_px, or too few
    points), the ENTIRE detection collapses to empty -- matching the
    project's existing "collapse sparse/malformed detections to empty"
    convention, never a partial repair."""

    def __init__(
        self,
        checkpoint_path: str = CHECKPOINT_PATH,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        min_peak_distance_heatmap_cells: float = DEFAULT_MIN_PEAK_DISTANCE_HEATMAP_CELLS,
        lattice_residual_threshold_px: float = DEFAULT_LATTICE_RESIDUAL_THRESHOLD_PX,
    ):
        self.model = load_model(checkpoint_path)
        self.model_version = MODEL_VERSION
        self.confidence_threshold = confidence_threshold
        self.min_peak_distance_heatmap_cells = min_peak_distance_heatmap_cells
        self.lattice_residual_threshold_px = lattice_residual_threshold_px

    def __call__(self, preprocessed: Preprocessed) -> Lattice:
        import cv2
        import torch

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
        peaks_heatmap_space, _confidences = detect_peaks(
            heatmap, threshold=self.confidence_threshold, min_distance_px=self.min_peak_distance_heatmap_cells
        )
        pixel_positions = np.array(
            [(hx * OUTPUT_STRIDE * fx, hy * OUTPUT_STRIDE * fy) for (hy, hx) in peaks_heatmap_space]
        ).reshape(-1, 2)

        # The lattice-consistency gate: reject the WHOLE detection set
        # (not individual points) if it doesn't fit a plausible regular
        # grid. This happens BEFORE the existing sparse-collapse check
        # below, so a gate-rejected image and a genuinely-sparse image
        # both end up at the same, already-safe empty convention.
        residual = _lattice_residual_px(pixel_positions)
        if residual is None or residual > self.lattice_residual_threshold_px:
            lattice = Lattice([], [], 0.0)
            assert_conforms(lattice)
            return lattice

        pixel_positions_list = [(float(x), float(y)) for x, y in pixel_positions]
        order = sorted(range(len(pixel_positions_list)), key=lambda i: (pixel_positions_list[i][1], pixel_positions_list[i][0]))
        pixel_positions_list = [pixel_positions_list[i] for i in order]

        if len(pixel_positions_list) < 3:
            lattice = Lattice([], [], 0.0)
            assert_conforms(lattice)
            return lattice

        dot_radius = _estimate_dot_radius(pixel_positions_list)
        lattice_coords, _M, _t = _fit_lattice_coords(np.array(pixel_positions_list))
        lattice = Lattice(pixel_positions_list, lattice_coords, dot_radius)
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
