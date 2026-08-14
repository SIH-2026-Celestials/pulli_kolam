"""M6 Phase 4: train Generator V1 (experiments/m6_generation/model.py)
on the structural sequence dataset (build_dataset.py's output).

    python -m experiments.m6_generation.train

CPU-only training (per the task's explicit environment constraints):
torch.set_num_threads is set explicitly (not left at whatever default
the process inherits), leaving headroom for any other concurrently
running torch process (this session also runs M5's own benchmark,
which loads a much smaller model but still competes for the same CPU
threads) rather than claiming all 8.

Supports resume (--resume), checkpointing (best-val-loss checkpoint
kept separately from the latest), gradient clipping, and early stopping
on validation loss patience -- all the task's explicit training-loop
requirements.
"""

from __future__ import annotations

import argparse
import json
import time
from functools import partial
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader

from experiments.m6_generation.dataset import KolamSequenceDataset, collate_batch, load_vocab
from experiments.m6_generation.model import KolamSequenceGenerator, ModelConfig

RESULTS_DIR = Path(__file__).resolve().parent / "results"
CHECKPOINT_PATH = RESULTS_DIR / "generator_v1.pt"
BEST_CHECKPOINT_PATH = RESULTS_DIR / "generator_v1_best.pt"
LOG_PATH = RESULTS_DIR / "training_log.json"

DEFAULT_TORCH_THREADS = 4  # leaves headroom for other concurrent torch processes this session, see module docstring


def _compute_loss(out: dict, batch: dict, criterion) -> dict:
    """`out`'s logits have T+1 positions (index 0 = hidden state right
    after the prepended CONDITION token, predicting target[0]; index T
    = hidden state after the LAST input token, which has no
    corresponding target since targets are the inputs shifted left by
    one -- see dataset.py's collate_batch docstring). Slice off that
    unused final position before comparing against the T-length
    targets."""
    mask = batch["loss_mask"]
    T = mask.size(1)
    n = mask.sum().clamp(min=1)

    def masked_ce(logits, target):
        logits = logits[:, :T, :]
        loss_per_pos = criterion(logits.transpose(1, 2), target)  # (B, T)
        return (loss_per_pos * mask).sum() / n

    motif_loss = masked_ce(out["motif_logits"], batch["motif_tgt"])
    x_loss = masked_ce(out["x_logits"], batch["x_tgt"])
    y_loss = masked_ce(out["y_logits"], batch["y_tgt"])
    t_loss = masked_ce(out["transform_logits"], batch["transform_tgt"])
    total = motif_loss + x_loss + y_loss + t_loss
    return {"total": total, "motif": motif_loss, "x": x_loss, "y": y_loss, "transform": t_loss}


def _run_epoch(model, loader, criterion, optimizer, max_grad_norm, train: bool) -> dict:
    model.train(train)
    totals = {"total": 0.0, "motif": 0.0, "x": 0.0, "y": 0.0, "transform": 0.0}
    n_batches = 0
    with torch.set_grad_enabled(train):
        for batch in loader:
            out = model(
                batch["grid_wh"], batch["symmetry_idx"], batch["scalars"],
                batch["motif_in"], batch["x_in"], batch["y_in"], batch["transform_in"],
            )
            losses = _compute_loss(out, batch, criterion)
            if train:
                optimizer.zero_grad()
                losses["total"].backward()
                nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm)
                optimizer.step()
            for k in totals:
                totals[k] += losses[k].item()
            n_batches += 1
    return {k: v / max(n_batches, 1) for k, v in totals.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--patience", type=int, default=4)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--d-model", type=int, default=128)
    parser.add_argument("--n-layers", type=int, default=3)
    parser.add_argument("--n-heads", type=int, default=4)
    parser.add_argument("--max-seq-len", type=int, default=160)
    parser.add_argument("--torch-threads", type=int, default=DEFAULT_TORCH_THREADS)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--seed", type=int, default=6363)
    args = parser.parse_args()

    torch.set_num_threads(args.torch_threads)
    torch.manual_seed(args.seed)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    vocab = load_vocab()
    train_ds = KolamSequenceDataset("train")
    val_ds = KolamSequenceDataset("val")
    print(f"train examples: {len(train_ds)}, val examples: {len(val_ds)}, vocab size: {vocab.size}")

    collate = partial(collate_batch, max_len=args.max_seq_len - 1)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, collate_fn=collate)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, collate_fn=collate)

    config = ModelConfig(
        vocab_size=vocab.size, d_model=args.d_model, n_layers=args.n_layers,
        n_heads=args.n_heads, max_seq_len=args.max_seq_len,
    )
    model = KolamSequenceGenerator(config)
    n_params = model.n_parameters()
    print(f"model parameters: {n_params}")

    start_epoch = 0
    history = []
    best_val_loss = float("inf")
    patience_counter = 0

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    criterion = nn.CrossEntropyLoss(reduction="none")

    if args.resume and CHECKPOINT_PATH.exists():
        ckpt = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=False)
        model.load_state_dict(ckpt["model_state_dict"])
        optimizer.load_state_dict(ckpt["optimizer_state_dict"])
        start_epoch = ckpt["epoch"] + 1
        history = ckpt.get("history", [])
        best_val_loss = ckpt.get("best_val_loss", float("inf"))
        print(f"resumed from epoch {start_epoch}")

    t_start = time.time()
    for epoch in range(start_epoch, args.epochs):
        t0 = time.time()
        train_losses = _run_epoch(model, train_loader, criterion, optimizer, args.max_grad_norm, train=True)
        val_losses = _run_epoch(model, val_loader, criterion, optimizer, args.max_grad_norm, train=False)
        epoch_time = time.time() - t0

        record = {
            "epoch": epoch, "train_loss": train_losses, "val_loss": val_losses,
            "epoch_time_seconds": epoch_time,
        }
        history.append(record)
        print(f"epoch {epoch:3d}  train_total={train_losses['total']:.4f}  "
              f"val_total={val_losses['total']:.4f}  time={epoch_time:.1f}s", flush=True)

        torch.save({
            "model_state_dict": model.state_dict(), "optimizer_state_dict": optimizer.state_dict(),
            "epoch": epoch, "history": history, "best_val_loss": best_val_loss,
            "config": config.to_dict(), "vocab_size": vocab.size,
        }, CHECKPOINT_PATH)

        if val_losses["total"] < best_val_loss:
            best_val_loss = val_losses["total"]
            patience_counter = 0
            torch.save({
                "model_state_dict": model.state_dict(), "epoch": epoch,
                "val_loss": val_losses["total"], "config": config.to_dict(), "vocab_size": vocab.size,
                "n_parameters": n_params,
            }, BEST_CHECKPOINT_PATH)
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                print(f"early stopping at epoch {epoch} (no val improvement for {args.patience} epochs)")
                break

    total_time = time.time() - t_start
    log = {
        "n_train_examples": len(train_ds), "n_val_examples": len(val_ds), "vocab_size": vocab.size,
        "n_parameters": n_params, "config": config.to_dict(),
        "args": vars(args), "history": history, "best_val_loss": best_val_loss,
        "total_training_time_seconds": total_time, "checkpoint_path": str(BEST_CHECKPOINT_PATH),
    }
    LOG_PATH.write_text(json.dumps(log, indent=2))
    print(f"best_val_loss={best_val_loss:.4f}  total_time={total_time:.1f}s")
    print(f"wrote {LOG_PATH}")


if __name__ == "__main__":
    main()
