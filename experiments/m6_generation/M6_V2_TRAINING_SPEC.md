# M6 V2 training specification

Built on `M6_V2_DESIGN.md`'s chosen architecture (neural proposal +
deterministic constraint layer, anchor+motif prediction instead of
independent x/y sampling).

## Minimum useful dataset size — determined from existing data, not assumed

The task explicitly warns against assuming 10k+ examples are required.
M6 V1 already used 11,000 examples (`experiments/m6_generation/results/dataset_report.json`)
and failed for a REPRESENTATION reason (independent x/y sampling allows
disconnection), not a DATA VOLUME reason — nothing in V1's failure mode
(0/100 valid, severe fragmentation from step 1) suggests more data of
the SAME representation would have helped, since the model was never
structurally prevented from proposing disconnected points regardless of
how much it saw.

**Recommendation: reuse the EXISTING 11,000-example dataset
(`experiments/m6_generation/data/{train,val,test}.jsonl`) unchanged for
V2's first training run** — re-encode the SAME token sequences into
V2's (anchor, motif, transform) representation (a re-encoding, not a
new data-collection effort) and measure whether the representation
change alone fixes connectivity before spending time collecting more
data. Only increase dataset size in a V2.1 if the re-encoded 11,000-
example run shows a genuine data-scarcity signal (e.g. val loss still
falling steeply at epoch 12, unlike V1's own training curve which had
already flattened: 8.90→7.95 over epochs 1-11, a shallowing not a cliff
— `experiments/m6_generation/results/training_log.json`).

## Training representation / token-state representation

Per-step target changes from V1's `(motif_id, x, y, transform_id)` to:

```
(anchor_index, motif_id, transform_id)
```

where `anchor_index` indexes into the CURRENTLY-PLACED point list (not a
fixed vocabulary — a pointer-network-style index, 0..current_length-1,
plus a special "ANCHOR_ORIGIN" value for the very first placement, which
has no existing point to anchor to). The new point's absolute
coordinates are DERIVED: `existing_points[anchor_index] + motif's
relative offset under transform_id` — never predicted directly. This is
the representation-level fix `M6_V2_DESIGN.md` identifies as the root
correction for V1's failure.

Re-encoding `build_dataset.py`'s existing 11,000 examples into this
format requires, for each example's already-recorded token sequence:
replaying it in order, and for each token recording WHICH prior token's
placed point it is Chebyshev/graph-adjacent to (ties broken by sequence
order) as `anchor_index` — a deterministic, no-new-data-needed
transformation of what's already on disk.

## Model architecture

Same backbone family as V1 (causal Transformer, `experiments/m6_generation/model.py`'s
`KolamSequenceGenerator` is the direct ancestor) with these changes:
- `x_head`/`y_head` (each `MAX_GRID`-way, i.e. 64-way classification)
  REMOVED.
- New `anchor_head`: a pointer mechanism — dot-product attention between
  the current hidden state and the hidden states of all PREVIOUSLY
  PLACED tokens (standard pointer-network attention, not a fixed-size
  classification head, since the number of valid anchor choices grows
  with sequence length).
- `motif_head` (vocab_size-way) and `transform_head` (N_TRANSFORMS-way)
  unchanged from V1.

## Parameter budget

V1 was 506,052 params. Removing the two 64-way x/y heads (each
`d_model x MAX_GRID` = 128×64 = 8,192 params, negligible) and adding a
pointer-attention anchor head (roughly one extra attention-head's worth
of parameters, `d_model x d_model` = 128×128 = 16,384 for the query/key
projections) keeps V2 in the SAME parameter class as V1 — **target
~500,000-550,000 params, not a "bigger Transformer"** per the task's own
explicit instruction.

## Train/validation/test split

Reuse `experiments/m5_generation/data/split_manifest.json`'s pattern-
level split UNCHANGED (same 350/75/75 pattern-disjoint split every other
component in this repository already uses) — re-encoding the token
representation does not change which real patterns produced which
examples, so the existing split remains leakage-safe.

## Losses

- **Primary**: per-step cross-entropy on (anchor_index, motif_id,
  transform_id), same masked-loss convention V1's `train.py` already
  implements (`loss_mask` over padding).
