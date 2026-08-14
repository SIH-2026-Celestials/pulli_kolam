# M4.2 Connectivity-Aware Generation - Evaluation

**Result: a real, measured, partial improvement - NOT full validity.**
Connectivity-aware placement scoring cuts average fragmentation by
**~4×** (mean connected components 82.42 → 19.99 across the same
120-candidate benchmark) and gets **5/120 candidates to a single
connected component** (0/120 before) - but **validity remains 0/120**.
Every one of those 5 fully-connected candidates fails on the Eulerian
parity check, with between 18 and 166 odd-degree nodes remaining.
**Connectivity was the wrong bottleneck to blame for validity being
zero; it was A bottleneck, and fixing it exposed the next one
precisely.** This is reported in full, not softened.

## 1. Baseline problem

`docs/M4_2_GENERATION.md`'s 120-candidate benchmark measured 0/120
valid novel candidates. The documented root cause (`docs/NOVEL_GENERATION.md`,
M3.7, confirmed again at n=120): `select_novel_placements` scores each
candidate placement using only LOCAL information (which dots does this
placement touch, what does it do to THEIR degree parity) - it has no
notion of which other dots are already part of the same connected
structure. A single deterministic forward pass over a fixed candidate
order therefore accepts placements scattered across the whole layout
with no bias toward connecting them to each other.

## 2. Hypothesis

If placement scoring is made connectivity-aware - rewarding placements
that merge two already-real structural fragments or extend one into a
fresh dot, and discouraging (with the right weight - see Section 4)
placements that create yet another disconnected fragment - the search
should converge toward fewer, larger components, and validity should
improve as a consequence of more candidates reaching a single
connected component that also happens to be Eulerian.

**This hypothesis is only PARTIALLY confirmed** (Section 8): the
connectivity half worked as predicted; the "and also Eulerian" half did
not follow for free.

## 3. Algorithm change

`engine/novel_generation.py`, additive only (default behavior
unchanged - `connectivity_aware: bool = False` on both
`select_novel_placements` and `generate_novel_kolam`; `engine/generation_api.py`'s
`GenerationConstraints` gained the same flag):

- **`_UnionFind`**: a minimal incremental disjoint-set over the target
  dot layout. Used ONLY as an efficient, always-current view of which
  dots are already connected as the search accepts placements one at a
  time - `engine.validity.check_validity` (unmodified) still runs the
  authoritative check via `nx.connected_components` on the final
  assembled graph; the union-find never substitutes for it.
- **`_connectivity_effect(uf, contribution)`**: for one candidate
  placement's stamped edges (which can span several component pairs at
  once - a placement is not assumed to be one edge), classifies each
  edge that would cross a component boundary as one of `n_merge_real`
  (both sides already belong to a component of size > 1), `n_extend`
  (one side untouched, one side already real), or `n_new_isolated_pair`
  (both sides untouched singletons). A local, this-call-only merge map
  deduplicates multiple edges bridging the SAME two components within
  one placement, so they count once. This function never mutates the
  global union-find - it is a pure trial.
- **`_connectivity_score(effect, penalize_new_isolated)`**: combines the
  classification into one additive score term, in the same
  `EDGE_UNIT_COST`-scaled currency `_novel_score` already uses.
- **The bootstrap guard**: `penalize_new_isolated` starts `False` and
  only becomes `True` after the FIRST placement is ever accepted. See
  Section 4 for why this is not optional.

## 4. Exact scoring/objective definition

```
score = _novel_score(motif, contribution, degree)          # UNCHANGED, existing objective
      + _connectivity_score(effect, penalize_new_isolated)  # NEW, additive
```

```
_connectivity_score = MERGE_REAL_REWARD   * n_merge_real
                     + EXTEND_REWARD       * n_extend
                     - NEW_ISOLATED_PENALTY * n_new_isolated_pair   (only if penalize_new_isolated)
```

