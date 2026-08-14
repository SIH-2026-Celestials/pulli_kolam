# Real-Data Reconstruction (M3.5)

## The core distinction this document exists to keep separate

Three different questions, easy to accidentally conflate, kept as three
separate, separately-testable code paths:

1. **Motif explanation** - how many source edges are explained by
   reusable motifs? Already answered by
   `engine.motifs.induce_motif_set_adaptive`'s own recall bookkeeping
   (see the MDL-gating session's results already on record). Not
   re-litigated here.
2. **Reconstruction** - can a source Kolam be reconstructed as ONE
   connected, Eulerian-valid structure? This is what
   `engine.reconstruction.reconstruct_kolam` answers, by adding back the
   EXACT source edges no motif explained.
3. **Novel generation** - can motifs produce a valid structure on a NEW,
   unseen dot layout, without copying source-specific residual edges?
   **Not implemented in M3.5.** `reconstruct_kolam` always targets
   `source.dot_points` and always copies real source edges for the
   residual - it is explicitly NOT this.

**`reconstruct_kolam` is not novel generation.** It answers one narrow
question: is the motif/residual *decomposition* of a real pattern itself
internally consistent - does motif-edges + residual-edges reproduce
something structurally valid? It is a diagnostic on the decomposition,
not a generator of new patterns.

## Three modes, kept distinguishable

| Mode | Function | dot layout | Residual edges | What it answers |
|---|---|---|---|---|
| A. Reconstruction | `reconstruct_kolam(source, placements)` | `source.dot_points` (fixed) | Copied verbatim from `source.graph` | Is the decomposition of THIS pattern self-consistent? |
| B. Motif-only generation | `generate_kolam(placements, dot_points)` (unchanged from M3) | caller-supplied | None - never added | What does the motif rule set alone produce? |
| C. Novel generation | *(not built)* | unseen/new | N/A - no source to copy from | Future work, out of scope for M3.5 |

`tests/test_reconstruction.py::test_motif_only_and_reconstruction_remain_distinguishable`
checks A and B give genuinely different `is_valid`/edge-count answers on
the same inputs, not the same answer computed twice under different names.

## Motif + residual reconstruction

`reconstruct_kolam(source: KolamPattern, placements: list[MotifPlacement], residual_policy="exact")`:

1. Build the motif-only candidate graph via the EXISTING, unmodified
   `engine.generation.build_candidate_graph` (reused, not reimplemented).
2. Count each distinct dot-pair's multiplicity in `source.graph` and in
   the motif-only candidate.
3. For every pair where source has MORE strands than the motif-only
   candidate produced, copy back exactly the deficit - no more, no less
   - from source. This is `residual_policy="exact"`, the only policy
   implemented; anything else raises (see "Known limitations").
4. The result is one `nx.MultiGraph`: motif-only edges + the exact
   residual strands, run through the SAME unmodified
   `check_validity`/`diagnose_validity` gate.

`ReconstructionResult.compare_to_source()` reports source vs. candidate
on exactly what Task 2 asked for: unique edges, total edge strands, edge
multiplicity (exact dict equality, not just counts), connected
components, Eulerian validity.

## Motif-only generation (the honest contrast)

`engine.reconstruction.motif_only_report(source, placements)` wraps the
EXISTING, UNCHANGED `generate_kolam` (no residual edges added,
automatically or otherwise) and adds the one measurement `generate_kolam`
itself has no reason to compute (it doesn't take a source pattern as
input at all): edge recall against a known source. This is the
"motif-only" baseline the reconstruction result is compared against.

## Do not call residuals noise

Residual edges are **unexplained structure**, not noise. A residual edge
exists in the real, hand-drawn source pattern - it is real ink, drawn on
purpose, by whoever made the original Kolam. It failing to match a
*reusable* motif means one of:

- it's part of a repeating motif the current radius/MDL-gate search
  didn't find (a search-completeness gap, not a property of the edge),
- it's a genuine one-off decorative flourish specific to this pattern
  (a real design choice, not an error), or
- the motif vocabulary this project currently searches (D4-symmetric,
  local, radius ≤ 3 windows) genuinely cannot express whatever local
  rule produced it.

None of these mean the edge is wrong, noisy, or safe to drop. Every
residual edge reconstruction copies is a real edge from the real source
graph.

## Novel generation

**Not attempted in M3.5.** Producing a valid structure on an unseen dot
layout - without any residual edges to fall back on, since there is no
source to copy from - needs the motif rules alone to be sufficient to
close every vertex's degree parity and connect the whole layout. The
real-data experiment below shows this is not yet true even ON THE
SOURCE'S OWN layout (motif-only is disconnected/invalid on every pattern
tested) - so attempting it on a genuinely new layout first would not be
a meaningful test of anything. This is explicitly deferred, per the task
instructions ("do not attempt arbitrary target layouts yet").

