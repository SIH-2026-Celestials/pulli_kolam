"""M4.2 Phase D: train DotHeatmapNetV2 (native 128x128 output) on
experiments/m4_2/data/train, validate on val. Dot detection only.

Same critical distribution-matching discipline M4.1 established (and
initially got wrong before fixing, see PROJECT_STATE.md session 13):
trains on `engine.image_io.preprocess(path).binary` -- the SAME
Otsu-binarized, deskewed mask the frozen contract hands the detector at
inference -- not the raw photo.

Deterministic: fixed torch seed. CPU-only.
"""

from __future__ import annotations

import glob
import json
import os
import sys

import cv2
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from experiments.m4_2.model import DotHeatmapNetV2, MODEL_INPUT_SIZE, OUTPUT_STRIDE, HEATMAP_SIZE, make_gaussian_heatmap  # noqa: E402
from engine import image_io  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "results", "dot_heatmap_net_v2.pt")
TRAIN_LOG_PATH = os.path.join(os.path.dirname(__file__), "results", "training_log.json")

SEED = 42


class DotHeatmapDatasetV2(Dataset):
    """Same distribution-matching discipline as M4.1's DotHeatmapDataset
    (experiments/m4_1/train.py) -- trains on preprocessed.binary, not
    the raw image -- generalized to this model's own
    MODEL_INPUT_SIZE/OUTPUT_STRIDE."""

    def __init__(self, split_dir: str):
        self.samples = []
        json_paths = sorted(glob.glob(os.path.join(split_dir, "*.json")))
        for json_path in json_paths:
            with open(json_path) as f:
                gt = json.load(f)

            preprocessed = image_io.preprocess(gt["image_path"])
            binary = preprocessed.binary
            h, w = binary.shape

            img = cv2.imread(gt["image_path"])
            M = cv2.getRotationMatrix2D((w / 2, h / 2), preprocessed.rotation_deg, 1.0)
            gt_px = np.array(list(gt["dot_pixel_positions"].values()), dtype=np.float32)
            deskewed_gt_px = cv2.transform(gt_px.reshape(-1, 1, 2), M).reshape(-1, 2)

            resized = cv2.resize(binary, (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE), interpolation=cv2.INTER_AREA)
            img_t = torch.from_numpy(resized.astype(np.float32) / 255.0).unsqueeze(0)

            fx, fy = MODEL_INPUT_SIZE / w, MODEL_INPUT_SIZE / h
            dot_positions_heatmap_space = [
                (px * fx / OUTPUT_STRIDE, py * fy / OUTPUT_STRIDE) for (px, py) in deskewed_gt_px
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


def main(n_epochs: int = 30, lr: float = 1e-3, batch_size: int = 8):
    torch.manual_seed(SEED)

    print("Loading train set (running preprocess() on every image, may take a while)...")
    train_ds = DotHeatmapDatasetV2(os.path.join(DATA_DIR, "train"))
    print("Loading val set...")
    val_ds = DotHeatmapDatasetV2(os.path.join(DATA_DIR, "val"))
    print(f"train images: {len(train_ds)}, val images: {len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    model = DotHeatmapNetV2()
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
            "model_parameters": model.n_parameters(), "best_val_loss": best_val_loss,
            "n_train_images": len(train_ds), "n_val_images": len(val_ds),
            "history": history,
        }, f, indent=2)

    print(f"\nBest val_loss: {best_val_loss:.4f}")
    print(f"Checkpoint: {CHECKPOINT_PATH}")


if __name__ == "__main__":
    main()
