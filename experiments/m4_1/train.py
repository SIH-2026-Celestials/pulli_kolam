"""M4.1 Phase 4: train DotHeatmapNet on experiments/m4_1/data/train,
validate on experiments/m4_1/data/val. Dot detection only -- see
model.py's docstring.

Deterministic: fixed torch seed. CPU-only (no CUDA on this machine,
verified in Phase 0) -- keeps the model and image size small enough that
this finishes in a few minutes, not hours.
"""

from __future__ import annotations

import json
import os
import sys

import cv2
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from experiments.m4_1.model import DotHeatmapNet, MODEL_INPUT_SIZE, STRIDE, make_gaussian_heatmap  # noqa: E402
from engine import image_io  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "results", "dot_heatmap_net.pt")
TRAIN_LOG_PATH = os.path.join(os.path.dirname(__file__), "results", "training_log.json")

SEED = 42
HEATMAP_SIZE = MODEL_INPUT_SIZE // STRIDE


class DotHeatmapDataset(Dataset):
    """Loads an M4.1 synthetic split and builds (model input, heatmap
    target) pairs.

    CRITICAL: the model's input is `engine.image_io.preprocess(path).binary`
    -- the SAME Otsu-binarized, deskewed mask the frozen ML contract
    (docs/ML_CONTRACT.md) says the detector receives -- NOT the raw
    rendered/degraded grayscale image. Training on anything else would be
    a train/inference distribution mismatch: at inference time (Phase 5's
    adapter), the model only ever sees `preprocessed.binary`, exactly the
    same as engine.image_io.detect_lattice does. Ground-truth dot pixel
    positions are rotated through the SAME deskew transform preprocess()
    applies, using the identical convention already established in
    tests/test_image_io.py's `_deskewed_gt_pixels` /
    experiments/m4_1/classical_baseline.py's `_deskewed_gt_pixels` --
    not a new one invented here.

    This also means the model's task is honestly harder (and possibly
    bottlenecked) in exactly the way the real deployment is: whatever
    binarization already destroys before the model sees the image, no
    amount of learning downstream can recover. That is itself a finding
    this experiment can surface, not a bug to hide."""

    def __init__(self, split_dir: str):
        self.samples = []  # (binary_resized_float_tensor, heatmap_tensor)
        json_paths = sorted(__import__("glob").glob(os.path.join(split_dir, "*.json")))
        for json_path in json_paths:
            with open(json_path) as f:
                gt = json.load(f)

            preprocessed = image_io.preprocess(gt["image_path"])
            binary = preprocessed.binary  # uint8, 255=ink/0=background
            h, w = binary.shape

            img = cv2.imread(gt["image_path"])
            M = cv2.getRotationMatrix2D((w / 2, h / 2), preprocessed.rotation_deg, 1.0)
            gt_px = np.array(list(gt["dot_pixel_positions"].values()), dtype=np.float32)
            deskewed_gt_px = cv2.transform(gt_px.reshape(-1, 1, 2), M).reshape(-1, 2)

            resized = cv2.resize(binary, (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE), interpolation=cv2.INTER_AREA)
            img_t = torch.from_numpy(resized.astype(np.float32) / 255.0).unsqueeze(0)

            fx, fy = MODEL_INPUT_SIZE / w, MODEL_INPUT_SIZE / h
            dot_positions_heatmap_space = [
                (px * fx / STRIDE, py * fy / STRIDE) for (px, py) in deskewed_gt_px
            ]
            heatmap = make_gaussian_heatmap(dot_positions_heatmap_space, HEATMAP_SIZE, HEATMAP_SIZE)
            self.samples.append((img_t, heatmap.unsqueeze(0)))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return self.samples[idx]


def run_epoch(model, loader, optimizer, loss_fn, train: bool) -> float:
    model.train(train)
    total_loss = 0.0
    n = 0
    for img, target in loader:
        if train:
            optimizer.zero_grad()
        logits = model(img)
        loss = loss_fn(logits, target)
        if train:
            loss.backward()
            optimizer.step()
        total_loss += loss.item() * img.shape[0]
        n += img.shape[0]
    return total_loss / n


def main(n_epochs: int = 40, lr: float = 1e-3, batch_size: int = 8):
    torch.manual_seed(SEED)

    train_ds = DotHeatmapDataset(os.path.join(DATA_DIR, "train"))
    val_ds = DotHeatmapDataset(os.path.join(DATA_DIR, "val"))
    print(f"train images: {len(train_ds)}, val images: {len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    model = DotHeatmapNet()
    print(f"model parameters: {model.n_parameters()}")

    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.BCEWithLogitsLoss()

    best_val_loss = float("inf")
    history = []
    for epoch in range(n_epochs):
        train_loss = run_epoch(model, train_loader, optimizer, loss_fn, train=True)
        with torch.no_grad():
            val_loss = run_epoch(model, val_loader, optimizer, loss_fn, train=False)
        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss})
        print(f"epoch {epoch:3d}  train_loss={train_loss:.4f}  val_loss={val_loss:.4f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
            torch.save(model.state_dict(), CHECKPOINT_PATH)

    with open(TRAIN_LOG_PATH, "w") as f:
        json.dump({
            "n_epochs": n_epochs, "lr": lr, "batch_size": batch_size, "seed": SEED,
            "model_parameters": model.n_parameters(),
            "best_val_loss": best_val_loss,
            "history": history,
        }, f, indent=2)

    print(f"\nBest val_loss: {best_val_loss:.4f}")
    print(f"Checkpoint: {CHECKPOINT_PATH}")
    print(f"Training log: {TRAIN_LOG_PATH}")


if __name__ == "__main__":
    main()