Final weights, in `EDGE_UNIT_COST` units (`EDGE_UNIT_COST = 4`):

| constant | value | value × EDGE_UNIT_COST |
|---|---|---|
| `CONNECTIVITY_MERGE_REAL_REWARD` | 8 | 32 |
| `CONNECTIVITY_EXTEND_REWARD` | 4 | 16 |
| `CONNECTIVITY_NEW_ISOLATED_PENALTY` | 0.05 | 0.2 |

**These weights were empirically calibrated, not guessed - and the
calibration itself is a real finding, reported honestly:**

- A first attempt used `(3, 1, 1)` (penalty at the same scale as the
  rewards). Result: **select_novel_placements returned ZERO
  placements** on every test input - the exact same "bootstrap
  collapse" failure mode `_novel_score`'s own docstring already
  documents for its parity term, reproduced here via a different
  mechanism: the very FIRST placement ever accepted, on an
  all-singleton union-find, is BY DEFINITION a "new isolated pair" (there
  is nothing yet to merge with or extend). An unconditional penalty
  punishes the one thing every candidate must eventually do to start
  anything. **Fixed by the bootstrap guard** (Section 3) - the penalty
  only applies once real structure already exists elsewhere.
- Even WITH the bootstrap guard, a sensitivity sweep across
  `(merge, extend, isolated)` weight combinations on a real unseen
  layout (`kolam19#15`, library from `kolam19#1`) found that **any
  isolated-pair penalty weight ≥ 0.1× `EDGE_UNIT_COST` made
  fragmentation WORSE than weight 0** (13 components vs. 3, same input).
  The reason: in a SINGLE forward greedy pass with no backtracking, a
  freshly-created isolated fragment is not pure waste - it is the ONLY
  raw material a LATER candidate can ever merge into something real
  (`n_merge_real` requires two components of size > 1 to already
  exist). Suppressing fragment creation starves the merge mechanism of
  the very fragments it depends on. **The threshold between "no
  measurable effect" and "actively harmful" was found to sit between
  0.05 and 0.1×; 0.05× was selected as the largest value confirmed
  identical to 0 across a 4-layout check** (real and synthetic), so the
  penalty mechanism the task requires is real and tested
  (`tests/test_connectivity_scoring.py`), without being the dominant
  term in practice.
- `MERGE_REAL_REWARD` and `EXTEND_REWARD` were swept together over
  `(3,1)` through `(20,10)`; component count improved monotonically up
  to roughly `(8,4)` and returned diminishing, sometimes mixed, further
  gains beyond that on the specific layouts tested. `(8, 4)` was
  selected as a reasonable, not exhaustively optimal, stopping point -
  consistent with the task's explicit "do not optimize prematurely."

## 5. Experimental configuration

Both arms use **`experiments/m4_2_generation/run_benchmark.py`'s
`run()`** with `connectivity_aware` as the ONLY difference - same
function, same fixed grid, so the two arms cannot silently drift out of
sync:

- 10 motif libraries (5 single-source kolam19, 2 single-source kolam29,
  3 multi-source pooled)
- 6 dot layouts (3 synthetic rectangular grids: 6×6, 10×10, 14×14; 3
  unseen real layouts: `kolam19#15`, `kolam19#20`, `kolam29#3`)
- 2 multiplicity caps (1, 2)
- **120 candidates per arm**, same as the original M4.2-C/D benchmark
- Run via `experiments/m4_2_generation/run_connectivity_comparison.py`,
  full output `experiments/m4_2_generation/results/connectivity_comparison.json`

## 6. Baseline results (arm A, connectivity_aware=False)

Reproduces `docs/M4_2_GENERATION.md`'s original numbers exactly (verified
by direct re-run before this comparison, byte-identical):

