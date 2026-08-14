"""M5: a learned placement scorer for structural kolam generation.

WHY THIS EXISTS: engine.novel_generation.select_novel_placements makes
every accept/reject decision with a fixed, hand-tuned linear combination
of growth/parity/connectivity terms (_novel_score + _connectivity_score +
_parity_score), in a single irreversible forward pass over a fixed
candidate order. Measured result (docs/M4_2_GENERATION.md,
experiments/m4_2_generation/results/*.json): 0/120 to 1/120 valid
candidates. The fixed weights were hand-guessed, not fit to any signal
about what actually distinguishes a placement that belongs in a real
valid kolam from one that doesn't.

This module replaces the *scoring function only* -- not the surrounding
search discipline -- with a small MLP trained by imitation learning
against real valid kolam patterns (kolam19/kolam29). Everything else
(candidate enumeration order, multiplicity cap, connectivity/parity
bookkeeping) is reused unmodified from engine.novel_generation; see
engine/learned_generation.py for the search loop that uses this scorer.

FEATURES ARE STRUCTURAL ONLY, NEVER GROUND-TRUTH: every feature computed
here is something a real generation call (no source pattern at all) can
compute from its own in-progress candidate graph. The oracle label used
at TRAINING time (is this placement consistent with a real pattern's
actual edges) never leaks into the feature vector itself -- see
experiments/m5_generation/build_training_data.py for how labels are
derived.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn

FEATURE_NAMES = [
    "motif_len",
    "n_touched",
    "n_new_dots",
    "n_existing_dots",
    "local_parity_net",
    "conn_n_merge_real",
    "conn_n_extend",
    "conn_n_new_isolated_pair",
    "conn_same_component_edges",
    "parity_odd_before",
    "parity_odd_after",
    "parity_delta_odd",
    "contribution_strands",
    "any_real_structure_exists",
    "progress_frac",
    "global_odd_frac",
]
N_FEATURES = len(FEATURE_NAMES)

DEFAULT_CHECKPOINT = (
    Path(__file__).resolve().parent.parent
    / "experiments"
    / "m5_generation"
    / "checkpoints"
    / "placement_scorer.pt"
)


class PlacementScorer(nn.Module):
    """Small MLP: structural features of one candidate placement -> logit
    of "does this placement belong in a valid reconstruction." Deliberately
    tiny (no GNN, no attention) -- the input is already a fixed-size,
    hand-engineered feature vector per candidate, not a graph, so a plain
    MLP is the simplest architecture that fits the actual input shape."""

    def __init__(self, n_features: int = N_FEATURES, hidden: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Linear(hidden // 2, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)

    def n_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())


def extract_features(
    motif_len: int,
    contribution: Counter,
    degree_before: Counter,
    connectivity_effect: dict | None,
    parity_effect: dict,
    any_real_structure_exists: bool,
    progress_frac: float,
    global_odd_frac: float,
) -> np.ndarray:
    """Build one candidate's feature vector. `contribution` is the Counter
    of {frozenset(edge): strand_count} the candidate would add (see
    engine.novel_generation._stamp_contribution); `degree_before` is the
    CURRENT accumulated degree Counter (state BEFORE this candidate);
    `connectivity_effect`/`parity_effect` are the dicts
    engine.novel_generation._connectivity_effect/_parity_effect already
    compute -- reused as-is, not recomputed with different semantics.
    `connectivity_effect` may be None (union-find not tracked) -- treated
    as an all-zero effect."""
    touched: set = set()
    for edge in contribution:
        a, b = tuple(edge)
        touched.add(a)
        touched.add(b)

    n_new = n_existing = 0
    local_parity_net = 0
    for node in touched:
        deg_before = degree_before.get(node, 0)
        if deg_before == 0:
            n_new += 1
            continue
        n_existing += 1
        deg_change = sum(count for edge, count in contribution.items() if node in edge)
        before_odd = deg_before % 2 == 1
        after_odd = (deg_before + deg_change) % 2 == 1
        if before_odd and not after_odd:
            local_parity_net += 1
        elif not before_odd and after_odd:
            local_parity_net -= 1

    ce = connectivity_effect or {
        "n_merge_real": 0,
        "n_extend": 0,
        "n_new_isolated_pair": 0,
        "same_component_edges": 0,
    }

    return np.array(
        [
            motif_len,
            len(touched),
            n_new,
            n_existing,
            local_parity_net,
            ce["n_merge_real"],
            ce["n_extend"],
            ce["n_new_isolated_pair"],
            ce["same_component_edges"],
            parity_effect["odd_before"],
            parity_effect["odd_after"],
            parity_effect["delta_odd"],
            sum(contribution.values()),
            float(any_real_structure_exists),
            progress_frac,
            global_odd_frac,
        ],
        dtype=np.float32,
    )


def _extract_numpy_weights(model: PlacementScorer) -> list[tuple[np.ndarray, np.ndarray]]:
    """Pull out (W, b) pairs for each nn.Linear layer as plain numpy
    arrays. Used to build a pure-numpy forward pass -- see ScorerBundle.score's
    docstring for why: the guided search calls this hundreds of thousands
    of times per candidate generation, and per-call torch tensor
    construction/dispatch overhead (not FLOPs -- this network is tiny)
    dominates runtime at that call volume."""
    weights = []
    for layer in model.net:
        if isinstance(layer, nn.Linear):
            W = layer.weight.detach().numpy()  # (out, in)
            b = layer.bias.detach().numpy()
            weights.append((W, b))
    return weights


@dataclass
class ScorerBundle:
    model: PlacementScorer
    feature_mean: np.ndarray
    feature_std: np.ndarray
    metadata: dict
    _np_weights: list = None

    def __post_init__(self):
        if self._np_weights is None:
            self._np_weights = _extract_numpy_weights(self.model)

    def score(self, features: np.ndarray) -> float:
        """Sigmoid probability in [0, 1] that this placement belongs in a
        valid reconstruction, per the imitation-learned scorer.

        PURE NUMPY, not a torch forward pass: engine.learned_generation's
        guided search calls this once per candidate placement examined
        (tens of thousands per restart) -- profiling showed torch's
        per-call dispatch overhead, not the ~1k-parameter matmuls
        themselves, was the dominant cost at that call volume (a single
        generation taking >100s). The weights are extracted once (see
        _extract_numpy_weights) and this reproduces the exact same
        Linear->ReLU->Linear->ReLU->Linear->sigmoid computation
        PlacementScorer.forward performs, verified equivalent by
        tests/test_learned_scoring.py."""
        x = (features - self.feature_mean) / self.feature_std
        for i, (W, b) in enumerate(self._np_weights):
            x = x @ W.T + b
            if i < len(self._np_weights) - 1:
                x = np.maximum(x, 0.0)  # ReLU
        logit = x[0]
        return 1.0 / (1.0 + np.exp(-logit))

    def score_batch(self, features: np.ndarray) -> np.ndarray:
        x = (features - self.feature_mean) / self.feature_std
        with torch.no_grad():
            logits = self.model(torch.from_numpy(x).float())
        return torch.sigmoid(logits).numpy()


def save_checkpoint(
    model: PlacementScorer,
    feature_mean: np.ndarray,
    feature_std: np.ndarray,
    metadata: dict,
    path: Path = DEFAULT_CHECKPOINT,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "n_features": model.net[0].in_features,
            "hidden": model.net[0].out_features,
            "feature_mean": feature_mean,
            "feature_std": feature_std,
            "feature_names": FEATURE_NAMES,
            "metadata": metadata,
        },
        path,
    )


def load_scorer(path: Path = DEFAULT_CHECKPOINT) -> ScorerBundle:
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    model = PlacementScorer(n_features=ckpt["n_features"], hidden=ckpt["hidden"])
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    return ScorerBundle(
        model=model,
        feature_mean=ckpt["feature_mean"],
        feature_std=ckpt["feature_std"],
        metadata=ckpt.get("metadata", {}),
    )
