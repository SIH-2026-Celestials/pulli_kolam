# M6 V2 design  -  evidence-driven architecture selection

Written AFTER M5.1's Phase 1-4 analysis (see
`experiments/m5_generation/M5_1_PIPELINE_AUDIT.md`,
`M5_1_CONSTRAINT_SPEC.md`, `benchmark_failure_analysis.json`,
`m5_1_counterfactual_report.json`) and M6 V1's own measured failure
(`experiments/m6_generation/results/benchmark.json`: 100/100 generated,
**0/100 structurally valid**, 20-45 connected components on a 49-dot
lattice, confirmed NOT fixed by either of two legitimate constrained-
decoding attempts  -  EOS-suppression floor, locality-radius x/y masking).

## What M6 V1 actually got wrong (not guessed  -  measured)

`experiments/m6_generation/model.py`'s `KolamSequenceGenerator.generate`
samples `(motif_id, x, y, transform_id)` autoregressively with FOUR
INDEPENDENT factorized heads. The x and y heads are conditioned only on
the hidden state (which attends back to all prior tokens via causal
self-attention)  -  there is no HARD mechanism forcing a newly-placed
point to be spatially or graph-adjacent to already-placed points. The
model must learn adjacency purely from cross-entropy on real sequences;
at 7,700 training examples / 12 epochs / 506K params, it has not
learned it well enough  -  confirmed by the two additive interventions
tried:

- `min_len` (force more tokens before allowing EOS): did NOT fix
  fragmentation (still 20-45 components)  -  proves the problem is not
  "too few placements," it's "placements that don't connect to each
  other."
- `locality_radius` (mask x/y logits to the bounding box of already-
  placed points, expanded by a radius): did NOT fix fragmentation
  either  -  proves BOUNDING-BOX proximity is insufficient; a point can be
  within the bounding box and still not share an edge/motif-adjacency
  with any existing point, since the x/y heads are sampled independently
  of WHICH existing point (if any) the new placement's motif shape would
  actually connect to.

**Root diagnosis: the representation itself allows disconnected
proposals, and nothing in V1's decoding loop rules them out before they
are accepted into the sequence.** This is a representation/decoding
problem, not a "needs more training" problem  -  more epochs on the same
representation would very likely still allow disconnected placements at
a similar rate, since nothing in the loss function penalizes
disconnection (the loss is per-token cross-entropy against the real
token stream, with no graph-level term).

## Architecture comparison

