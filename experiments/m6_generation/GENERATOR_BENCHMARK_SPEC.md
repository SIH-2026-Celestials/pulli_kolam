# Generator benchmark specification

Applies to ANY future kolam generator (M5.1, M6 V2, or later) — a single
shared contract so results are comparable across generator versions
without re-deriving what "good" means each time. Every gate below cites
the real measurement it's calibrated against; none are aspirational
round numbers picked without justification.

## VALIDITY

| metric | how computed | pass gate | rationale |
|---|---|---|---|
| structural validity rate | `engine.validity.check_validity` on the final (post-repair, if any) candidate graph | ≥ 60% | M5's own measured final rate is 71.8% (`benchmark_report.json`) — 60% is a floor BELOW M5's current production number, so a new generator that regresses below it should fail the gate, not just "look different." |
| connectivity rate | fraction with `largest_component_covers_all_nodes == True` | ≥ 65% | M5 measured connectivity == validity (359/359 valid candidates are exactly the 359 connected ones, `benchmark_failure_analysis.json`) — since Phase 3 proved connectivity is the SOLE bottleneck, this gate should track validity closely; a generator that's connected but not valid would be a genuinely new (currently unobserved) failure mode worth flagging, not silently averaged away. |
| renderer validity rate | fraction of valid candidates that `engine.render.render_generated_kolam_svg/png` completes without raising | ≥ 99% | Rendering is pure deterministic geometry (`engine.render`'s own module docstring) — a valid graph should essentially never fail to render; a lower rate indicates a renderer/representation bug, not a generation-quality issue, and should be investigated separately from validity tuning. |

## NOVELTY

| metric | how computed | pass gate | rationale |
|---|---|---|---|
| exact duplicate rate | `engine.novelty.novelty_report`'s `exact_topological_duplicate_rate` | ≤ 1% | M5 measured 0.0% (`benchmark_report.json`) — 1% leaves slack for a differently-tuned generator while still requiring near-zero literal copying. |
| near-duplicate rate | `near_duplicate_rate` (threshold 0.9 coordinate-similarity, same convention `engine.novelty.novelty_report` already uses) | ≤ 5% | M5 measured 0.0% — 5% is a conservative ceiling, not a target to aim for. |
| D4-canonical uniqueness | `unique_rate` (fraction of candidates with distinct `graph_fingerprint`) | ≥ 95% | M5 measured 100.0% (359/359) — a small allowance (95%) accounts for legitimately small/simple candidates that may coincide by chance, without accepting a generator that repeats itself often. |
| distance from training set | `experiments/m6_generation/novelty.py`'s `nearest_training_novelty` combined_distance (topology + degree + symmetry + geometric terms, each in [0,1]) | mean ≥ 0.15, report full distribution | No prior real measurement exists for this metric on M5 (it's an M6-specific tool) — the gate is deliberately loose (report-and-monitor, not a hard pass/fail) until a baseline run establishes what "normal" looks like for a real generator; TIGHTENING this gate without that baseline would be inventing a threshold, which this document's own principle forbids. |

## FIDELITY (distributional match to real corpus — `structural_dataset_report.json` is the reference)