## Known limitations

- **Only `residual_policy="exact"` exists.** It is the correct baseline
  for answering "is the decomposition self-consistent," but it is also
  the least interesting policy long-term (it can only ever reproduce
  `source` exactly, never anything new). Other policies (e.g. a
  residual drawn from a *different* pattern's leftover structure, or an
  approximate/synthetic residual) are unimplemented future work.
- **Over-explanation is real and not corrected here.** A dot pair can
  end up with MORE parallel strands in the motif-only candidate than
  `source` actually has, when two overlapping motif windows (adjacent
  placements whose radius-`r` neighborhoods share an edge) each
  independently stamp it. `reconstruct_kolam`'s residual step only ever
  ADDS missing strands - it never removes excess ones. This means a
  pattern can reach **full connectivity and full edge coverage** (every
  distinct source edge present) while still **failing Eulerian
  validity**, because the excess strands break degree parity at their
  endpoints. This was measured directly, not theorized: see the
  real-data experiment results below (kolam19 #26 specifically). Fixing
  this (e.g. deduplicating overlapping-window stamps before adding
  residual) is future work, not attempted in M3.5 per "do not optimize
  motif discovery yet."
- Reconstruction inherits every limitation `generate_kolam` already has
  (dot-level trace only, no loop-around/half-integer reconstruction -
  see `docs/GENERATION.md`).

## Example: real-data experiment

Run via `validate_reconstruction.py`, patterns `kolam19`/`kolam29`/`kolam109`
× `{1, 26}` (all six requested IDs exist in their collections, no
substitution needed; induction run at `max_radius=1` for speed - this is
a reconstruction-decomposition check, not a re-run of the MDL-gated
recall numbers already on record).

```
      source   dots  src_edges  motifs  recall  residual  mo_valid  mr_valid  agreement  mult_exact
   kolam19#1    184        228       6  0.7544        56     False     False        1.0       False
  kolam19#26    200        276       7  0.7681        64     False     False        1.0       False
   kolam29#1    472        680       8  0.8059       132     False     False        1.0       False
  kolam29#26    464        644       8  0.7950       132     False     False        1.0       False
  kolam109#1   7016      10628      10  0.8686      1396     False     False        1.0       False
 kolam109#26   6892      10300      10  0.8683      1356     False     False        1.0       False
```

Consistent across **all 6 patterns, every scale tested**: motif-only is
always disconnected (41 to 800 components) and always invalid.
Motif+residual always reaches full connectivity (1 component) AND full
edge agreement (every distinct source edge present) - the residual
mechanism does exactly what it's supposed to. But motif+residual is
**still invalid on all 6 patterns**, because of the over-explanation
limitation above: odd-degree-node count drops substantially after
residual restoration but never reaches zero (e.g. kolam109 #1: 1736 →
1528 odd nodes; kolam19 #26: 40 → 24), and strand count always ends up
higher than source (e.g. kolam109 #1: 12992 → 16248 strands, +3256
excess). This is the same mechanism at every scale, not a small-pattern
artifact.

**Scalability finding, discovered while running this experiment**: the
full pipeline (`reconstruct_kolam`/`generate_kolam`) unconditionally
calls `diagnose_validity`, whose odd-vertex matching is O(k²)
shortest-path computations. At kolam19/29 scale (k in the tens) this is
instant. At kolam109 scale, k reaches 1500+ - a first attempt was killed
after 10+ minutes of CPU time with no result. This script computes the
same required fields via the same real engine functions
(`induce_motif_set_adaptive`, `build_candidate_graph`, `check_validity`)
minus that one expensive diagnostic call. The full `ReconstructionResult`
(with `diagnosis`) remains exercised and correct at kolam19-scale (all
`tests/test_reconstruction.py` tests use it directly). Optimizing
`diagnose_validity`'s matching for large k is unimplemented future work,
out of scope here (task explicitly deferred optimization).
