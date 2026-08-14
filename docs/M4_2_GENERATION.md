# M4.2 Generation - Constraint API, Novelty Measurement, Rendering

**Result: the generation pipeline is real, tested, deterministic, and
genuinely novel structurally - but not yet valid at scale.** 0/120
benchmarked candidates were fully valid single-stroke structures. This
is the same limitation `docs/NOVEL_GENERATION.md` (M3.7) already
reported at n=5 ("no connectivity-seeking strategy"), now confirmed at
n=120 across a much wider sweep of libraries, layouts, and multiplicity
caps - not a new problem, but a more thoroughly measured one.

## What was built this session

- **`engine/generation_api.py`** (M4.2-A): a single constraint-based
  entry point, `generate_kolam_candidate(GenerationConstraints)`. Wraps
  `engine.novel_generation.select_novel_placements` +
  `engine.generation.generate_kolam` (both unmodified) - it does not
  reimplement placement or validity logic. Supports: explicit or
  `(width, height)`-grid lattice, a motif library built from one or more
  source patterns (`motif_library_from_sources` - the "richer library
  from multiple patterns" extension `docs/NOVEL_GENERATION.md`'s Known
  Limitations named as not attempted), a flat multiplicity cap, and a
  `require_single_stroke` flag that turns `GeneratedKolam.is_valid` into
  an explicit `satisfied`/`reasons_unsatisfied` report rather than a
  silent pass/fail.
  **Not supported** (documented gap, not hidden): `symmetry`,
  `complexity`, and `stroke count` as hard, SEARCHED-FOR constraints -
  there is no retry/search loop. That is M5-E's scope ("structural
  search"), not started.
