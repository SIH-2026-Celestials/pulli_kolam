# M5.1 Constraint Specification

Evidence sources (all real, all cited by exact file):
`structural_dataset_report.json` (500 real patterns, Phase 2),
`benchmark_failure_analysis.json` (M5's final 500-candidate run, Phase 3),
`m5_1_counterfactual_report.json` (60-candidate/variant diagnostic runs, Phase 4).
No threshold below is invented  -  each traces to a specific measurement.

## 1. Hard constraints

### 1.1 Maximum edge multiplicity = 2

- **Motivation:** eliminate the repair-induced multiplicity-3 edges found
  in 97.5% of M5's repaired-valid candidates.
- **Empirical evidence:** `structural_dataset_report.json`
  `A_edge_multiplicity`: 181,966 edges measured across all 500 real
  patterns, maximum observed multiplicity = **2**, zero patterns contain
  multiplicity > 2. This is not a soft preference  -  it is the entire
  observed support of the real distribution.
- **Exact condition:** `max(edge_multiplicity.values()) <= 2` for the
  final candidate graph.
- **Hard or soft:** HARD, but see 3.1/4.1 below for *where* this is
  enforced  -  a naive hard cap during repair alone (Variant A) collapses
  validity from 68.3% → 13.3% (`m5_1_counterfactual_report.json`,
  N=60/variant, same seeds). The cap belongs in the search phase (already
  correct: `DEFAULT_MAX_MULTIPLICITY = 2`) with a SMARTER repair strategy
  underneath it (Section 4), not a blunt post-hoc rejection.
- **Expected computational cost:** none beyond what M5 already pays  - 
  `engine.novel_generation.DEFAULT_MAX_MULTIPLICITY` is already 2; this
  constraint is about fixing `engine.learned_generation.DEFAULT_REPAIR_MAX_MULTIPLICITY`
  (currently 3) to match, not adding new computation.
- **Failure behavior:** a candidate that cannot be repaired within the
  multiplicity-2 budget stays reported as invalid (never silently
  relaxed)  -  same "skip, don't force" discipline `repair_multiplicity`
  already uses for `n_nodes_outside_largest_component > 0`.

### 1.2 Single connected component (no merged/invented edges)

- **Motivation:** already enforced, confirmed correct by evidence  -  keep
  as-is.
- **Empirical evidence:** `structural_dataset_report.json`
  `C_connectivity`: 500/500 real patterns are a single connected
  component (`fraction_fully_connected: 1.0`).
- **Exact condition:** `check_validity(G)["largest_component_covers_all_nodes"] == True`.
- **Hard or soft:** HARD (already the case; `engine.validity.check_validity`
  is never softened per its own module docstring).
- **Failure behavior:** `repair_multiplicity` already correctly refuses
  to merge components (returns candidate unchanged)  -  this is the
  DOMINANT failure mode of M5 (141/141 invalid candidates fail here,
  0/141 fail on parity alone, `benchmark_failure_analysis.json`) and is
  NOT something repair should ever try to fix by inventing geometry.

### 1.3 Eulerian circuit or Eulerian path on the largest component

- Already `engine.validity.check_validity`'s definition; confirmed by
  Phase 2 that 100% of real patterns are Eulerian circuits (closed loop)
  and 0% are open paths (`G_structural_complexity.fraction_eulerian_circuit_closed_loop: 1.0`).
  This is informative for a FUTURE generator's target distribution
  (Section 6/M6_V2_DESIGN.md) but is not itself a new constraint on M5  - 
  M5 already accepts either circuit or path per the task's own original
  hard-gate definition, and changing that now would be scope creep
  unsupported by a *generation* need (open paths are a legitimate
  Eulerian structure even if this specific real corpus happens not to
  contain any).

## 2. Soft constraints

### 2.1 Symmetry coverage  -  NOT recommended as a constraint

- **Motivation considered:** real patterns average only 19.7% D4 coverage
  (`structural_dataset_report.json` `F_symmetry.mean_coverage: 0.1974`,
  median 0.19, **0% of real patterns reach "high symmetry" (≥0.5)**).
  M5's own candidates average 21.6% (`benchmark_report.json`), already
  statistically indistinguishable from real data.
- **Decision: do NOT add a symmetry-steering constraint.** The evidence
  shows M5 is already unbiased relative to real data on this axis  - 
  adding a soft symmetry bonus would move candidates AWAY from the real
  distribution, not toward it. This is the clearest example in this
  spec of an "arbitrary rule that sounds mathematically elegant" the
  task explicitly warned against  -  rejected on evidence, not omitted by
  oversight.

### 2.2 Edge-length locality preference

- **Motivation:** real edges are near-exclusively short:
  `structural_dataset_report.json` `D_edge_locality`: p95 edge length =
  2.0 lattice units, mean 1.575, only 27.45% of edges exceed
  `sqrt(2)` (an immediate diagonal step).
- **Exact condition (soft, scoring-time):** no code change needed today
   -  `engine.motifs.Motif` shapes are already induced from real patterns'
  own local windows (`local_window`, radius 1 by default), which
  structurally cannot produce edges longer than the induction radius
  allows. This constraint is ALREADY implicitly satisfied by construction,
  not something to bolt on. Recorded here so a future generator (which
  is NOT constrained to only emit induced-motif edges) knows the
  empirical bound to respect (see M6_V2 specs).
- **Hard or soft:** SOFT for any future free-form edge generator; N/A
  (already structurally guaranteed) for M5 itself.

## 3. Search constraints

### 3.1 Multiplicity cap during search: KEEP at 2 (already correct)

- Confirmed correct by Section 1.1's evidence. No change recommended.

### 3.2 Restart count / connectivity effort  -  supported by evidence, not yet confirmed as the fix

- **Motivation:** Phase 3 found connectivity is the ONLY failure mode
  (100% of invalid candidates, 0% pure-parity failures)  -  so effort
  spent finding a connected structure is the highest-leverage lever
  available to search.
- **Empirical evidence (complete, N=60/variant, same seeds 0-59):**
  baseline/A/B/C all show an IDENTICAL `connectivity_failure_rate` of
  31.67% (19/60) regardless of repair strategy  -  expected, since repair
  cannot affect search-phase connectivity outcomes, confirming
  connectivity is decided entirely in the search phase. **Variant D
  (n_restarts=12) reduced connectivity_failure_rate to 21.67% (13/60)  - 
  a real ~10-percentage-point improvement  -  raising overall validity
  from 68.3% to 78.3%, at 2.03x latency cost (9.5s → 19.2s/candidate).**
- **Decision: doubling `n_restarts` from 6 to 12 is a genuine, measured
  win on validity, at a real and non-trivial latency cost.** Whether
  this tradeoff is worth taking is a DEPLOYMENT decision (is 19.2s/candidate
  acceptable for the target use case?), not a correctness question  -  this
  spec recommends making `n_restarts` a caller-configurable parameter
  (already exposed as such in `engine.learned_generation.generate_novel_kolam_learned`)
  rather than hard-changing the default, so latency-sensitive callers
  (e.g. the live API) keep the current 6/9.5s tradeoff while a batch/
  offline generation job can opt into 12/19.2s for higher yield. The
  diminishing-but-real per-restart gain (an additional 6 restarts bought
  10 points of connectivity, not 20) suggests restart count has
  DECREASING returns  -  not a reason to keep pushing it arbitrarily
  higher without re-measuring, but not yet a dead end either.
- Search-phase restart count IS therefore a real, usable lever  -  but it
  does not eliminate the connectivity problem (78.3% is still short of
  100%), so M6 V2's connectivity-aware decoding approach (Section 6)
  remains the correct longer-term investment; Variant D is a legitimate
  near-term improvement to ship alongside it, not a substitute for it.
- **Hard or soft:** SOFT (a resource/latency tradeoff, not a
  correctness rule).
- **Expected computational cost:** linear in n_restarts  -  doubling
  restarts roughly doubles worst-case latency per candidate (measured
  baseline avg latency 9.48s/candidate at n_restarts=6).

## 4. Repair constraints

### 4.1 Two-tier (soft) repair: cap=2 first, cap=3 fallback only if unresolved

- **Motivation:** Variant A (hard cap=2, no fallback) proved a naive cap
  is too costly (validity 68.3% → 13.3%)  -  SOME real corrections
  genuinely require a third strand on some edge to close parity within
  the search-phase structure that's already been built (not because real
  DATA has multiplicity 3, but because a search-phase candidate's
  specific residual parity defects may not always be closable by
  doubling only never-yet-doubled edges).
