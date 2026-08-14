# M4.2 Parity-Aware Generation - Evaluation

**Result: a real, measured, marginal success.** Combining
connectivity-aware AND parity-aware placement scoring produced
**PULLI's first-ever valid novel-generated candidate (1/120)** - 0/120
in every session since M3.7, including the connectivity-only experiment
immediately before this one. Mean odd-degree-node count dropped
sharply (55.90 → 9.38, min reaching 0), confirming parity scoring works
as designed. **But the same change also WORSENED average fragmentation**
(mean components 19.99 → 98.12) relative to connectivity-alone, a real
tension between the two objectives that this report analyzes rather
than papers over. **1/120 (0.83%) is not enough to call the M4.2
validity gate reliably passed** - this is reported as genuine progress,
not as completion.

## 1. Problem statement

`docs/M4_2_CONNECTIVITY_EVALUATION.md` established that connectivity-aware
scoring fixes fragmentation (mean components 82.42→19.99) but leaves
validity at 0/120, because the 5 candidates that DO reach a single
component still have 18-166 odd-degree nodes - Eulerian validity
(`engine.validity.check_validity`) requires the largest component to
have either 0 odd-degree nodes (circuit) or exactly 2 (path). Parity was
identified as the precise next bottleneck.

## 2. Existing generation behavior

`select_novel_placements` (`engine/novel_generation.py`) is a single
deterministic forward pass over a fixed candidate order
(`sorted(interior) × library × D4_TRANSFORMS`). Each candidate is scored
and immediately accepted or rejected - there is no backtracking, no
re-evaluation of already-accepted placements, and no lookahead. The
existing `_novel_score` already has a LOCAL parity term (reward/penalty
for a previously-touched node flipping between odd/even), but it
explicitly does NOT count parity for a node touched for the first time
(`degree_before == 0`) - a deliberate fix for a different bootstrap
problem (see that function's own docstring). This means a newly-touched
node ending up at ODD degree (e.g., one endpoint of an open-path motif)
was never counted as a cost by the original scoring at all.

## 3. Why connectivity scoring was insufficient

Connectivity-aware scoring optimizes purely for merging/extending
components - it has no awareness of degree parity. A placement that
perfectly bridges two components can just as easily leave both bridge
endpoints at odd degree as at even degree; nothing in `_connectivity_score`
distinguishes those cases. The Session-19 benchmark's 5 fully-connected
candidates are direct proof: full connectivity was reached with 18-166
odd-degree nodes still present, because nothing in that scoring pass
ever tried to reduce that count.

## 4. Parity scoring design

`_parity_effect(degree_before, contribution)`: computes `odd_before`,
`odd_after`, and `delta_odd = odd_after - odd_before` by scanning ONLY
the nodes `contribution` touches (any untouched node's degree, and
therefore parity, is provably unchanged by this placement - so this is
an EXACT global computation, not a local approximation limited to the
placement's own edges, per the task's explicit requirement). `deg_change`
sums ALL of a placement's edge counts touching a node - identical
arithmetic to `_novel_score`'s own `deg_change`, which is what makes
repeated-strand placements correct for free: an odd number of new
parallel strands flips `(deg_before + deg_change) % 2`; an even number
preserves it. No special-casing for multiplicity was needed because the
modular arithmetic already encodes it exactly.

`_parity_score(effect, neutral)`: `-PARITY_IMPROVEMENT_WEIGHT * delta_odd`
when `neutral=False` (reduction scores positive, increase scores
negative, no change scores exactly 0); returns `0.0` unconditionally
when `neutral=True`.

**The bootstrap guard was NOT optional - it was found necessary by
direct testing, exactly as it was for connectivity:**

- A first, unguarded version (`neutral` always `False`) caused **total
  collapse: `select_novel_placements` returned ZERO placements on every
  tested input**, identical in shape to the original `_novel_score`
  bootstrap bug and the connectivity bootstrap bug both already
  documented. Cause: on an empty graph, `odd_before` is always 0 for the
  very first candidate, but many real motif shapes (e.g. any motif with
  an odd-degree endpoint, like an open path) leave `odd_after > 0` -
  `delta_odd > 0`, penalized, rejected. Since nothing is ever accepted,
  no structure ever exists, so EVERY subsequent candidate is evaluated
  from the same all-singleton state - the collapse is total, not a slow
  start.
- **Fix**: reuse the exact same `any_real_structure_exists` flag
  `select_novel_placements` already tracks for connectivity's bootstrap
  guard. `neutral=True` (parity term contributes exactly 0, per this
  task's own literal instruction - "for an empty/initial state, parity
  scoring should be neutral") until the first placement is ever
  accepted; active in both directions afterward.

**Weight calibration** (`PARITY_IMPROVEMENT_WEIGHT`): swept `{0.25, 0.5,
1, 2} × EDGE_UNIT_COST` on a real unseen layout
(`kolam19#15`, connectivity_aware=True). Odd-degree count dropped
sharply between 0.5× (26) and 1× (4), with diminishing further gain at
2× (2); connected-component count was flat (13) across ALL four
weights on this input - the weight affects HOW parity-clean the result
is, not how fragmented, on this test case. **1× `EDGE_UNIT_COST` (a
plain, symmetric weight - reward and penalty at the same magnitude, no
asymmetric hand-tuning) was selected** as a reasonable point past the
steepest improvement, without exhaustively optimizing (per the task's
explicit "do not choose arbitrary weights without documenting them" -
documented above - and general "do not optimize prematurely").

## 5. Mathematical interpretation

`check_validity`'s actual criterion (`engine/validity.py`, unmodified,
verified by direct reading, NOT redefined anywhere in this experiment)
checks Eulerian-ness of the **largest connected component only**:
`nx.is_eulerian(Gc)` (0 odd-degree nodes) or `nx.has_eulerian_path(Gc)`
(exactly 2), where `Gc` is the subgraph induced by the largest
component. `_parity_effect`'s `delta_odd`, as implemented, counts odd
nodes across the WHOLE accumulated graph (every touched node, regardless
of which eventual component it ends up in) - this is what the task
explicitly specified ("Parity is a global property of the graph"). The
two are closely related but not identical: a placement could reduce the
GLOBAL odd count while acting entirely inside a component that never
becomes the LARGEST one, contributing nothing to the actual gate. This
is a real, acknowledged imprecision in the proxy objective, not a bug -
narrowing the parity signal to "only the largest component, tracked
incrementally" was considered but not implemented (it would require
re-deriving "largest component" on every trial, which the union-find
already tracks size for cheaply - a natural extension for a future
session, not attempted here to keep this experiment focused on ONE
change at a time, per this project's own repeated engineering
discipline).

