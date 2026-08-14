"""M4.2 Phase B: a native 128x128-output detector, replacing M4.1's
32x32 DotHeatmapNet (experiments/m4_1/model.py) -- NOT by upsampling its
output, but by giving the network an actual decoder path with skip
connections (a small U-Net), per the M4.1.2 target-resolution finding
(experiments/m4_1/diagnostics/TARGET_RESOLUTION_REPORT.md) that 128x128
is the minimum resolution at which this dataset's real dot density
(180-500+ dots/image) becomes individually separable under a Gaussian-
blob target.

Solves dot detection ONLY -- same scope discipline as M4.1's model
(no motif/symmetry/graph/stroke/classification knowledge anywhere in
this file).

COORDINATE CONVENTION (must match experiments/m4_2/train.py and
experiments/m4_2/ml_lattice_detector.py exactly):
  - Input: 1-channel (grayscale/binary mask), resized to
    MODEL_INPUT_SIZE x MODEL_INPUT_SIZE.
  - Output: 1-channel heatmap LOGITS at HEATMAP_SIZE x HEATMAP_SIZE
    (== MODEL_INPUT_SIZE / OUTPUT_STRIDE), (row, col) = (y, x) array
    convention (numpy/torch default), matching M4.1's own convention
    exactly -- callers apply torch.sigmoid() for a probability map.
  - A point at ORIGINAL image pixel (px, py) maps to heatmap cell
    (px / fx / OUTPUT_STRIDE, py / fy / OUTPUT_STRIDE), where
    fx = original_width / MODEL_INPUT_SIZE, fy = original_height / MODEL_INPUT_SIZE
    -- the exact scaling convention M4.1 established, reused here with
    a different OUTPUT_STRIDE.

HEATMAP SEMANTICS: identical to M4.1's -- a Gaussian blob (sigma in
heatmap-CELL units, see make_gaussian_heatmap) placed at each true dot's
heatmap-space position, blobs combined via max() (not sum), so a dot's
own peak is never diluted by a nearby dot's blob.

GAUSSIAN RADIUS (sigma): SIGMA_CELLS below, a plain module constant --
deliberately configurable (per the M4.2 task's explicit instruction),
not hardcoded inline in the target-construction function. Default value
justified in TARGET_RESOLUTION_REPORT.md, not an arbitrary new guess:
that experiment measured full (100%) local-maxima recoverability at
128x128 with sigma=1.2 cells for every density tested (180-500 dots),
so 1.2 is kept as 128x128's default -- moving to a smaller sigma was
identified as optional extra margin for the densest patterns, not a
requirement, so is not forced here.

PEAK SEMANTICS: a "peak" is whatever experiments/m4_1/peak_detect.py's
detect_peaks() returns for a given (threshold, min_distance) -- reused
unmodified, see experiments/m4_2/ml_lattice_detector.py.
"""

from __future__ import annotations

import torch
import torch.nn as nn

MODEL_INPUT_SIZE = 256
OUTPUT_STRIDE = 2  # 256 / 2 = 128 -- native 128x128 output, NOT upsampled from a coarser map
HEATMAP_SIZE = MODEL_INPUT_SIZE // OUTPUT_STRIDE  # 128
SIGMA_CELLS = 1.2  # see module docstring "GAUSSIAN RADIUS" -- configurable, not hardcoded inline


def _conv_block(in_ch: int, out_ch: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(in_ch, out_ch, 3, padding=1), nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
        nn.Conv2d(out_ch, out_ch, 3, padding=1), nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
    )


class DotHeatmapNetV2(nn.Module):
    """Small U-Net: encoder (256->128->64->32, channels 16->32->64->96),
    decoder (32->64->128, with skip connections from the matching
    encoder stage) producing a NATIVE 128x128 single-channel heatmap.

    ~440K parameters -- still small/CPU-trainable (verified in Phase D),
    but with an actual decoder path, unlike M4.1's encoder-only model,
    which is precisely the missing capability M4.1.2 identified as
    necessary."""

    def __init__(self, in_channels: int = 1):
        super().__init__()
        # encoder
        self.enc1 = _conv_block(in_channels, 16)   # 256x256
        self.pool1 = nn.MaxPool2d(2)                # -> 128x128
        self.enc2 = _conv_block(16, 32)             # 128x128
        self.pool2 = nn.MaxPool2d(2)                # -> 64x64
        self.enc3 = _conv_block(32, 64)             # 64x64
        self.pool3 = nn.MaxPool2d(2)                # -> 32x32
        self.bottleneck = _conv_block(64, 96)       # 32x32

        # decoder -- only up to 128x128 (OUTPUT_STRIDE=2), not all the
        # way back to 256x256, since the target resolution is 128x128
        self.up1 = nn.ConvTranspose2d(96, 64, kernel_size=2, stride=2)   # 32 -> 64
        self.dec1 = _conv_block(64 + 64, 64)         # concat skip from enc3 (64ch @ 64x64)
        self.up2 = nn.ConvTranspose2d(64, 32, kernel_size=2, stride=2)   # 64 -> 128
        self.dec2 = _conv_block(32 + 32, 32)         # concat skip from enc2 (32ch @ 128x128)

        self.head = nn.Conv2d(32, 1, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Returns heatmap LOGITS at HEATMAP_SIZE x HEATMAP_SIZE (128x128
        for the default MODEL_INPUT_SIZE/OUTPUT_STRIDE). No sigmoid
        applied here -- callers use BCEWithLogitsLoss for training or
        torch.sigmoid() for inference, same convention as M4.1."""
        e1 = self.enc1(x)          # 16 @ 256
        e2 = self.enc2(self.pool1(e1))   # 32 @ 128
        e3 = self.enc3(self.pool2(e2))   # 64 @ 64
        b = self.bottleneck(self.pool3(e3))  # 96 @ 32

        d1 = self.up1(b)                       # 64 @ 64
        d1 = self.dec1(torch.cat([d1, e3], dim=1))  # 64 @ 64
        d2 = self.up2(d1)                      # 32 @ 128
        d2 = self.dec2(torch.cat([d2, e2], dim=1))  # 32 @ 128

        return self.head(d2)  # 1 @ 128

    def n_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())


def make_gaussian_heatmap(dot_positions_heatmap_space: list[tuple[float, float]],
                           heatmap_h: int, heatmap_w: int, sigma: float = SIGMA_CELLS) -> torch.Tensor:
    """Identical construction to experiments/m4_1/model.py's function of
    the same name (max-combination Gaussian blobs), generalized to this
    module's own default sigma/resolution. Not imported from model.py
    m4_1 to keep experiments/m4_2/ self-contained and independently
    versioned, per this being a NEW model version, not a patch to the
    old one."""
    heatmap = torch.zeros((heatmap_h, heatmap_w), dtype=torch.float32)
    if not dot_positions_heatmap_space:
        return heatmap
    yy, xx = torch.meshgrid(torch.arange(heatmap_h, dtype=torch.float32),
                             torch.arange(heatmap_w, dtype=torch.float32), indexing="ij")
    for (px, py) in dot_positions_heatmap_space:
        g = torch.exp(-((xx - px) ** 2 + (yy - py) ** 2) / (2 * sigma * sigma))
        heatmap = torch.maximum(heatmap, g)
    return heatmap