- **`engine/novelty.py`** (M4.2-D): `graph_fingerprint()` - a
  translation- and D4-symmetry-canonical fingerprint of a graph's edge
  multiset (same 8-transform canonicalization idea
  `engine.symmetry.canonical_motif` already uses for local motif
  windows, applied to a whole graph). `novelty_report()` measures, over
  a batch of candidates against a pool of source patterns: uniqueness
  among candidates themselves, exact topological duplication (layout-
  independent), exact coordinate duplication and near-duplication (only
  where a candidate and a source share a dot layout - reported as
  "not applicable" rather than fabricated when they don't, matching
  `engine.novel_generation.duplicates_source`'s existing convention).
- **`engine/render.py`** (M4.2-E): deterministic SVG and PNG rendering.
  `GeneratedKolam` → straight-line-segment stroke through `dot_trace`
  (does not reconstruct loop-around geometry - same documented scope
  limit as `docs/GENERATION.md`'s own trace reconstruction). `KolamPattern`
  → the pattern's ACTUAL recorded `trace_points`, real geometry, not an
  approximation. An invalid candidate (`is_valid=False`, which already
  means `dot_trace=None`) is rendered dots-only and explicitly labeled
  `INVALID` - never a picture that could be mistaken for a successful
  result. Both renderers share one layout function, so SVG and PNG
  output always agree on placement; same input always produces the same
  output (verified by test, `tests/test_render.py`).
- **`experiments/m4_2_generation/run_benchmark.py`**: generates 120
  candidates from a fixed, fully-enumerated, non-random grid - 10 motif
  libraries (5 single-source + 2 single-source-kolam29 + 3 multi-source
  pooled) × 6 dot layouts (3 synthetic rectangular grids: 6×6, 10×10,
  14×14; 3 unseen real layouts: `kolam19#15`, `kolam19#20`, `kolam29#3`
  - none of these three patterns' own motifs are used in any library
  placed on them) × 2 multiplicity caps (1, 2). Deterministic (the
  underlying placement algorithm has no RNG) - re-running reproduces the
  same result. Full output: `experiments/m4_2_generation/results/benchmark.json`.

## Measured results (120 candidates, real run, no numbers invented)

| metric | value |
|---|---|
| Validity rate | **0/120 (0.0000)** |
| Multiplicity violations | **0/120** - the per-candidate `max_multiplicity` cap was never exceeded, checked directly against each candidate's actual graph, not assumed from the generator's internal guard |
| Symmetry coverage (D4, `engine.symmetry.analyze_symmetry`) | min 0.042, mean 0.368, max 0.774 |
| Placements per candidate | min 1, mean 4.05, max 15 |
| Unique candidates (distinct D4+translation-canonical fingerprints) | 52/120 (**43.3%**) - many (library, layout, multiplicity) combinations converge on the same shape, most commonly 3 fingerprints appearing 6 times each |
| Exact topological duplicate of ANY source pattern (layout-independent) | **0/120 (0.0%)** |
| Exact coordinate duplicate of a source pattern (only where layouts match - 60 comparable pairs existed) | **0/60 (0.0%)** |
| Near-duplicate (similarity ≥ 0.9, coordinate-comparable pairs only) | **0/60 (0.0%)** |
| Total wall-clock time, 120 candidates | 30.2s (mean 0.25s/candidate) |

By layout (validity is 0 everywhere, so this table reports the more
informative structural metrics instead):

| layout | n | mean placements | mean symmetry coverage |
|---|---|---|---|
| synthetic_grid_6x6 | 20 | 2.60 | 0.237 |
| synthetic_grid_10x10 | 20 | 2.90 | 0.288 |
| synthetic_grid_14x14 | 20 | 3.15 | 0.328 |
| real_layout_kolam19_15 | 20 | 5.25 | 0.455 |
| real_layout_kolam19_20 | 20 | 4.95 | 0.381 |
| real_layout_kolam29_3 | 20 | 5.45 | 0.516 |

Real (non-uniform-grid) unseen layouts consistently get more placements
and higher symmetry coverage than synthetic rectangular grids of
comparable size - real kolam dot layouts apparently offer more
motif-compatible local neighborhoods than a plain rectangular grid does,
a real (if modest, n=120) finding, not asserted from theory.

## Interpretation

**Novelty: genuinely good news, honestly measured.** Zero candidates,
across 120 tries, were an exact structural copy (topological OR
coordinate) of any source pattern used, and zero were even a
near-duplicate. This directly answers M4.2-D's question ("a generator
producing only copies is not successful") - this generator does not
produce copies. 43.3% of candidates were unique from EACH OTHER too,
meaning the same underlying shape does recur across different
(library, layout, multiplicity) inputs about half the time - expected,
since several single-pattern libraries share overlapping local
geometry, not a bug.

**Validity: still the real, unresolved gap - now measured at 24× the
previous sample size.** `docs/NOVEL_GENERATION.md` already identified
the root cause: `select_novel_placements` scores local growth/parity
greedily with no global connectivity objective, so candidates
fragment into many small components instead of one connected structure.
This benchmark did not change that algorithm and does not claim to -
it exists to measure the CURRENT algorithm's behavior honestly at
scale, which it does: 0/120, not "mostly valid" or "usually connected."
**The generator is not fixed by this session; it is now more precisely
characterized.**

**Multiplicity and rendering are unambiguously correct.** Every one of
120 candidates respected its multiplicity cap exactly (checked, not
assumed), and every candidate - valid or not - rendered to a real,
correctly-placed SVG/PNG with an honest INVALID label where warranted.
These are the parts of M4.2's gate that this session actually closes
completely.

## M4.2 gate - partial

Checking against this task's own M4.2 GATE:

| requirement | status |
|---|---|
| generation API exists | ✅ `engine/generation_api.py` |
| generated patterns are structurally valid | ❌ 0/120 in this benchmark (a real, measured negative - not a missing feature, an algorithmic limitation already known since M3.7) |
| multiplicity is exact | ✅ verified per-candidate, 0 violations |
| novelty is measurable | ✅ `engine/novelty.py`, real numbers above |
| rendering works | ✅ `engine/render.py`, tested, deterministic |
| tests pass | ✅ 29 new tests (`tests/test_render.py`, `tests/test_novelty.py`, `tests/test_generation_api.py`), 200/200 total suite passing |
| reproducible benchmark exists | ✅ `experiments/m4_2_generation/run_benchmark.py`, deterministic, config recorded in output JSON |

**Overall: M4.2 is INFRASTRUCTURE-COMPLETE, VALIDITY-INCOMPLETE.** Every
supporting piece (API, novelty, rendering, benchmark, tests) is real,
tested, and measured. The one gate item that genuinely fails
("generated patterns are structurally valid") fails because of a
pre-existing, already-documented algorithmic gap in
`select_novel_placements` (no connectivity-seeking strategy), not
because any of this session's new code is broken or untested.
Per this project's explicit rule against calling something complete
merely because code exists, **M4.2 is reported as PARTIAL, not
COMPLETE**, until placement selection gains some connectivity-aware
strategy - a well-scoped, already-diagnosed next task (see
`docs/MAJOR_MILESTONE_REPORT.md`'s "next bottleneck").