## 6. Implementation

- `engine/novel_generation.py`: `PARITY_IMPROVEMENT_WEIGHT` constant,
  `_parity_effect()`, `_parity_score()`, new `parity_aware: bool = False`
  parameter on `select_novel_placements` and `generate_novel_kolam`
  (fully independent of `connectivity_aware` - either flag may be used
  alone or combined).
- `engine/generation_api.py`: `GenerationConstraints.parity_aware`
  (default `False`), threaded through.
- `experiments/m4_2_generation/run_benchmark.py`: `run()` gained a
  `parity_aware` parameter (default `False`, exact original behavior
  preserved) plus `n_odd_degree_nodes` per-row/summary fields.
- `experiments/m4_2_generation/run_parity_comparison.py` (new): the A/B/C
  harness this report's numbers come from.

## 7. Test results

`tests/test_parity_scoring.py`, 14 new tests, covering the task's 10
numbered requirements plus 4 supporting checks (bootstrap-collapse
regression, measured odd-count reduction, `GenerationConstraints`
wiring, default value). **Full suite: 227/227 passing** (213 before this
session + 14 new). No existing test modified or weakened.

## 8. 120-candidate benchmark (×3 arms, 360 candidates total)

Identical config across all three arms (10 libraries × 6 layouts × 2
multiplicity caps = 120 candidates/arm), via
`experiments/m4_2_generation/run_parity_comparison.py`. Full results:
`experiments/m4_2_generation/results/parity_comparison.json`.

## 9. Before/after table

| Metric | A: Baseline | B: Connectivity | C: Connectivity + Parity |
|---|---:|---:|---:|
| Valid | 0/120 | 0/120 | **1/120** |
| Fully connected | 0/120 | 5/120 | 3/120 |
| Mean components | 82.42 | 19.99 | **98.12** |
| Mean odd-degree nodes | 45.93 | 55.90 | **9.38** |
| Min odd-degree nodes | 8 | 6 | **0** |
| Unique rate | 43.3% | 85.8% | 78.3% |
| Exact duplicates (any) | 0.0% | 0.0% | 0.0% |
| Multiplicity violations | 0/120 | 0/120 | 0/120 |
| Runtime/candidate | 0.256s | 0.791s | 0.377s |

Note the non-monotonic pattern: parity-aware scoring reduces mean
odd-degree count dramatically (55.90→9.38) but at the cost of WORSENING
mean fragmentation relative to connectivity-alone (19.99→98.12) - see
Section 10 for why.

## 10. Failure analysis

**Why does adding parity-awareness make average fragmentation worse?**
Both `_connectivity_score` and `_parity_score` are ADDITIVE terms on the
SAME single `score <= 0: continue` gate. A placement that would help
connectivity (merging two components) but leaves a bad parity outcome
(e.g. converts an even-degree bridge point to odd) now has its
connectivity reward partially or fully cancelled by a parity penalty -
some placements that arm B accepted (because connectivity alone made
them net-positive) are now REJECTED in arm C (because the combined
score is now negative). Fewer accepted placements, on average, means
more of the layout stays untouched, i.e. more singleton/small
components - directly explaining the mean-component increase. This is
the OPPOSITE tradeoff from Section 4's calibration finding: there, a
too-strong CONNECTIVITY penalty starved the merge mechanism; here, a
correctly-weighted PARITY term still competes with connectivity for the
same accept/reject decision, and parity wins more often than expected,
since the two objectives are not always aligned (a placement can be
connectivity-positive and parity-negative at the same time).