| metric | how computed | pass gate | rationale |
|---|---|---|---|
| degree distribution distance | e.g. Wasserstein or simple L1 histogram distance between candidate-batch and real-corpus degree distributions (`B_node_degree.distribution`) | report, no hard gate yet | Real data has essentially ALL nodes at degree 2 or 4 (`percentiles: p5=2, p25=4, p50=4, p75=4, p95=4`) — an extremely narrow, near-bimodal distribution. A hard gate here risks over-fitting a generator to exactly reproduce degree-2/4-only structure at the cost of legitimate diversity; report the distance, let a human judge whether a large deviation is a bug or an intentional design choice (e.g. exploring degree-6 motifs). |
| multiplicity distribution distance | fraction at multiplicity 1 vs. 2 vs. 3+, compared to `A_edge_multiplicity` (74.55% / 25.45% / 0.00% in real data) | multiplicity-3+ fraction MUST be 0% (hard, ties to M5_1_CONSTRAINT_SPEC.md Section 1.1) | This is the ONE fidelity metric promoted to a HARD gate, because Phase 2's evidence is unambiguous (0/500 real patterns ever exceed multiplicity 2) and Phase 3 found the current violation (97.5% of M5's repaired-valid candidates) is a fixable code artifact, not an inherent tradeoff. |
| edge-length distribution | compare to `D_edge_locality` (p95=2.0, mean=1.575 lattice units) | report, no hard gate yet | M5's motifs are already induced from real local windows (radius 1), structurally bounding edge length — this metric matters more for a free-form generator (M6) than for M5, and no M6 candidate has reached validity yet to measure against (V1: 0/100 valid). Revisit once M6 V2 produces valid candidates to measure. |
| symmetry distribution | compare mean/median coverage to `F_symmetry` (mean 19.7%) | report, no hard gate | Per M5_1_CONSTRAINT_SPEC.md Section 2.1, real data itself is NOT symmetry-biased — this metric exists to catch a generator that's ACCIDENTALLY over- or under-symmetric relative to real data, not to enforce a target. |
| complexity distribution | compare mean nodes/edges to `G_structural_complexity` (mean 256.7 nodes, 363.9 distinct edges) | report, no hard gate | Complexity is legitimately layout-dependent (M5 operates on real patterns' own layouts; a free-form generator like M6 may target a deliberately smaller/simpler `size` preset) — a fixed numeric gate would penalize intentional scale choices. |

## QUALITY

| metric | how computed | pass gate | rationale |
|---|---|---|---|
| recognizer verification (recall) | `experiments/m6_generation/verify.py`'s `verify_with_recognizer` against the FROZEN M4.2 detector, ground truth = the generator's own exact dot positions | ≥ 90% recall | M5's own smoke test (a single 10x10-lattice candidate) measured 100/100 classical-detector recall on a clean rendered image (session verification, not yet a full benchmark) — 90% leaves slack for detector noise on more complex real candidates without accepting a generator/renderer combination the frozen verifier can barely read. |
| rendering success rate | fraction of valid candidates that produce a non-empty SVG/PNG without exception | ≥ 99% | Same reasoning as the VALIDITY section's renderer-validity-rate gate — restated here because "renders" and "renders CORRECTLY" are formally the same check in this pipeline (`engine.render` never partially succeeds). |
| visual sanity checks | MANUAL, human spot-check of a sample (e.g. 10-20 rendered SVGs) per benchmark run | qualitative, not a numeric gate | Some failure modes (e.g. a valid-but-visually-degenerate structure — all edges collinear, a single long line back-and-forth) pass every automated gate above while being an obviously bad kolam. No automated metric in this spec currently catches this; flagged as a known gap, not silently assumed to be covered. |

## PERFORMANCE

| metric | how computed | pass gate | rationale |
|---|---|---|---|
| latency (mean) | wall-clock per candidate, `time.time()` around the full generate→validate→repair pipeline | ≤ 15s/candidate | M5 measured 11.4s/candidate mean (`benchmark_report.json`) — 15s leaves ~30% headroom; a generator far slower than this (e.g. M6 V1's search-free path was actually FASTER at 0.08s/candidate but 0% valid — speed alone is not the goal) should be flagged, not silently accepted just because it's "fast." |
| throughput | candidates/hour at the measured mean latency | report (derived from latency, not independently gated) | Directly implied by the latency gate; no separate threshold needed. |
| memory | peak RSS during a benchmark run (e.g. via `resource.getrusage` or an external profiler) | report, no hard gate yet | No prior measurement exists in this repository for either M5 or M6 — establish a baseline before setting a threshold, per this document's own stated principle against inventing unmeasured targets. |

## How to run this benchmark against a candidate generator

1. Generate ≥100 candidates (matching M5's/M6's own benchmark scale
   convention) using the SAME seed range convention already established
   (`run_benchmark.py`'s `seed = i`, or a documented disjoint range for
   a new generator, avoiding accidental seed collisions across
   generator versions being compared).
2. Compute every VALIDITY/NOVELTY/FIDELITY/QUALITY/PERFORMANCE metric
   above from the SAME batch of candidates (not separately-generated
   samples per metric — keeps every reported number about the same
   underlying run).
3. Write a JSON report with the same top-level shape
   `run_benchmark.py`/`run_generation_benchmark.py` already use
   (`{"summary": {...}, "records": [...]}`) so future tooling (e.g.
   `experiments/m5_generation/compare_all.py`) can read any generator's
   report interchangeably.
4. Report EVERY metric, including ones with no hard gate yet — this
   spec's "report, no hard gate" entries exist specifically so future
   runs build up the baseline evidence needed to eventually set an
   evidence-backed gate, the same way M5.1's Phase 2/3 measurements now
   justify Section 1.1's hard multiplicity gate.