- **Empirical evidence:** Variant B (soft two-tier) recovers validity
  fully (68.3%, statistically identical to baseline's 68.3%) while
  reducing the multiplicity-violation rate from 63.3% → 55.0%  -  a real
  but modest improvement. The fallback tier was needed in 52/60 = 86.7%
  of repaired cases, meaning most corrections genuinely cannot be closed
  within a multiplicity-2 budget given the CURRENT search output.
- **Exact condition:** call `repair_multiplicity(candidate, max_repair_multiplicity=2)`
  first; if still invalid, call `repair_multiplicity(candidate, max_repair_multiplicity=3)`
  on the result. (Exactly `experiments/m5_generation/m5_1_counterfactual_experiment.py::_two_tier_repair`.)
- **Hard or soft:** SOFT preference (prefer cap=2, allow cap=3 as a
  documented, measured fallback  -  never silently).
- **Failure behavior:** unchanged from current `repair_multiplicity`  - 
  a correction that cannot be satisfied even at cap=3 is skipped, not
  forced.
- **Verdict: RECOMMENDED as an immediate, low-risk improvement over the
  current single-tier cap=3 default**  -  same validity, meaningfully
  fewer multiplicity violations, and it's a 5-line change layered on
  existing, unmodified `repair_multiplicity` calls (two calls instead of
  one), not a new algorithm.

### 4.2 Reroute-aware repair (try alternate shortest paths before escalating)

- **Motivation:** the two-tier fallback (4.1) still needs multiplicity-3
  87% of the time because it always uses the SAME shortest path
  `diagnose_validity` computed  -  if that path happens to cross an
  already-doubled edge, there is no way to avoid it without also trying
  a DIFFERENT path between the same two odd-degree nodes.
- **Exact condition:** implemented and measured in Phase 4 as Variant C
  (`_reroute_aware_repair`: try up to 5 alternate shortest simple paths
  via `nx.shortest_simple_paths`, prefer any that avoids reusing an
  already-multiplicity-2 edge, escalate to multiplicity 3 only if none
  of the 5 alternates avoid it).
- **Hard or soft:** SOFT (a smarter search over the SAME repair problem,
  not a different correctness rule).
- **Expected computational cost:** `nx.shortest_simple_paths` is more
  expensive than a single `nx.shortest_path` call (generates paths in
  increasing length order, lazily)  -  bounded here to 5 alternates per
  correction, so worst-case cost is a small constant multiple of the
  current repair cost, not unbounded.
- **Measured result (N=60, same seeds):** validity 68.3% (identical to
  baseline and Variant B  -  reroute-awareness does not cost validity),
  multiplicity-violation rate **50.0%** (best of all four repair
  variants tested  -  beats Variant B's 55.0% and baseline's 63.3%),
  latency 9.78s/candidate (statistically indistinguishable from
  baseline's 9.48s  -  the bounded 5-alternate-path search adds
  negligible overhead in practice).
- **Verdict: RECOMMENDED over the simpler two-tier approach (4.1).**
  Variant C dominates Variant B on every measured axis (lower
  violation rate, same validity, near-identical latency)  -  this is not
  a marginal improvement requiring an Occam's-razor tiebreak, it is a
  strict improvement. Combined with Section 1.1: even Variant C's best
  measured 50% violation rate does not reach 0%, meaning **no tested
  repair strategy alone eliminates multiplicity-3 edges**  -  the
  remaining violations reflect genuine cases where every alternate path
  (up to 5 tried) collides with an already-doubled edge. Full
  elimination would require either raising `K_ALTERNATES` further
  (untested, diminishing-returns risk) or accepting that repair-based
  parity-closing has an inherent floor on how well it can respect a
  strict multiplicity-2 cap given search's current output  -  which is
  itself an argument for M6 V2's connectivity-first generation approach
  (Section 6), where fewer parity defects would need correcting in the
  first place.

## 5. Connectivity constraints

Already covered by Section 1.2 (hard) and Section 3.2 (search effort,
soft). No additional connectivity-specific constraint is recommended  - 
Phase 3's evidence is unambiguous that connectivity is a SEARCH problem,
not a validation-rule problem; the validation rule (`check_validity`)
is already correct and should not change.

## 6. Symmetry constraints

Explicitly NOT recommended  -  see Section 2.1. Real data does not support
a symmetry-steering constraint.

## 7. Complexity constraints

- **Motivation considered:** should M5 be constrained toward real
  patterns' observed complexity (mean 256.7 nodes, mean 363.9 distinct
  edges, `structural_dataset_report.json` `G_structural_complexity`)?