**All 3 fully-connected candidates in arm C, examined individually**
(not just aggregated):

| library | layout | placements | odd nodes | valid |
|---|---|---|---|---|
| single_kolam29_2 | real_layout_kolam19_20 | 30 | 20 | False |
| multi_kolam19_1_kolam19_2 | real_layout_kolam19_20 | 21 | 4 | False |
| **multi_kolam19_1_kolam19_5** | **real_layout_kolam19_20** | 21 | **2** | **True** - the ONE valid candidate, an Eulerian PATH (`has_eulerian_path=True`, `is_eulerian_circuit=False`) |

**Striking pattern: all 3 fully-connected arm-C candidates, including
the one valid one, occurred on the SAME layout** (`kolam19#20`, an
unseen real dot layout) - none on any synthetic grid, none on
`kolam29#3` (which DID produce fully-connected candidates in arm B).
This strongly suggests the greedy heuristic's success is highly
layout-dependent (some real layouts happen to have a candidate ordering
where connectivity- and parity-improving placements align well enough,
by chance of the fixed deterministic scan order, to reach validity) -
not yet a robust, general capability.

**The `multi_kolam19_1_kolam19_2` near-miss (4 odd nodes, so close to 2)
is the single most informative failure case**: it reached full
connectivity with only 4 odd-degree nodes remaining - extremely close
to the 0-or-2 target. Manually inspecting whether "later placements
could theoretically cancel those parity violations": by construction,
the search is a SINGLE FORWARD PASS with no revisiting - once the
`interior × library × transform` candidate list is exhausted, there is
no second chance to place one more small motif that would flip exactly
those 4 nodes back to even. **The greedy, non-backtracking ordering is
the direct, demonstrated cause of this near-miss failing** - not a
scoring-weight problem (Section 4 already showed weight has limited
further effect on this class of case) and not a multiplicity-cap
problem (`max_multiplicity=2` was already the more permissive setting
used by all 3 fully-connected candidates).

## 11. Did the M4.2 validity gate pass?

**No, not reliably.** `docs/M4_2_GENERATION.md`'s own gate table lists
"generated patterns are structurally valid" as one binary checklist
item; this session moves it from a flat "0/120, never observed" to
"1/120, observed once, on one specific layout out of six tested,
non-reproducible on any other layout in this exact benchmark." A 0.83%
success rate, concentrated on a single input, is proof of concept that
the mechanism CAN work, not evidence of a dependable generation
capability. Per this task's own explicit framing (preferring
"0/120 → 7/120 with honest analysis" over declaring completion for its
own sake), **M4.2 remains PARTIAL.**

## 12. Remaining bottleneck

**The single-pass, non-backtracking search structure itself.** Section
10's near-miss analysis (4 odd nodes, unreachable by any later
placement in the same pass) is direct, specific evidence that the
scoring objective is no longer the limiting factor for the BEST
candidates found so far - the search STRATEGY is. A greedy pass that
locks in every accept/reject decision permanently, with no ability to
revisit a placement once made, cannot generally converge on exactly 0
or 2 odd nodes without either (a) exceptional luck in candidate
ordering (as happened once, on one layout), or (b) some form of
lookahead, backtracking, or a final constrained "closing" pass that
specifically targets the LAST few remaining odd-degree nodes.

## 13. Recommendation for the next experiment

**A bounded, opt-in "closing pass" experiment**: after the existing
single forward pass completes, run ONE additional, clearly-labeled,
SEPARATE pass that considers ONLY candidates whose sole purpose is
reducing the CURRENT (already fixed) set of remaining odd-degree nodes
toward 0 or 2 - still built from the SAME motif library (no new edges
invented, no source residual copied, no silent repair: every accepted
edge in this pass is still a real, motif-shaped, contribution-derived
placement, exactly like the main pass), but explicitly scored ONLY on
parity effect, since by this point connectivity and novelty have
already been decided. This is a genuinely NEW, separately-scoped
experiment (a second search phase, not a scoring-weight change) and
should be evaluated with its own before/after benchmark before being
considered for adoption - per this task's own explicit rule against
"stacking hacks" onto a single scoring function. Do not attempt this by
loosening `check_validity` or by falling back to
`engine.reconstruction`'s residual mechanism; both are explicitly
forbidden by this project's own generation/reconstruction distinction
(`docs/NOVEL_GENERATION.md`).

## M5 gate - explicit answer (re-asked, still relevant)

**"Is PULLI ready to begin M5?" Still no.** 1/120 valid, on one layout,
is not "generated candidates the system can reliably produce as grammar
input." The gap narrowed measurably this session (0→1) but the honest
answer has not changed since `docs/M4_2_CONNECTIVITY_EVALUATION.md`'s
own answer to this same question.
