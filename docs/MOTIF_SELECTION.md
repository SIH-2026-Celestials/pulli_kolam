# Motif Selection (M3.6)

Not AI, not machine learning. This is a deterministic, greedy structural
algorithm, exactly like `engine.motifs.induce_motif_set_adaptive` before
it - the change is what it tracks and checks, not the nature of the
method.

## Why ordinary edge coverage is insufficient

Every pre-M3.6 induction function tracks edge coverage as a **distinct
pair set**: `induce_motif_set`, `induce_motif_set_adaptive`, and
`mdl_gain` all reduce a source pattern's edges to
`{frozenset(e) for e in G.edges()}` - a Python `set`, which silently
collapses a double-strand edge (source multiplicity 2) down to the same
single boolean "covered / not covered" as a single-strand edge. Once any
placement touches a pair, that pair is marked done; nothing tracks *how
many strands* have actually been accounted for. This was a known,
explicitly documented limitation as far back as `compression_ratio`'s
own docstring (M3 session): "covering an edge once counts as fully
explained even if the original has a double strand there."

## What over-explanation means

Because coverage is boolean, two *different* motif placements can each
independently decide a dot pair is worth stamping, and `build_candidate_graph`
(which has no source to check against) will happily add both - netting
2, 3, or more strands on a pair where the source has only 1. This is
**over-explanation**: the motif-only candidate ends up with more
parallel strands on some edges than the real pattern ever had.

Measured directly (not theorized) across all 6 patterns via
`validate_motif_selection.py`, mode A (`induce_motif_set_adaptive`,
unmodified):

| pattern | over-explained edges | multiplicity agreement |
|---|---|---|
| kolam19#1 | 68 | 60.5% |
| kolam19#26 | 36 | 69.6% |
| kolam29#1 | 136 | 68.5% |
| kolam29#26 | 102 | 75.8% |
| kolam109#1 | 2968 | 58.9% |
| kolam109#26 | 2620 | 61.4% |

Over-explanation is why M3.5's `reconstruct_kolam` (which can only ever
*add* missing strands, never remove excess ones) still failed Eulerian
validity on all 6 real patterns even after reaching 100% distinct-edge
coverage - see `docs/RECONSTRUCTION.md`.

## Why MultiGraph multiplicity matters

A double strand is real, deliberately-drawn structure (see
`docs/DATA_FORMAT.md`'s concrete example: the same dot pair connected
twice by the curve arcing around a skipped dot on two different sides).
Collapsing it to `nx.Graph` would corrupt vertex-degree parity and break
the Eulerian validity check outright - this was established from the
very first session and has never changed. M3.6 does not touch this: all
selection here still operates on `nx.MultiGraph`, and every test in
`tests/test_motif_selection.py` verifies parallel strands survive intact
through selection AND through `build_candidate_graph`.

## Multiplicity-aware selection

`engine.motif_selection.induce_motif_set_multiplicity_aware(source,
radius=1, max_radius=3)`:

