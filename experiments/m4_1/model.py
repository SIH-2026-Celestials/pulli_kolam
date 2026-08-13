"""M4.1 Phase 4: the smallest reasonable learned baseline for dot
detection ONLY -- no motif/symmetry/graph/stroke/classification
knowledge anywhere in this file. Solves exactly one problem: given an
image, produce a heatmap whose peaks are candidate dot centers.

Architecture (deliberately small, CPU-trainable in minutes):
  input: 1x1xHxW grayscale, resized to MODEL_INPUT_SIZE
  4 conv blocks (stride 2 each via maxpool) -> total downsample = 8x
  1x1 conv head -> single-channel heatmap logits at H/8 x W/8
  sigmoid -> probability map in [0, 1]

This is a stride-8 heatmap-regression detector (CenterNet-style, without
CenterNet's size/offset heads -- dots are the only target and are all
roughly the same size, so those extra heads aren't justified here).

Why PyTorch: already installed in this environment (2.11.0+cpu, verified
before writing any of this) -- not a new dependency being introduced.
See PROJECT_STATE.md M4.1 section for the explicit dependency note.
"""

from __future__ import annotations

import torch
import torch.nn as nn

MODEL_INPUT_SIZE = 256  # resize target; must be divisible by STRIDE
STRIDE = 8  # 3 maxpool(2) layers -> 2^3


class DotHeatmapNet(nn.Module):
    """~50K parameters. Solves dot detection only -- see module docstring."""

    def __init__(self, in_channels: int = 1, base_channels: int = 16):
        super().__init__()
        c = base_channels
        self.features = nn.Sequential(
            nn.Conv2d(in_channels, c, 3, padding=1), nn.BatchNorm2d(c), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # /2
            nn.Conv2d(c, c * 2, 3, padding=1), nn.BatchNorm2d(c * 2), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # /4
            nn.Conv2d(c * 2, c * 4, 3, padding=1), nn.BatchNorm2d(c * 4), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # /8
            nn.Conv2d(c * 4, c * 4, 3, padding=1), nn.BatchNorm2d(c * 4), nn.ReLU(inplace=True),
        )
        self.head = nn.Conv2d(c * 4, 1, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Returns heatmap LOGITS (no sigmoid) at H/8 x W/8 -- callers use
        BCEWithLogitsLoss for training or torch.sigmoid for inference."""
        return self.head(self.features(x))

    def n_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())


def make_gaussian_heatmap(dot_positions_model_space: list[tuple[float, float]],
                           heatmap_h: int, heatmap_w: int, sigma: float = 1.2) -> torch.Tensor:
    """Ground-truth training target: a Gaussian blob at each dot's
    STRIDE-DOWNSAMPLED position (i.e. already divided by STRIDE before
    calling this). Standard keypoint-heatmap-regression target
    construction -- sigma in heatmap-pixel units, not input-image units."""
    heatmap = torch.zeros((heatmap_h, heatmap_w), dtype=torch.float32)
    if not dot_positions_model_space:
        return heatmap
    yy, xx = torch.meshgrid(torch.arange(heatmap_h, dtype=torch.float32),
                             torch.arange(heatmap_w, dtype=torch.float32), indexing="ij")
    for (px, py) in dot_positions_model_space:
        g = torch.exp(-((xx - px) ** 2 + (yy - py) ** 2) / (2 * sigma * sigma))
        heatmap = torch.maximum(heatmap, g)
    return heatmap