| # | Architecture | Verdict |
|---|---|---|
| 1 | Pure autoregressive Transformer (M6 V1's own approach, unconstrained) | **Rejected  -  already tried, measured 0% validity.** |
| 2 | Graph/edge generator (predict an adjacency matrix or edge list directly, e.g. one-shot or diffusion-style) | Rejected for V2: requires either a fixed max node count (real patterns range up to ~500+ nodes, `structural_dataset_report.json` `G_structural_complexity`, mean 256.7) making a dense adjacency-matrix output prohibitively large, or a much larger architecture than "compact/CPU-trainable" allows. Not ruled out permanently  -  a possible V3 direction once V2's core connectivity problem is fixed and scale is the next bottleneck. |
| 3 | Neural proposal + constrained decoder (model proposes, deterministic layer accepts/rejects/repairs each step) | **Selected  -  see justification below.** |
| 4 | M5-style search guided by a neural model (no generative sequence model at all  -  reuse M5's placement-scorer-guided multi-restart search unchanged) | This is what M5 ALREADY IS. Re-proposing it as "M6 V2" would not be a new generator, and the task explicitly asks for a genuinely novel neural generator, not a repackaging of M5. Rejected as the *entire* V2 scope, but its core mechanism (a learned per-step ACCEPT/REJECT signal) is directly incorporated into option 3 below. |
| 5 | Hybrid neural + search architecture (neural proposal ranks candidates, search backtracks on rejection) | This is architecturally very close to option 3 with backtracking added. Reasonable, but backtracking multiplies latency (M5's own multi-restart search already costs ~9.5s/candidate at n_restarts=6 for exactly this reason)  -  for a V2 whose goal is to prove the CORE representation fix works, option 3's simpler single-pass constrained decoding is the right first step; backtracking/hybrid search is a natural V3 enhancement once V2's baseline connectivity rate is measured. |

## Chosen: Option 3  -  Neural proposal + deterministic constraint layer

### Why this, specifically, based on evidence:

1. **M5's OWN evidence (Phase 3) shows connectivity, not parity, is the
   hard part.** M5's search-and-repair split already demonstrates the
   winning pattern: a cheap, fast mechanism (greedy/random proposal)
   generates candidates, and a SEPARATE, deterministic, always-correct
   layer (repair) fixes what it can and honestly rejects what it can't.
   V2 should structurally mirror this, but move the constraint
   ENFORCEMENT earlier  -  into the decoding loop itself, at the point
   each token is chosen  -  rather than only after a full sequence is
   generated.

2. **Every one of M5's HARD constraints (Section 1 of
   M5_1_CONSTRAINT_SPEC.md) is ALREADY a cheap, local, incrementally-
   checkable condition** (multiplicity ≤ 2: check one Counter increment;
   connectivity: check via incremental union-find, exactly as
   `engine.novel_generation._UnionFind`/`_connectivity_effect` already
   do). This means constrained decoding is not a research problem here  - 
   the exact incremental-connectivity-tracking code M5's OWN search loop
   already uses (`_UnionFind`, `_connectivity_effect`) can be reused
   almost verbatim inside V2's decoding loop.

3. **The neural model's job shrinks to something it can actually learn
   at this data/parameter scale**: instead of learning "emit a globally
   coherent structure" end-to-end (which V1 failed at), the model only
   needs to learn "given the current partial valid structure, propose a
   plausible NEXT step"  -  a much smaller, more local, more learnable
   distribution, and closer to what `engine.learned_scoring.PlacementScorer`
   already proved IS learnable at a similar (1,089-parameter) scale for
   an analogous per-step decision.

### V2 architecture sketch

```
seed + condition (grid, symmetry, complexity, density)
        |
        v
INITIALIZE valid partial state (empty graph, all dots unvisited)
        |
        v
LOOP (bounded by max_steps):
        |
        v
  neural proposal head: given (partial graph state, condition,
    position embeddings of ALREADY-PLACED points) -> a DISTRIBUTION
    over "which existing point to extend from" x "which motif/transform
    to stamp" -- NOT independent x/y coordinates. This is the single
    biggest representation change from V1: the model chooses an EXISTING
    anchor point + a motif shape, and the new point's coordinates are
    DERIVED deterministically from the anchor + motif's relative
    geometry (exactly how engine.motifs.apply_motif already works) --
    it is IMPOSSIBLE for the model to emit a disconnected point, because
    every proposal is defined relative to something already placed.
        |
        v
  deterministic constraint layer (reuses engine.novel_generation's
    _UnionFind/_connectivity_effect, engine.learned_scoring's multiplicity
    check, both UNMODIFIED): checks multiplicity <= 2 (hard, per
    M5_1_CONSTRAINT_SPEC.md 1.1) and any other cheap local constraint;
    REJECTS and resamples (bounded attempts) if violated, exactly like
    M5's search loop's own `if score <= 0: continue`.
        |
        v
  STOP when: neural model proposes EOS, OR max_steps reached, OR (new,
    vs V1) the constraint layer determines the graph COULD close (every
    node has even degree) -- give the model the option to stop at a
    genuinely valid state, not just wherever it happens to run out of
    budget.
        |
        v
CLOSING PHASE (new, borrowed directly from M5's repair_multiplicity,
  UNMODIFIED call): if the loop ends with residual odd-degree nodes but
  full connectivity, run engine.learned_generation.repair_multiplicity
  (with M5.1's two-tier or reroute-aware strategy, whichever Phase 4
  determines is better) -- V2 does NOT need to re-solve parity-closing;
  M5 already solved that problem well (100% success rate once connected).
        |
        v
engine.validity.check_validity (hard gate, unmodified)
        |
        v
engine.render (unmodified)
```

### What makes this genuinely different from "M5 with extra steps"

M5's search proposes from a FIXED, externally-supplied motif library
(induced from a specific real pattern or a small handful of them) and a
FIXED target lattice (a real pattern's own dot layout). V2's neural
proposal head is a LEARNED distribution over motif+anchor combinations,
conditioned on (grid size, symmetry, complexity, density)  -  it can
generate a structure for a lattice size/shape it has never seen
paired with a specific motif library, and its notion of "what motif
fits here" is learned from the FULL training corpus's patterns jointly,
not selected from one library at generation time. This is the actual
generative/novel capability M5 lacks (M5 can only ever recombine motifs
from whatever library it's handed).

## Summary

**Recommended: Option 3, neural proposal + constrained decoder, with
the proposal head predicting (anchor point, motif, transform) instead
of V1's independent (x, y, motif, transform)  -  this single change
(coordinates DERIVED from an existing anchor rather than SAMPLED
independently) directly and structurally eliminates V1's measured
failure mode, because a disconnected proposal becomes representationally
impossible rather than merely discouraged.**