1. **Simulate, don't assume.** For every candidate `(motif, point,
   transform)` stamp, `simulate_placement_contribution` computes its
   exact predicted per-edge STRAND contribution as a `Counter` (not a
   set) - a motif with a repeated relative edge correctly reports
   contributing 2 to that edge from one stamp.
2. **Reject, never clip.** `violates_multiplicity(contribution,
   accumulated, source_multiplicity)` is a hard, binary predicate: would
   accepting this contribution push ANY touched edge's running total
   above what `source` actually has? If yes, the WHOLE placement is
   rejected - there is no partial-acceptance path anywhere in this
   module. The algorithm knows the placement is incompatible; it does
   not silently repair it into something smaller.
3. **Score at the motif-TYPE-group level, filter at the individual-point
   level.** Candidates are grouped by canonical motif type (same shape
   `_build_candidates` already produces), and a group's score amortizes
   its motif-rule cost across every point that reuses it - an early
   design that scored one individual point at a time was tried and
   discarded (see git history / module docstring): it made every brand-
   new motif type score negative on its lone first instance, since the
   rule cost isn't yet amortized, so nothing ever got selected. But
   within an accepted group, each individual point is STILL
   independently checked against the running multiplicity total - a
   group can be selected and only part of its points end up placed.
4. **Score, transparently.** `EDGE_UNIT_COST * strands_explained -
   motif_rule_cost (once per new type) - PLACEMENT_COST` - the exact
   same currency `compression_ratio`/`mdl_gain` already established, not
   a new arbitrary scale. "Remaining uncovered edges" (the fourth factor
   the task asked to consider) is satisfied structurally rather than as
   an extra weighted term: `violates_multiplicity` already guarantees
   every strand counted in an accepted contribution had real deficit
   remaining, so every point of score is, by construction, useful
   progress - not an independent bonus layered on top.
5. **Guarantee, not heuristic.** By construction,
   `accumulated_multiplicity[e] <= source_multiplicity[e]` for every
   edge, always - verified directly in
   `test_greedy_selection_never_exceeds_source_multiplicity_on_real_data`.

## Eulerian-aware selection

`engine.motif_selection.induce_motif_set_eulerian_aware` uses the exact
same greedy core and the exact same hard multiplicity constraint -
nothing about parity ever overrides it. It only changes the scoring
function: `_parity_delta` counts, for a candidate's touched vertices, how
many move from odd degree to even minus how many move from even to odd,
and this is added as a bonus (`PARITY_BONUS = EDGE_UNIT_COST`, the same
unit as one newly-explained strand - chosen for transparency, not
because it is provably optimal).

Measured effect, all 6 patterns, motif-only candidates (no residual):

| pattern | odd-degree count: A | B (mult-aware) | C (mult+Eulerian) |
|---|---|---|---|
| kolam19#1 | 44 | 18 | **6** |
| kolam19#26 | 40 | 22 | **12** |
| kolam29#1 | 88 | 146 | **62** |
| kolam29#26 | 88 | 72 | **48** |
| kolam109#1 | 1736 | 1846 | **800** |
| kolam109#26 | 1580 | 1240 | **1138** |

C reduces odd-degree count relative to B on every single pattern, often
substantially (kolam19#1: 18 → 6; kolam109#1: 1846 → 800). Interestingly,
C also has HIGHER edge recall than B on every pattern (avg 81.5% vs
76.8%) - preferring parity-improving candidates over pure density
sometimes happens to pick motif types that also cover more ground, a
side effect worth noting, not something the scoring function targets
directly.

**Important interpretive caveat**: none of A, B, or C reach full
Eulerian validity on the motif-only candidate for ANY of the 6 patterns
(0/6 valid across all three modes) - this was never expected. Reaching
validity motif-only would require closing every remaining odd-degree
vertex exactly, and even C's substantial reduction leaves hundreds to
thousands of odd vertices on the larger patterns. What DOES reliably
reach validity is motif+residual reconstruction (see
`docs/RECONSTRUCTION.md`) - but see the next caveat for why that's not
as informative a comparison as it first appears.

**A second interpretive caveat, about `compression_ratio` specifically**:
`engine.motifs.compression_ratio` only counts *distinct* residual edges,
not strand multiplicity - it was never designed to penalize
over-explanation (that concept didn't exist when it was written). This
means mode A's compression ratio can look BETTER than B's on some
patterns (e.g. kolam19#1: A=1.77 vs B=1.64) purely because A's excess
strands are invisible to that metric, even though A is measurably worse
on the very defect (over-explanation) this whole phase exists to fix.
Reading `compression_ratio` alone, without the over-explanation and
multiplicity-agreement numbers alongside it, would give a misleading
picture of which mode is actually better. `compression_ratio` was not
modified in M3.6 (out of scope - the task only asked for selection
changes) - this caveat is flagged, not fixed.

**Why motif+residual validity isn't a meaningful per-pattern
differentiator between B and C**: since B and C both guarantee
`accumulated <= source` for every edge, adding back the exact residual
deficit always reproduces `source`'s edge multiset EXACTLY -
`multiplicity_exact_match = True`, always, by construction. And since
every real CSV-sourced pattern is itself always valid (pre-verified
dataset), motif+residual reconstruction is therefore ALWAYS valid for
both B and C, on every pattern - verified directly on 4 of the 6 real
patterns (kolam19#1/#26, kolam29#1/#26). This is a real, structural
consequence of the multiplicity guarantee (not a new algorithm doing
extra work at reconstruction time), and it means "is motif+residual
valid" cannot distinguish B from C at all - both always say yes. The
metric that actually differentiates B from C is the MOTIF-ONLY behavior
above (odd-degree count, recall) - that's the honest, informative
comparison, and it's why `docs/MOTIF_SELECTION.md`'s tables report
motif-only numbers, not motif+residual ones.

## Limitations of greedy selection

- **No lookahead, no backtracking.** A motif-type group's accept/reject
  decision, once made, is permanent - exactly like the pre-existing
  `induce_motif_set`'s `candidates.pop(best_cm)`. A greedy choice that
  looks best this round can foreclose a better combination two rounds
  later; this is never revisited.
- **No ILP/CP-SAT.** Explicitly out of scope for this baseline, per the
  task instructions. An exact solver could in principle find a
  provably-optimal multiplicity-respecting motif set; this greedy
  algorithm makes no optimality claim, only the structural
  no-over-explanation guarantee.
- **Recall dropped relative to mode A.** Rejecting violating candidates
  means B's average recall (76.8%) is *lower* than A's (87.8%) - the
  price of the correctness guarantee is coverage. C partially recovers
  some of this (81.5%) as a side effect of its scoring, not by design.
- **Runtime grows with the Eulerian bonus.** C is consistently slower
  than A/B (measured: 13.3s vs 8.0s/8.6s on kolam109#1) - the parity
  bookkeeping (`_parity_delta`, tracking a running `degree` Counter) adds
  real per-candidate cost. Still tractable at every scale tested.
- **Group-then-filter is a specific, chosen design, not the only valid
  one.** Scoring at the group level (not the individual point level) was
  a deliberate fix for a real bug found during development (see module
  docstring) - but it means a motif type's rule cost is judged based on
  its FULL point list's potential, even though some of those points may
  later get filtered out for violating multiplicity, occasionally
  over- or under-valuing a group relative to what it will actually
  contribute once filtered.

## Example

Real-data experiment, `kolam19` #1 (228 distinct source edges), motif-only
candidates, no residual:

```
       mode  motifs  recall  over_expl  mult_agree  components  odd  valid  compress  time
A (existing)      8  0.9035         68      0.6053          15   44  False    1.7743  0.14s
B (mult-aware)     9  0.8158          0      0.8158          30   18  False    1.6432  0.15s
C (mult+euler)    10  0.8596          0      0.8596          26    6  False    1.7175  0.16s
```

Full 6-pattern table and summary averages: `validate_motif_selection.py`.
