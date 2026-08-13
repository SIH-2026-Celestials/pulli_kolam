"""M4.1 Phase 5: the contract adapter. Converts DotHeatmapNet's raw
output into the FROZEN engine.ml_contract.MLLatticeDetector contract
(Preprocessed -> Lattice), exactly the same output type
engine.image_io.detect_lattice produces -- see docs/ML_CONTRACT.md.

This file does NOT modify engine/image_io.py, engine/ml_contract.py, or
any downstream consumer. It is a new, separate implementation of the
same `Preprocessed -> Lattice` contract detect_lattice already
satisfies -- the model adapts to the contract, not the other way
around (M4.1 task's explicit rule).

Handles, per the contract spec (docs/ML_CONTRACT.md Section 4/5):
  - confidence threshold          (CONFIDENCE_THRESHOLD)
  - candidate peaks / duplicates  (non-max suppression, MIN_PEAK_DISTANCE_PX)
  - coordinate normalization      (rescale heatmap-space -> preprocessed.binary pixel space)
  - deterministic ordering        (sorted by (y, x), same rule stated below)
  - empty detection               (Lattice([], [], 0.0), matching detect_lattice's own convention)
  - sparse detection               (see NOTE on the known trace_path blocker below)
  - malformed output              (checkpoint/model errors raise, not silently repaired)

Does NOT silently repair invalid model output: if the checkpoint is
missing or the model produces NaNs, this raises rather than returning a
Lattice that looks valid but isn't (see `load_model`, `MalformedOutputError`).
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
from experiments.m4_1.model import DotHeatmapNet, MODEL_INPUT_SIZE, STRIDE  # noqa: E402
from experiments.m4_1.peak_detect import detect_peaks  # noqa: E402

CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "results", "dot_heatmap_net.pt")

# Confidence threshold on the sigmoid heatmap -- a candidate peak below
# this is not reported at all (not the same thing as "low confidence but
# still returned": the frozen contract has no confidence field, so a
# below-threshold candidate simply isn't a detection -- see
# docs/ML_CONTRACT.md Section 4 "this contract has no confidence field").
CONFIDENCE_THRESHOLD = 0.4

# NMS suppression radius, in HEATMAP-CELL units (not original-image
# pixels -- see bug note below). Must be set relative to the Gaussian
# training target's own footprint (model.py's make_gaussian_heatmap,
# sigma=1.2 heatmap-cells), not to the original image's pixel scale,
# because a single dot's heatmap "blob" spans multiple adjacent cells
# regardless of how large the original image is.
#
# BUG FOUND AND FIXED during Phase 5/6 testing (see PROJECT_STATE.md):
# the first version derived this from a FIXED original-pixel constant
# (STRIDE * 1.5 = 12px) converted into heatmap-space via
# `MIN_PEAK_DISTANCE_PX / STRIDE / avg_resize_factor` -- for a 400x400
# test image that worked out to ~0.96 heatmap cells, far smaller than a
# sigma=1.2 blob's ~1.9-cell effective radius, so NMS failed to collapse
# a single dot's blob (~9-13 raw cells above threshold) into one peak.
# 5 true dots produced 45 raw "detections" instead of 5. This also fed
# a large, partially-degenerate point cloud into
# engine.image_io._fit_lattice_coords, which is very likely what
# actually triggered the native crash documented below (not the OpenMP
# conflict per se -- see the investigation note in PROJECT_STATE.md
# distinguishing the two issues).
MIN_PEAK_DISTANCE_HEATMAP_CELLS = 2.5


class MalformedOutputError(RuntimeError):
    """Raised when the model's output cannot be trusted -- NaN/Inf
    logits, wrong output shape, or a missing/corrupt checkpoint. Per the
    M4.1 task's explicit rule, this adapter does NOT silently repair
    invalid output into something that merely looks like a valid
    Lattice."""


def load_model(checkpoint_path: str = CHECKPOINT_PATH) -> DotHeatmapNet:
    if not os.path.exists(checkpoint_path):
        raise MalformedOutputError(
            f"no trained checkpoint at {checkpoint_path} -- run experiments/m4_1/train.py first. "
            "Refusing to serve an untrained (random-weight) model as a detector."
        )
    model = DotHeatmapNet()
    state_dict = torch.load(checkpoint_path, map_location="cpu")
    model.load_state_dict(state_dict)
    model.eval()
    return model


class LearnedLatticeDetector:
    """Callable object satisfying engine.ml_contract.MLLatticeDetector:
    __call__(self, preprocessed: Preprocessed) -> Lattice.

    A callable OBJECT (not a bare function) because it needs to carry
    loaded model weights -- exactly the case
    engine/ml_contract.py's own docstring anticipates ("implementations
    that need to carry state... can't be a bare function")."""

    def __init__(self, checkpoint_path: str = CHECKPOINT_PATH):
        self.model = load_model(checkpoint_path)

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

        heatmap = torch.sigmoid(logits)[0, 0].numpy()  # H/8 x W/8, in [0, 1]

        # rescale factors: heatmap-space -> ORIGINAL preprocessed.binary
        # pixel space (heatmap cell -> input-model pixel via STRIDE, then
        # model-input pixel -> original pixel via the resize ratio)
        fx = w / MODEL_INPUT_SIZE
        fy = h / MODEL_INPUT_SIZE
        peaks_heatmap_space, confidences = detect_peaks(
            heatmap, threshold=CONFIDENCE_THRESHOLD,
            min_distance_px=MIN_PEAK_DISTANCE_HEATMAP_CELLS,
        )

        pixel_positions: list[tuple[float, float]] = []
        for (hy, hx) in peaks_heatmap_space:
            px = hx * STRIDE * fx
            py = hy * STRIDE * fy
            pixel_positions.append((float(px), float(py)))

        # Deterministic ordering: sort by (y, x) -- no ordering is
        # REQUIRED by the contract (docs/ML_CONTRACT.md Section 4), but a
        # stable, documented order makes this adapter's own output
        # reproducible/diffable across runs, which matters for testing.
        order = sorted(range(len(pixel_positions)), key=lambda i: (pixel_positions[i][1], pixel_positions[i][0]))
        pixel_positions = [pixel_positions[i] for i in order]

        if not pixel_positions:
            lattice = Lattice([], [], 0.0)
            assert_conforms(lattice)
            return lattice

        # Per docs/ML_CONTRACT.md Section 5's recommended convention: a
        # detector finding fewer than 3 points cannot fit a lattice
        # (matches detect_lattice's own >=3-point requirement) AND, per
        # this contract's stricter recommendation (to avoid the
        # documented trace_path IndexError blocker -- see
        # docs/ML_CONTRACT.md Section 5, PROJECT_STATE.md's M4.0 report),
        # collapses to FULLY empty rather than reproducing the asymmetric
        # 1-2-point shape. This is a deliberate, documented adapter
        # choice, not a silent repair of bad output -- the peaks ARE
        # real model output, we are choosing not to report them in a
        # shape known to crash a downstream function we are not allowed
        # to modify this session.
        if len(pixel_positions) < 3:
            lattice = Lattice([], [], 0.0)
            assert_conforms(lattice)
            return lattice

        dot_radius = _estimate_dot_radius(pixel_positions)

        # Fit integer lattice_coords via the SAME routine detect_lattice
        # itself uses (engine.image_io._fit_lattice_coords, imported not
        # reimplemented) -- required to avoid reproducing the exact
        # asymmetric-Lattice blocker (>=3 pixel_positions but 0
        # lattice_coords) that crashes trace_path. This is reuse of an
        # existing private helper, not a modification of image_io.py.
        lattice_coords, _M, _t = _fit_lattice_coords(np.array(pixel_positions))
        lattice = Lattice(pixel_positions, lattice_coords, dot_radius)
        assert_conforms(lattice)
        return lattice


def _estimate_dot_radius(pixel_positions: list[tuple[float, float]]) -> float:
    """A rough dot-radius estimate for trace_path's hub-capture-radius
    parameter, derived from median nearest-neighbor spacing (same
    general idea image_io._fit_lattice_coords uses for lattice spacing,
    reused conceptually here -- not by importing private internals)."""
    if len(pixel_positions) < 2:
        return 5.0
    pts = np.array(pixel_positions)
    dists = []
    for i in range(len(pts)):
        d = np.sqrt(((pts - pts[i]) ** 2).sum(axis=1))
        d[i] = np.inf
        dists.append(d.min())
    return float(np.median(dists)) * 0.3