- **Decision: NOT recommended as a new constraint on M5 today.** M5
  operates on WHATEVER dot layout it's given (test-split real patterns'
  own layouts, per `run_benchmark.py`)  -  its edge/node counts are
  therefore already bounded by the input layout's own real scale
  (measured `avg_n_edges: 321.4` in the Phase 4 counterfactual runs,
  well within the real corpus's observed range). A complexity constraint
  would matter for a FREE-FORM generator not tied to a real layout
  (i.e., M6, not M5)  -  deferred to `M6_V2_TRAINING_SPEC.md`.

## 8. Novelty constraints

- **Current state, confirmed working:** M5's final benchmark measured
  100% unique fingerprints, 0% exact duplicates, 0% near-duplicates
  against source patterns (`benchmark_report.json`'s `novelty` block).
  No constraint change is needed or recommended  -  novelty is not a
  problem this phase needs to solve.

## Summary recommendation for immediate M5.1 action (final, all 5 variants measured)

| variant | validity | mult. violation | connectivity failure | latency |
|---|---|---|---|---|
| baseline (current production) | 68.3% | 63.3% | 31.7% | 9.5s |
| A: hard cap=2, no fallback | 13.3% | 0.0% | 31.7% | 9.4s |
| B: soft two-tier (cap 2, fallback 3) | 68.3% | 55.0% | 31.7% | 9.4s |
| **C: reroute-aware repair** | **68.3%** | **50.0%** | 31.7% | 9.8s |
| D: connectivity-first (n_restarts=12) + reroute repair | **78.3%** | 60.0%* | **21.7%** | 19.2s |

*Variant D's higher violation rate than C at the same repair strategy is
consistent with it resolving MORE candidates overall (more repairs
attempted → more opportunities for a violation), not a regression in
the repair mechanism itself  -  the repair strategy is identical to C.

1. **Replace `DEFAULT_REPAIR_MAX_MULTIPLICITY = 3`'s flat single-tier
   repair with reroute-aware repair (Section 4.2 / Variant C)**  -  the
   single clearly-best repair strategy tested: strictly dominates the
   two-tier fallback (4.1) on every axis, cuts the multiplicity-
   violation rate from 63.3% to 50.0% at no validity cost and
   negligible (0.3s) latency cost. This is the recommended immediate
   code change.
2. **Make `n_restarts` a deployment-tunable parameter, default
   unchanged at 6 for latency-sensitive callers, with 12 documented as
   a measured, available option for yield-sensitive/offline use**  - 
   Variant D proves it's a real lever (68.3%→78.3% validity) but at 2x
   latency, a genuine tradeoff rather than a strict improvement, so it
   should be a choice, not a forced default change.
3. **Do NOT add a symmetry-steering or complexity-steering constraint**
    -  both rejected on direct evidence (Section 2.1, Section 7).
4. **Multiplicity-3 will NOT be fully eliminated by repair-side fixes
   alone**  -  even the best-tested repair strategy (C) leaves 50% of
   repaired candidates with a violation. Full elimination requires
   either a more exhaustive reroute search (untested beyond
   `K_ALTERNATES=5`) or, more fundamentally, M6 V2's connectivity-first
   generation approach producing search-phase output with fewer parity
   defects to repair in the first place.
5. **This document does not modify production M5**  -  see
   `experiments/m5_generation/m5_1_counterfactual_experiment.py` for the
   isolated implementation (all 5 variants, fully measured, N=60/variant,
   same seeds 0-59 throughout) and
   `experiments/m5_generation/results/m5_1_counterfactual_report.json`
   for the complete raw data. Applying recommendation 1 or 2 to
   `engine/learned_generation.py` is a deliberate, separate follow-up
   action, not implied by this spec's existence  -  per the task's
   explicit instruction not to modify production M5 in this phase.
