"""M6 Phase 4 (dataset side): load build_dataset.py's {split}.jsonl +
vocab.json into padded, tensorized batches for train.py.

Preprocessing (JSON parse, token-list construction) happens ONCE at
load time, cached as plain Python lists on the Dataset object -- not
repeated every epoch (the task's own explicit "avoid repeatedly running
expensive preprocessing on every epoch" instruction). Padding/collation
happens per-batch (cheap tensor ops only), via `collate_batch`.
"""

from __future__ import annotations

import json
from pathlib import Path

import torch
from torch.utils.data import Dataset

from experiments.m6_generation.representation import (
    EOS_MOTIF_ID,
    PAD_MOTIF_ID,
    MotifVocabulary,
    PlacementToken,
)

DATA_DIR = Path(__file__).resolve().parent / "data"


def load_vocab() -> MotifVocabulary:
    return MotifVocabulary.from_dict(json.loads((DATA_DIR / "vocab.json").read_text()))


class KolamSequenceDataset(Dataset):
    """One example = one (condition, token sequence) pair. `tokens`
    stored WITHOUT the EOS token appended -- EOS is added at collation
    time as the final TARGET (never a training INPUT, since generation
    always stops once EOS is predicted, so the model never needs to
    condition on having already seen an EOS)."""

    def __init__(self, split: str):
        path = DATA_DIR / f"{split}.jsonl"
        self.rows = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                self.rows.append(json.loads(line))

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int) -> dict:
        row = self.rows[idx]
        tokens = [PlacementToken.from_dict(t) for t in row["tokens"]]
        symmetry_idx = 1 if row["symmetry_bucket"] == "high_symmetry" else 0
        return {
            "grid_wh": (float(row["grid_width"]), float(row["grid_height"])),
            "symmetry_idx": symmetry_idx,
            "scalars": (float(row["complexity"]), float(row["density"])),
            "tokens": tokens,
        }


def collate_batch(batch: "list[dict]", max_len: int) -> dict:
    """Right-pad every sequence to the batch's own max length (capped at
    `max_len`, matching ModelConfig.max_seq_len - 1 for the condition
    token). INPUT sequence = [BOS-less real tokens] (teacher forcing:
    position i's input is token i, used to predict token i+1); TARGET
    sequence = real tokens shifted left by one, with EOS appended as the
    final target. PAD_MOTIF_ID/0 fill both past each example's real
    length; `loss_mask` marks which target positions are real (1) vs
    padding (0) so the loss never rewards predicting padding correctly."""
    B = len(batch)
    lengths = [min(len(b["tokens"]) + 1, max_len) for b in batch]  # +1 for EOS target
    T = max(lengths) if lengths else 1

    motif_in = torch.full((B, T), PAD_MOTIF_ID, dtype=torch.long)
    x_in = torch.zeros((B, T), dtype=torch.long)
    y_in = torch.zeros((B, T), dtype=torch.long)
    t_in = torch.zeros((B, T), dtype=torch.long)

    motif_tgt = torch.full((B, T), PAD_MOTIF_ID, dtype=torch.long)
    x_tgt = torch.zeros((B, T), dtype=torch.long)
    y_tgt = torch.zeros((B, T), dtype=torch.long)
    t_tgt = torch.zeros((B, T), dtype=torch.long)
    loss_mask = torch.zeros((B, T), dtype=torch.bool)

    grid_wh = torch.zeros((B, 2), dtype=torch.float32)
    symmetry_idx = torch.zeros((B,), dtype=torch.long)
    scalars = torch.zeros((B, 2), dtype=torch.float32)

    for i, ex in enumerate(batch):
        toks = ex["tokens"][: max_len - 1]
        grid_wh[i] = torch.tensor(ex["grid_wh"])
        symmetry_idx[i] = ex["symmetry_idx"]
        scalars[i] = torch.tensor(ex["scalars"])

        # INPUT: real tokens at positions 0..len(toks)-1 (position 0's
        # input embeds token[0] itself is WRONG for teacher forcing --
        # correct teacher forcing feeds token[t-1] as input to predict
        # token[t]; position 0 has no "previous real token" so it uses
        # the condition token's position instead (see model.py's
        # `generate` first-step handling) -- collation therefore SHIFTS:
        # input[0] is a PAD placeholder (mirrors generate()'s bootstrap
        # step), input[1:] = toks[0:-1], target[0:] = toks[0:] + [EOS].
        n = len(toks)
        if n > 0:
            motif_in[i, 1:n] = torch.tensor([t.motif_id for t in toks[:-1]], dtype=torch.long)
            x_in[i, 1:n] = torch.tensor([t.x for t in toks[:-1]], dtype=torch.long)
            y_in[i, 1:n] = torch.tensor([t.y for t in toks[:-1]], dtype=torch.long)
            t_in[i, 1:n] = torch.tensor([t.transform_id for t in toks[:-1]], dtype=torch.long)

            motif_tgt[i, :n] = torch.tensor([t.motif_id for t in toks], dtype=torch.long)
            x_tgt[i, :n] = torch.tensor([t.x for t in toks], dtype=torch.long)
            y_tgt[i, :n] = torch.tensor([t.y for t in toks], dtype=torch.long)
            t_tgt[i, :n] = torch.tensor([t.transform_id for t in toks], dtype=torch.long)
            loss_mask[i, :n] = True

        if n < T:
            motif_tgt[i, n] = EOS_MOTIF_ID
            loss_mask[i, n] = True

    return {
        "grid_wh": grid_wh, "symmetry_idx": symmetry_idx, "scalars": scalars,
        "motif_in": motif_in, "x_in": x_in, "y_in": y_in, "transform_in": t_in,
        "motif_tgt": motif_tgt, "x_tgt": x_tgt, "y_tgt": y_tgt, "transform_tgt": t_tgt,
        "loss_mask": loss_mask,
    }
