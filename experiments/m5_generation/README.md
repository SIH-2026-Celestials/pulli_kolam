# M5 -- Learned-Scorer-Guided Novel Kolam Generation

## Audit finding (bottleneck, in code-level terms)

Traced the full pipeline: dot layout -> motif library
(`engine.motifs.induce_motif_set_adaptive`) -> placement selection
(`engine.novel_generation.select_novel_placements`) -> candidate graph
(`engine.generation.build_candidate_graph`) -> hard validity gate
(`engine.validity.check_validity`, Eulerian-circuit-or-path over the
largest connected component) -> trace reconstruction
(`engine.generation.reconstruct_dot_trace`) -> render (`engine.render`).

The bottleneck is **not** detection, not rendering, not the validity
definition -- it is the **placement-selection search** in
`select_novel_placements`: a single deterministic greedy pass over a
fixed candidate order (sorted interior point x motif x D4 transform),
accepting a candidate iff a fixed hand-tuned linear score
(`_novel_score` [+ `_connectivity_score` [+ `_parity_score`]]) is
positive. It never revisits an earlier decision. Measured result
(`experiments/m4_2_generation/results/*.json`, all pre-existing, read
not regenerated this session):

| generator | n | validity rate |
|---|---|---|
| baseline greedy | 120 | 0/120 = 0% |
| + connectivity-aware | 120 | 0/120 = 0% (fragmentation reduced 82.4 -> 20.0 mean components, but never reaches 1) |
| + connectivity + parity-aware | 120 | 1/120 = 0.8% |
| multi-restart beam (hand-tuned score, pre-M5) | 120 | 9/120 = 7.5% |

So restarts/backtracking clearly help (0.8% -> 7.5%), but the
**scoring function itself** was still a hand-guessed linear
combination, never fit to what actually distinguishes a placement that
belongs in a real valid kolam from one that doesn't.

## What this session did

Found that `engine/learned_generation.py`, `engine/learned_scoring.py`,
`engine/generation_api.py`, and `experiments/m5_generation/{build_training_data.py,
train_placement_scorer.py,run_benchmark.py}` already existed on disk
(uncommitted) from a prior session, including a already-built,
pattern-level-split training dataset
(`experiments/m5_generation/data/{train,val,test}.npz`, 528175/108690/122675
examples from 350/75/75 patterns of kolam19+kolam29, leakage-safe split
by pattern ID -- see `build_training_data.py`'s `_split_pattern_ids`) --
but **no trained checkpoint and no benchmark results existed yet**. This
session:

1. Verified the audit above (bottleneck identification) independently
   before touching anything.
2. Trained `engine.learned_scoring.PlacementScorer` (MLP, 16 -> 32 -> 16
   -> 1, **1089 parameters**) via `train_placement_scorer.py`: binary
   classification, "does this placement belong in a valid
   reconstruction of the real pattern it was replayed against" (oracle
   label from teacher-forced replay against real edge multisets --
   ground truth is used ONLY to compute the label, never as a model
   feature). Result: checkpoint at
   `experiments/m5_generation/checkpoints/placement_scorer.pt`.
3. Ran the existing multi-restart search
   (`engine.learned_generation.generate_novel_kolam_learned`: 16
   independent greedy passes in different shuffled candidate orders,
   scored by the trained MLP instead of the hand-tuned linear score,
   keep the structurally best; then bounded, geometry-safe multiplicity
   repair -- never invents new lattice geometry, only increases the
   strand count of edges the candidate already placed, along
   `diagnose_validity`'s own shortest-path corrections, capped at
   multiplicity 3) at REDUCED scale (see "Scale note" below) on
   held-out TEST-split patterns only.
4. Measured validity/connectivity/multiplicity/novelty/latency exactly
   as the pre-existing `run_benchmark.py` defines them (this session's
   `run_benchmark_lite.py` computes IDENTICAL metrics at smaller N,
   documented not hidden).
5. Generated and rendered actual novel Kolam SVGs via
   `engine.generation_contract.generate_kolam` (new production-facing
   interface this session, wrapping the search above) --
   `experiments/m5_generation/artifacts/valid/*.svg` +`.json` metadata
   per successful candidate, failed attempts logged separately in
   `artifacts/failed/`.

## Scale note (time-budget decision, not hidden)

Direct timing measurement: one candidate at n_restarts=16 on a 200-dot
real held-out layout took ~24 seconds (CPU-only, per this repo's
existing convention). The originally-committed `run_benchmark.py`
(N_CANDIDATES=500, N_RESTARTS=16) would take on the order of 3-4 hours
-- outside this session's budget. `run_benchmark_lite.py` runs the
IDENTICAL metric computation at N_CANDIDATES=80, N_RESTARTS=12 and
reports itself as reduced-scale (see its `SCALE_NOTE` field in the
output JSON). `run_benchmark.py` itself is unmodified and can be run
later with a larger time budget for the full 500-candidate evaluation.

## Files

- `engine/learned_scoring.py` -- `PlacementScorer` (MLP), feature
  extraction, checkpoint load/save. (pre-existing, untouched this
  session other than training it)
- `engine/learned_generation.py` -- multi-restart search + bounded
  repair. (pre-existing, untouched)
- `engine/generation_contract.py` -- **new this session**: production
  inference contract, `generate_kolam(...) -> dict` with
  success/graph/render/validity/novelty/metrics/model fields.
- `experiments/m5_generation/train_placement_scorer.py` -- trains the
  scorer (pre-existing script, run this session).
- `experiments/m5_generation/run_benchmark.py` -- full serious
  benchmark (pre-existing, NOT completed this session -- too slow, see
  scale note).
- `experiments/m5_generation/run_benchmark_lite.py` -- **new this
  session**: reduced-scale version of the above, same metrics.
- `experiments/m5_generation/generate_and_render.py` -- **new this
  session**: produces actual rendered novel Kolam SVGs via the
  production contract.
- `experiments/m5_generation/compare_all.py` -- **new this session**:
  assembles the full decision matrix against every prior generator this
  project has measured.

See `experiments/m5_generation/results/` for all numeric results and
`docs/M4_2_GENERATION.md` for the pre-M5 generation history this work
builds on.
