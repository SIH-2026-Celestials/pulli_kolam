"""Tests for experiments/m6_generation/model.py: KolamSequenceGenerator's
forward pass shapes and autoregressive generate() loop."""

from __future__ import annotations

import torch

from experiments.m6_generation.model import KolamSequenceGenerator, ModelConfig
from experiments.m6_generation.representation import MAX_GRID, N_TRANSFORMS


def _small_model(vocab_size=20):
    torch.manual_seed(0)
    config = ModelConfig(vocab_size=vocab_size, d_model=32, n_layers=2, n_heads=4, dim_feedforward=64, max_seq_len=24)
    return KolamSequenceGenerator(config), config


def test_forward_output_shapes():
    model, config = _small_model()
    B, T = 4, 6
    grid_wh = torch.rand(B, 2) * 10
    symmetry_idx = torch.randint(0, 2, (B,))
    scalars = torch.rand(B, 2)
    motif_in = torch.randint(0, config.vocab_size, (B, T))
    x_in = torch.randint(0, MAX_GRID, (B, T))
    y_in = torch.randint(0, MAX_GRID, (B, T))
    t_in = torch.randint(0, N_TRANSFORMS, (B, T))

    out = model(grid_wh, symmetry_idx, scalars, motif_in, x_in, y_in, t_in)
    assert out["motif_logits"].shape == (B, T + 1, config.vocab_size)
    assert out["x_logits"].shape == (B, T + 1, MAX_GRID)
    assert out["y_logits"].shape == (B, T + 1, MAX_GRID)
    assert out["transform_logits"].shape == (B, T + 1, N_TRANSFORMS)


def test_generate_respects_max_len():
    model, config = _small_model()
    grid_wh = torch.tensor([[7.0, 7.0]])
    symmetry_idx = torch.tensor([0])
    scalars = torch.tensor([[0.5, 0.5]])
    tokens = model.generate(grid_wh, symmetry_idx, scalars, max_len=10)
    assert len(tokens) <= 10
    for motif_id, x, y, t in tokens:
        assert 0 <= x < MAX_GRID
        assert 0 <= y < MAX_GRID
        assert 0 <= t < N_TRANSFORMS


def test_generate_deterministic_given_same_torch_generator_seed():
    model, config = _small_model()
    grid_wh = torch.tensor([[7.0, 7.0]])
    symmetry_idx = torch.tensor([0])
    scalars = torch.tensor([[0.5, 0.5]])

    gen1 = torch.Generator().manual_seed(123)
    gen2 = torch.Generator().manual_seed(123)
    t1 = model.generate(grid_wh, symmetry_idx, scalars, max_len=10, generator=gen1)
    t2 = model.generate(grid_wh, symmetry_idx, scalars, max_len=10, generator=gen2)
    assert t1 == t2


def test_n_parameters_positive_and_reasonable():
    model, _ = _small_model()
    n = model.n_parameters()
    assert 0 < n < 10_000_000  # "compact" -- sanity ceiling, not a huge diffusion model