- **Auxiliary structural losses — recommended, with justification**:
  - **Connectivity loss: NOT needed as a soft loss term.** Per
    `M6_V2_DESIGN.md`, the anchor-pointer representation makes
    disconnection STRUCTURALLY IMPOSSIBLE by construction (every new
    point is defined relative to an existing one) — a soft penalty
    would be redundant with a hard representational guarantee already
    in place. Do not add one; it would only add training noise for no
    correctness benefit.
  - **Multiplicity loss: recommended as a HARD constraint at decoding
    time (reuse `engine.novel_generation`'s existing multiplicity-cap
    check), NOT a soft training loss.** Per M5.1's own Phase 4 finding
    (Variant A: a hard cap alone, with no fallback, collapses validity
    68.3%→13.3%), a purely hard constraint without a repair fallback is
    demonstrably too aggressive — but that finding was about REPAIR
    (post-hoc), not decode-time proposal rejection-and-resample (which
    has a cheap alternative: reject and resample a different anchor/motif,
    at generation time, before commitment — unlike repair, which must
    work with whatever the search already built).
  - **Symmetry conditioning: NOT a loss term** — per
    `M5_1_CONSTRAINT_SPEC.md` Section 2.1, real data shows NO symmetry
    bias to train toward (mean coverage 19.7%, 0% of patterns "high
    symmetry"). `symmetry` remains a CONDITIONING INPUT (as in V1,
    unchanged) so a caller can still ask for `symmetry=rotational4`, but
    training data is not re-weighted toward it.

## Complexity conditioning

Unchanged from V1: `(complexity, density)` scalar conditioning inputs,
computed the same way `build_dataset.py` already does
(`min(1.0, n_distinct_edges / (3 * n_dots))` and
`min(1.0, n_edge_instances / n_dots / 6.0)`).

## Decoding algorithm

Greedy-with-rejection-and-resample, bounded:

```
for step in range(max_steps):
    propose (anchor_index, motif_id, transform_id) from model
    derive new_point = existing_points[anchor_index] + motif offset[transform_id]
    if new_point already in dot_points AND placement passes multiplicity check:
        accept, append to sequence
    else:
        resample (bounded to K_RESAMPLE attempts, e.g. 5); if all fail, skip this step (do not force)
    if model proposes EOS (or every node has even degree -- new early-stop signal): break
```

This differs from V1's plain `torch.multinomial` sampling only by
adding the reject-and-resample loop around the HARD constraints
(multiplicity, valid-lattice-membership) — the same "never force an
invalid placement through" discipline `engine.novel_generation.select_novel_placements`
already uses for its own accept/reject gate.

## Stopping criterion

EOS token (unchanged from V1) OR max_steps reached OR (new) the partial
graph is ALREADY fully valid (every node even-degree, single component)
— giving the model a genuine "I'm done and correct" signal distinct
from "I ran out of room," which V1 never had.

## Invalid-state handling

Because the anchor-pointer representation prevents disconnection by
construction, the ONLY residual invalid states V2 can produce are (a)
parity failures (odd-degree nodes) if the model stops before achieving
even degree everywhere, or (b) hitting max_steps without EOS. Both are
handled EXACTLY as M5 already does: `engine.learned_generation.repair_multiplicity`
(with M5.1's evidence-preferred two-tier or reroute-aware strategy) for
(a); reporting `hit_max_len_without_eos: True` honestly for (b), same
field V1's `assemble_and_validate` already tracks.

## Checkpoint strategy

Unchanged from V1's `train.py` (already implements this correctly):
save every epoch to a rolling checkpoint (resumable), save a SEPARATE
best-val-loss checkpoint, early-stop on patience. No changes needed —
V1's training LOOP was never the problem; only the per-step target
representation was.

## Training compute estimate

V1 took 1,972s (12 epochs, 7,700 train examples, 506K params, CPU,
`torch_threads=4`). V2's architecture is parameter-comparable, so a
first V2 training run should be budgeted similarly (~35-45 minutes) —
not a reason to skip validating the representation fix before investing
in a longer run.
