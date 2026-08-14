"""Tests for engine/learned_scoring.py (M5): the imitation-trained
placement scorer and its numpy fast-path forward pass."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from engine.learned_scoring import (
    N_FEATURES,
    PlacementScorer,
    ScorerBundle,
    load_scorer,
    save_checkpoint,
)

CHECKPOINT = Path(__file__).resolve().parent.parent / "experiments" / "m5_generation" / "checkpoints" / "placement_scorer.pt"


def test_placement_scorer_forward_shape():
    model = PlacementScorer(n_features=N_FEATURES, hidden=32)
    x = torch.randn(5, N_FEATURES)
    out = model(x)
    assert out.shape == (5,)


def test_save_and_load_checkpoint_roundtrip(tmp_path):
    model = PlacementScorer(n_features=N_FEATURES, hidden=16)
    mean = np.zeros(N_FEATURES, dtype=np.float32)
    std = np.ones(N_FEATURES, dtype=np.float32)
    path = tmp_path / "scorer.pt"
    save_checkpoint(model, mean, std, {"note": "test"}, path=path)

    bundle = load_scorer(path)
    assert isinstance(bundle, ScorerBundle)
    assert bundle.metadata["note"] == "test"
    assert bundle.feature_mean.shape == (N_FEATURES,)


def test_numpy_score_matches_torch_forward(tmp_path):
    torch.manual_seed(0)
    model = PlacementScorer(n_features=N_FEATURES, hidden=32)
    mean = np.random.randn(N_FEATURES).astype(np.float32) * 0.1
    std = np.abs(np.random.randn(N_FEATURES).astype(np.float32)) + 0.5
    path = tmp_path / "scorer.pt"
    save_checkpoint(model, mean, std, {}, path=path)
    bundle = load_scorer(path)

    features = np.random.randn(N_FEATURES).astype(np.float32)

    numpy_score = bundle.score(features)

    x = (features - mean) / std
    with torch.no_grad():
        logit = model(torch.from_numpy(x).float().unsqueeze(0))
    torch_score = torch.sigmoid(logit).item()

    assert numpy_score == pytest.approx(torch_score, abs=1e-5)


@pytest.mark.skipif(not CHECKPOINT.exists(), reason="trained checkpoint not present")
def test_real_checkpoint_loads_and_scores():
    bundle = load_scorer(CHECKPOINT)
    assert bundle.metadata["test_acc"] > bundle.metadata["trivial_baseline_acc"]
    features = np.zeros(N_FEATURES, dtype=np.float32)
    score = bundle.score(features)
    assert 0.0 <= score <= 1.0
