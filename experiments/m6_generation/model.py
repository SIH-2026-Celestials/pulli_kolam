"""M6 Phase 4: Generator V1 -- a compact, CPU-trainable causal
Transformer over PlacementToken sequences (experiments/m6_generation/representation.py).

NOT a huge diffusion model, not pixel generation -- per the task's own
explicit instruction, this predicts the SAME symbolic sequence
engine.motifs.induce_motif_set_adaptive already extracts from real
patterns (see ARCHITECTURE.md section 10), one placement token at a
time, autoregressively.

FACTORIZED TOKEN HEAD: each step's target is not one flat vocabulary id
but four independent, small classification heads sharing one hidden
state -- motif_id (vocab_size incl. reserved EOS/PAD/UNK), x
(MAX_GRID), y (MAX_GRID), transform_id (N_TRANSFORMS). A single flat
vocabulary over the Cartesian product of these would be
vocab_size*MAX_GRID*MAX_GRID*N_TRANSFORMS classes -- absurdly large and
mostly never observed; factorizing keeps every head's classification
problem small and keeps the embedding tables the dominant parameter
cost (bounded by vocab_size + 2*MAX_GRID + N_TRANSFORMS terms, not their
product).

CONDITIONING: one extra "condition token" is prepended to the sequence,
built by projecting (grid_width, grid_height, symmetry_bucket,
complexity, density) into d_model and used as position 0's input
embedding -- the causal Transformer then attends back to it at every
later step, the same mechanism a BOS/CLS conditioning token uses in
sequence-to-sequence literature. No new attention mechanism is
introduced.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import torch
from torch import nn

from experiments.m6_generation.representation import (
    EOS_MOTIF_ID,
    MAX_GRID,
    N_TRANSFORMS,
    PAD_MOTIF_ID,
)

SYMMETRY_BUCKETS = ["low_symmetry", "high_symmetry"]


@dataclass
class ModelConfig:
    vocab_size: int  # MotifVocabulary.size, includes 3 reserved ids
    d_model: int = 128
    n_layers: int = 3
    n_heads: int = 4
    dim_feedforward: int = 256
    dropout: float = 0.1
    max_seq_len: int = 256  # includes the prepended condition token

    def to_dict(self) -> dict:
        return {
            "vocab_size": self.vocab_size, "d_model": self.d_model, "n_layers": self.n_layers,
            "n_heads": self.n_heads, "dim_feedforward": self.dim_feedforward,
            "dropout": self.dropout, "max_seq_len": self.max_seq_len,
        }

    @staticmethod
    def from_dict(d: dict) -> "ModelConfig":
        return ModelConfig(**d)


class ConditionEncoder(nn.Module):
    """(grid_width, grid_height, symmetry_bucket, complexity, density) ->
    one d_model vector, used as the sequence's first ("condition") token."""

    def __init__(self, d_model: int):
        super().__init__()
        self.grid_proj = nn.Linear(2, d_model // 4)
        self.symmetry_embed = nn.Embedding(len(SYMMETRY_BUCKETS), d_model // 4)
        self.scalar_proj = nn.Linear(2, d_model // 2)  # complexity, density
        self.out_proj = nn.Linear(d_model // 4 + d_model // 4 + d_model // 2, d_model)

    def forward(self, grid_wh: torch.Tensor, symmetry_idx: torch.Tensor, scalars: torch.Tensor) -> torch.Tensor:
        g = self.grid_proj(grid_wh)
        s = self.symmetry_embed(symmetry_idx)
        c = self.scalar_proj(scalars)
        return self.out_proj(torch.cat([g, s, c], dim=-1))


class TokenEmbedding(nn.Module):
    """Sum of four small embeddings (motif/x/y/transform) -- see module
    docstring's factorization rationale."""

    def __init__(self, vocab_size: int, d_model: int):
        super().__init__()
        self.motif_embed = nn.Embedding(vocab_size, d_model)
        self.x_embed = nn.Embedding(MAX_GRID, d_model)
        self.y_embed = nn.Embedding(MAX_GRID, d_model)
        self.transform_embed = nn.Embedding(N_TRANSFORMS, d_model)

    def forward(self, motif_id: torch.Tensor, x: torch.Tensor, y: torch.Tensor, transform_id: torch.Tensor) -> torch.Tensor:
        return self.motif_embed(motif_id) + self.x_embed(x) + self.y_embed(y) + self.transform_embed(transform_id)


class PositionalEncoding(nn.Module):
    """Standard sinusoidal positional encoding -- no learned parameters,
    keeps the model's parameter count dominated by the embedding tables
    and attention layers, not position encoding."""

    def __init__(self, d_model: int, max_len: int):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, : x.size(1)]


class KolamSequenceGenerator(nn.Module):
    """Generator V1: causal Transformer decoder (encoder-only stack with
    a causal mask -- no cross-attention, no separate encoder; the
    condition token IS the only "context" this model needs, per the
    module docstring) predicting the next PlacementToken's 4 factorized
    fields at every position."""

    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        self.condition_encoder = ConditionEncoder(config.d_model)
        self.token_embedding = TokenEmbedding(config.vocab_size, config.d_model)
        self.pos_encoding = PositionalEncoding(config.d_model, config.max_seq_len)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.d_model, nhead=config.n_heads, dim_feedforward=config.dim_feedforward,
            dropout=config.dropout, batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=config.n_layers)
        self.norm = nn.LayerNorm(config.d_model)

        self.motif_head = nn.Linear(config.d_model, config.vocab_size)
        self.x_head = nn.Linear(config.d_model, MAX_GRID)
        self.y_head = nn.Linear(config.d_model, MAX_GRID)
        self.transform_head = nn.Linear(config.d_model, N_TRANSFORMS)

    def n_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def _causal_mask(self, seq_len: int, device) -> torch.Tensor:
        return torch.triu(torch.full((seq_len, seq_len), float("-inf"), device=device), diagonal=1)

    def forward(
        self,
        grid_wh: torch.Tensor,        # (B, 2) float
        symmetry_idx: torch.Tensor,    # (B,) long
        scalars: torch.Tensor,         # (B, 2) float -- complexity, density
        motif_id: torch.Tensor,        # (B, T) long -- INPUT tokens (teacher-forced, shifted right)
        x: torch.Tensor,               # (B, T) long
        y: torch.Tensor,               # (B, T) long
        transform_id: torch.Tensor,    # (B, T) long
        padding_mask: "torch.Tensor | None" = None,  # (B, T+1) bool, True = PAD (ignore)
    ) -> dict:
        cond = self.condition_encoder(grid_wh, symmetry_idx, scalars).unsqueeze(1)  # (B, 1, D)
        tok = self.token_embedding(motif_id, x, y, transform_id)  # (B, T, D)
        seq = torch.cat([cond, tok], dim=1)  # (B, T+1, D)
        seq = self.pos_encoding(seq)

        mask = self._causal_mask(seq.size(1), seq.device)
        hidden = self.transformer(seq, mask=mask, src_key_padding_mask=padding_mask)
        hidden = self.norm(hidden)

        return {
            "motif_logits": self.motif_head(hidden),
            "x_logits": self.x_head(hidden),
            "y_logits": self.y_head(hidden),
            "transform_logits": self.transform_head(hidden),
        }

    @torch.no_grad()
    def generate(
        self,
        grid_wh: torch.Tensor, symmetry_idx: torch.Tensor, scalars: torch.Tensor,
        max_len: int, temperature: float = 1.0, generator: "torch.Generator | None" = None,
    ) -> list:
        """Autoregressive sampling, ONE sequence at a time (batch size 1
        internally per call -- Phase 5's constrained generation calls
        this repeatedly with different seeds/temperatures for many
        candidates rather than needing batched sampling here). Returns a
        plain list of (motif_id, x, y, transform_id) ints, EOS excluded
        (caller decides whether to keep a sequence that hit max_len
        without emitting EOS -- reported, not hidden, by generate.py)."""
        self.eval()
        device = grid_wh.device
        motif_seq = torch.empty((1, 0), dtype=torch.long, device=device)
        x_seq = torch.empty((1, 0), dtype=torch.long, device=device)
        y_seq = torch.empty((1, 0), dtype=torch.long, device=device)
        t_seq = torch.empty((1, 0), dtype=torch.long, device=device)

        out_tokens = []
        for _ in range(max_len):
            if motif_seq.size(1) == 0:
                # first step: feed a single PAD placeholder as input so
                # forward()'s token embedding has SOMETHING to embed at
                # T=0 before any real token exists -- its output at
                # position 0 (right after the condition token) is what
                # predicts the FIRST real token.
                m_in = torch.full((1, 1), PAD_MOTIF_ID, dtype=torch.long, device=device)
                x_in = torch.zeros((1, 1), dtype=torch.long, device=device)
                y_in = torch.zeros((1, 1), dtype=torch.long, device=device)
                t_in = torch.zeros((1, 1), dtype=torch.long, device=device)
            else:
                m_in, x_in, y_in, t_in = motif_seq, x_seq, y_seq, t_seq

            out = self.forward(grid_wh, symmetry_idx, scalars, m_in, x_in, y_in, t_in)
            last = -1  # last position's prediction is the next token

            def sample(logits_key, size):
                logits = out[logits_key][0, last] / max(temperature, 1e-6)
                probs = torch.softmax(logits, dim=-1)
                return torch.multinomial(probs, 1, generator=generator).item()

            next_motif = sample("motif_logits", self.config.vocab_size)
            if next_motif == EOS_MOTIF_ID:
                break
            next_x = sample("x_logits", MAX_GRID)
            next_y = sample("y_logits", MAX_GRID)
            next_t = sample("transform_logits", N_TRANSFORMS)
            out_tokens.append((next_motif, next_x, next_y, next_t))

            motif_seq = torch.cat([motif_seq, torch.tensor([[next_motif]], device=device)], dim=1)
            x_seq = torch.cat([x_seq, torch.tensor([[next_x]], device=device)], dim=1)
            y_seq = torch.cat([y_seq, torch.tensor([[next_y]], device=device)], dim=1)
            t_seq = torch.cat([t_seq, torch.tensor([[next_t]], device=device)], dim=1)

        return out_tokens