| metric | value |
|---|---|
| Validity rate | 0/120 (0.0%) |
| Fully connected (1 component) | 0/120 (0.0%) |
| Connected components | min 2, mean 82.42, max 369 |
| Multiplicity violations | 0/120 |
| Unique candidates (novelty) | 52/120 (43.3%) |
| Exact duplicate rate (topological or coordinate) | 0.0% |
| Runtime | 30.11s total, 0.2509s/candidate |

## 7. Connectivity-aware results (arm B, connectivity_aware=True)

| metric | value |
|---|---|
| Validity rate | **0/120 (0.0%)** - unchanged |
| Fully connected (1 component) | **5/120 (4.2%)** - up from 0 |
| Connected components | min **1**, mean **19.99**, max 209 |
| Multiplicity violations | 0/120 - unchanged |
| Unique candidates (novelty) | **103/120 (85.8%)** - up from 43.3% |
| Exact duplicate rate (topological or coordinate) | 0.0% - unchanged |
| Runtime | 95.66s total, 0.7971s/candidate - **~3.2× slower** |

## 8. Validity comparison

**Unchanged: 0/120 in both arms.** Connectivity-aware scoring measurably
fixes fragmentation (mean components 82.42 → 19.99, a ~4× reduction;
5 candidates now reach exactly 1 component where 0 did before) but does
NOT fix Eulerian parity, which `check_validity`'s hard gate ALSO
requires. See Section 11 for the exact odd-degree-node counts on the 5
fully-connected candidates - this is not a near-miss; the parity gap is
large (18 to 166 odd-degree nodes on 212-456-dot layouts).

## 9. Novelty comparison

**Improved, not degraded - worth stating plainly since it was not the
target of this change.** Unique-candidate rate rose from 43.3% to
85.8%. This is best explained by connectivity-aware candidates simply
having MORE placements on average (mean 15.62 vs. 4.05 - nearly 4×),
which makes each candidate's shape more distinct from the others by
construction, not by any deliberate novelty-seeking mechanism.
Exact-duplicate rate (against source patterns) stayed at 0.0% in both
arms - connectivity-aware generation still does not copy its sources.

## 10. Runtime comparison

Connectivity-aware scoring is **~3.2× slower** (0.2509s → 0.7971s per
candidate; 30.11s → 95.66s total for 120 candidates). The union-find
trial (`_connectivity_effect`) itself is cheap (near-O(1) amortized per
edge); the actual cost is that connectivity-aware scoring ACCEPTS more
candidates on average (mean placements 4.05 → 15.62), so
`select_novel_placements`'s own per-accepted-placement bookkeeping
(accumulating edges, updating degree/union-find) simply runs more
times. This is a real, measured cost, not a rounding artifact - worth
knowing before enabling this by default in any latency-sensitive path
(none currently exists; `api/` does not call generation at all).

## 11. Failure cases

All 5 fully-connected-but-invalid candidates, with their actual
odd-degree-node counts (computed directly from each candidate's own
graph, not estimated):

| library | layout | max_mult | n_dots | placements | odd-degree nodes |
|---|---|---|---|---|---|
| single_kolam19_5 | real_layout_kolam29_3 | 2 | 456 | 18 | 166 |
| single_kolam29_2 | real_layout_kolam19_20 | 2 | 212 | 30 | 68 |
| multi_kolam19_1_kolam19_2 | real_layout_kolam19_20 | 2 | 212 | 23 | 18 |
| multi_kolam19_1_kolam19_5 | real_layout_kolam19_20 | 2 | 212 | 22 | 20 |
| multi_kolam19_1_kolam19_5 | real_layout_kolam29_3 | 2 | 456 | 29 | 40 |

Two clear patterns, both real and worth flagging for the next attempt:

1. **All 5 fully-connected candidates occurred on REAL unseen layouts,
   none on synthetic rectangular grids** - consistent with
   `docs/M4_2_GENERATION.md`'s own earlier finding that real kolam dot
   layouts offer richer motif-compatible local neighborhoods than a
   plain grid.
