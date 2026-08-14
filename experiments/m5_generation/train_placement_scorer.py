"""M5: train engine.learned_scoring.PlacementScorer on the oracle-labeled
dataset built by build_training_data.py.

Binary classification (BCEWithLogitsLoss): does this candidate placement
belong in a valid reconstruction of the real pattern it was replayed
against? Reports real train/val/test accuracy, AUC-style separation, and
positive rates -- this script does not report success unless the
numbers are actually good; if val accuracy is near the trivial
always-negative baseline, that is what gets printed.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from engine.learned_scoring import N_FEATURES, PlacementScorer, save_checkpoint

DATA_DIR = Path(__file__).resolve().parent / "data"
CHECKPOINT_PATH = Path(__file__).resolve().parent / "checkpoints" / "placement_scorer.pt"
RESULTS_PATH = Path(__file__).resolve().parent / "results" / "train_report.json"

EPOCHS = 60
BATCH_SIZE = 256
LR = 1e-3
SEED = 5252


def _load(split: str) -> tuple[np.ndarray, np.ndarray]:
    d = np.load(DATA_DIR / f"{split}.npz")
    return d["X"].astype(np.float32), d["y"].astype(np.float32)


def _accuracy(logits: torch.Tensor, y: torch.Tensor) -> float:
    preds = (torch.sigmoid(logits) > 0.5).float()
    return (preds == y).float().mean().item()


def main() -> None:
    torch.manual_seed(SEED)

    X_train, y_train = _load("train")
    X_val, y_val = _load("val")
    X_test, y_test = _load("test")

    feature_mean = X_train.mean(axis=0)
    feature_std = X_train.std(axis=0)
    feature_std[feature_std < 1e-6] = 1.0

    def normalize(X):
        return (X - feature_mean) / feature_std

    Xt = torch.from_numpy(normalize(X_train)).float()
    yt = torch.from_numpy(y_train).float()
    Xv = torch.from_numpy(normalize(X_val)).float()
    yv = torch.from_numpy(y_val).float()
    Xte = torch.from_numpy(normalize(X_test)).float()
    yte = torch.from_numpy(y_test).float()

    model = PlacementScorer(n_features=N_FEATURES, hidden=32)
    n_params = model.n_parameters()
    print("model parameters:", n_params)

    # class-balanced loss weight: positives are the minority class throughout
    n_pos = yt.sum().item()
    n_neg = len(yt) - n_pos
    pos_weight = torch.tensor([n_neg / max(n_pos, 1.0)])
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)

    n = len(Xt)
    t0 = time.time()
    history = []
    for epoch in range(EPOCHS):
        model.train()
        perm = torch.randperm(n)
        total_loss = 0.0
        for i in range(0, n, BATCH_SIZE):
            idx = perm[i : i + BATCH_SIZE]
            xb, yb = Xt[idx], yt[idx]
            optimizer.zero_grad()
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(idx)
        train_loss = total_loss / n

        model.eval()
        with torch.no_grad():
            val_logits = model(Xv)
            val_acc = _accuracy(val_logits, yv)
            val_loss = criterion(val_logits, yv).item()
        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss, "val_acc": val_acc})
        if epoch % 10 == 0 or epoch == EPOCHS - 1:
            print(f"epoch {epoch:3d}  train_loss={train_loss:.4f}  val_loss={val_loss:.4f}  val_acc={val_acc:.4f}")

    train_time = time.time() - t0

    model.eval()
    with torch.no_grad():
        test_logits = model(Xte)
        test_acc = _accuracy(test_logits, yte)
        test_probs = torch.sigmoid(test_logits).numpy()

    # simple rank-based AUC (Mann-Whitney U), no sklearn dependency
    order = np.argsort(test_probs)
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, len(order) + 1)
    y_test_np = y_test
    n_pos_test = y_test_np.sum()
    n_neg_test = len(y_test_np) - n_pos_test
    if n_pos_test > 0 and n_neg_test > 0:
        auc = (ranks[y_test_np == 1].sum() - n_pos_test * (n_pos_test + 1) / 2) / (n_pos_test * n_neg_test)
    else:
        auc = None

    trivial_baseline_acc = max(y_test_np.mean(), 1 - y_test_np.mean())

    metadata = {
        "architecture": "MLP (16 -> 32 -> 16 -> 1)",
        "n_parameters": n_params,
        "n_train_examples": int(len(Xt)),
        "n_val_examples": int(len(Xv)),
        "n_test_examples": int(len(Xte)),
        "epochs": EPOCHS,
        "batch_size": BATCH_SIZE,
        "lr": LR,
        "train_time_seconds": round(train_time, 1),
        "final_val_acc": history[-1]["val_acc"],
        "test_acc": test_acc,
        "test_auc": auc,
        "trivial_baseline_acc": float(trivial_baseline_acc),
        "seed": SEED,
    }
    print(json.dumps(metadata, indent=2))

    save_checkpoint(model, feature_mean, feature_std, metadata, path=CHECKPOINT_PATH)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps({"metadata": metadata, "history": history}, indent=2))


if __name__ == "__main__":
    main()