2. **All 5 occurred at `max_multiplicity=2`, none at 1** - the extra
   strand budget likely gives the connectivity-aware search more
   candidate edges to find a bridging placement with.

Eulerian validity needs the largest component to have either 0
odd-degree nodes (circuit) or exactly 2 (path). 18-166 is nowhere close
- **this is a distinct, unaddressed problem, not a tuning shortfall of
the connectivity change.** `_novel_score`'s existing parity term does
react to individual placements' effect on individual nodes' parity, but
nothing in either the old or new scoring has any GLOBAL view of "how
many odd-degree nodes remain in the whole candidate right now" the way
`_connectivity_effect` gives a global view of components.

## 12. Interpretation

The hypothesis in Section 2 is half right. Connectivity-aware scoring
IS the correct mechanism for the fragmentation problem specifically -
the ~4× reduction in mean component count and the appearance of
single-component candidates (previously literally never observed) are
real, structural, reproducible evidence of that, not noise. But
"structurally valid" per this project's own hard gate
(`engine.validity.check_validity`) requires BOTH full connectivity AND
Eulerian parity, and this change only targets the first. **Validity
being 0/120 in both arms could have meant either "connectivity is the
whole problem" or "connectivity is one of at least two problems" - this
experiment distinguishes those two possibilities directly, and the
answer is the second one.** That is a genuine, useful, negative-on-the-
headline-metric result, not a wasted effort: it converts a vague "the
generator doesn't work" into a precise "the generator now reliably gets
close to connected, and separately still needs a parity-aware
mechanism."

## 13. Is M4.2 now COMPLETE or PARTIAL?

**Still PARTIAL.** Per the task's own stated success criteria
("Only declare M4.2 COMPLETE if the generator itself produces valid
novel candidates under the project's existing validity definition and
the result is demonstrated by benchmark evidence") - validity is 0/120
in this benchmark, identical to before. Connectivity-aware scoring is a
real, measured, additive improvement (fragmentation, novelty), but it
does not clear the actual gate. Declaring COMPLETE here would be
exactly the kind of premature declaration the project's rules
explicitly forbid.

## 14. Recommended next step

**A parity-aware term, symmetric in spirit to the connectivity-aware
term added this session.** Concretely: extend `_connectivity_effect` (or
add a sibling function) that tracks, alongside the union-find, a
running count of odd-degree nodes in the CURRENT candidate graph, and
reward placements that reduce this count (or keep it at exactly 0 or 2)
over ones that increase it - the same "additive score term, same
currency, opt-in flag, bootstrap-guard-checked" pattern this session
already established and validated as sound engineering practice, not a
new design idiom to invent. This is a distinct, well-scoped next
experiment, not a variant of this one - do not attempt to retrofit it
into `_connectivity_score` without its own sensitivity check, since
this session's clearest lesson (Section 4) is that naive weight choices
for this style of additive scoring term can silently collapse the
search entirely.

## M5 gate - explicit answer

**"Is PULLI ready to begin M5?" No.**

M5 consumes structurally valid generated candidates as its raw input
(parsing them into grammar descriptions, generating new ones from a
grammar, searching for constraint-satisfying structures). This
session's benchmark evidence is that the generator still produces 0/120
valid novel candidates - a parity-aware mechanism (Section 14) is a
concrete, scoped prerequisite, not yet attempted. Beginning M5 now would
mean building a grammar layer with no valid candidates to parse or
target, which is exactly the kind of "code exists but doesn't answer
the real question" outcome this project's rules explicitly warn
against. M5 remains NOT STARTED, correctly, until a future session
either closes the parity gap or makes a deliberate, evidenced decision
to scope M5 around RECONSTRUCTION-derived valid patterns instead of
NOVEL-generation ones (reconstruction, unlike novel generation, always
reaches validity via its residual fallback - see
`docs/RECONSTRUCTION.md` - and was never in question here).
