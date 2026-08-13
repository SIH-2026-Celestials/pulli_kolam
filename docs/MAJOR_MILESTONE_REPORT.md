# PULLI Major Milestone Report - M4.1 / M4.2 / M5

**Written honestly, per this campaign's own explicit rule: a milestone
is not complete because code exists for it.** This report synthesizes
what is ACTUALLY implemented, tested, and measured across three
requested milestones, scoped down deliberately (confirmed with the user
before starting) rather than shallowly touching all three.

## 1. Baseline before this session

- Full test suite: **171 passed** (`python -m pytest -q`).
- Real-photo baseline (`validate_real_photos.py`, 22 photos): 13
  `NO_DOT_DETECTION`, 3 `INSUFFICIENT_LATTICE_POINTS`, 6 `SUCCESS`, 0
  crashes (the previously-documented `trace_path` `IndexError` on
  `kolam_india12_mckaysavage.jpg` was already gated in Session 17 - see
  `PROJECT_STATE.md` Session 17).
- M4.1 (ML investigation): already complete as of Session 16, with a
  documented mixed result (`docs/M4_2_EVALUATION.md`) - classical
  detector remains production default.
- Generation: M3.7's `engine.novel_generation` existed (`generate_novel_kolam`,
  `select_novel_placements`) with a known, documented limitation (0/5
  valid candidates at the time, no connectivity-seeking strategy).

## 2. M4.1 - ML investigation

**Not re-run.** Confirmed with the user before starting: re-running
M4.1-A through M4.1-F would either duplicate sessions 13-16's already-
executed, evidenced experiments, or require new real-photo ground-truth
labels this repository does not have. `docs/M4_1_ML_INVESTIGATION.md`
maps every phase of the standard M4.1 task structure onto where its
answer already lives in this repo's history, and states plainly what
was never investigated (a true hybrid CV+ML fusion detector, a
segmentation-based detector) rather than implying those were tried.

**Status: COMPLETE (cited).**

## 3. ML vs. classical results (cited, not re-measured)

From `docs/M4_2_EVALUATION.md` (Session 16):

| Metric | Classical | ML (128×128, M4.2 detector) |
|---|---|---|
| Synthetic test recall | 0.1998 | 0.9979 |
| Synthetic test F1 | 0.1998 | 0.9982 |
| Localization error (px) | 0.77 | 2.74 |
| Real no-dot false-positive rate (18 photos) | 0.333 | 1.000 |
| Inference latency (ms) | 19.1 | 125.2 |

Decision (pre-committed rule, computed programmatically, not asserted):
`recommend_ml_as_default = False`. `detector=classical` remains
production default.

## 4. Selected architecture

Unchanged: classical CV (`engine.image_io.detect_lattice`/`trace_path`)
for production dot detection. The 128×128 ML detector
(`experiments/m4_2/model.py`) remains available behind `detector=ml`/
`detector=compare` in `api/` for continued experimentation.

## 5. M4.2 - generation results (this session's real, new work)

**Status: PARTIAL** - infrastructure complete and tested; the
generator's own output validity does not yet pass the gate.

- `engine/generation_api.py`, `engine/novelty.py`, `engine/render.py`
  built, tested (29 new tests), and exercised end-to-end.
- Benchmark (`experiments/m4_2_generation/run_benchmark.py`): 120 real
  candidates, deterministic config, full results in
  `experiments/m4_2_generation/results/benchmark.json`.
- **Validity: 0/120 (0.0%).** A real, measured negative result - not
  new (M3.7 already found 0/5), now confirmed at a much larger,
  systematically-varied sample. Root cause unchanged from M3.7:
  `select_novel_placements` has no global connectivity objective.
- **Multiplicity: exact, 0/120 violations**, checked directly against
  each candidate's real graph.
- Full interpretation: `docs/M4_2_GENERATION.md`.

## 6. Novelty results

From the same 120-candidate benchmark (`engine.novelty.novelty_report`):

| Metric | Value |
|---|---|
| Unique among candidates themselves | 52/120 (43.3%) |
| Exact topological duplicate of any source (layout-independent) | 0/120 (0.0%) |
| Exact coordinate duplicate (60 layout-comparable pairs) | 0/60 (0.0%) |
| Near-duplicate (similarity ≥ 0.9) | 0/60 (0.0%) |

**This generator does not produce copies of its source patterns** - a
genuinely positive, measured finding, reported alongside the validity
negative rather than in place of it.

## 7. M5 - structural grammar results

**Status: NOT STARTED**, by deliberate scope decision (confirmed with
the user). `docs/M5_STRUCTURAL_GRAMMAR.md` documents what already exists
in this codebase that M5 would build on (motif primitives, symmetry
analysis, MDL cost accounting, the new graph fingerprint), what M5-A
through M5-E would each actually require, and a recommended build order
for a future session. No grammar object, parser, grammar-based
generator, or search mechanism exists.

## 8. Validity results (consolidated)

| Population | Valid | Total |
|---|---|---|
| M4.2 generation benchmark, this session | 0 | 120 |
| M3.7 novel generation, session history | 0 | 5 |
| Reconstruction (`engine.reconstruction.reconstruct_kolam`) | always valid by construction (residual fallback) | n/a - different question, see `docs/RECONSTRUCTION.md` |

The distinction matters: reconstruction always succeeds because it can
fall back to copying real source residual edges; novel generation
(M3.7/M4.2) has no such fallback and inherits the full gap between what
a greedy, non-connectivity-aware motif library can cover and what a
complete valid structure needs.

## 9. Performance

- Generation benchmark: 120 candidates in 30.2s (mean 0.25s/candidate)
  - fast enough that connectivity-aware search (a likely next step,
  see Section 12) has real time budget to explore multiple candidates
  per request.
- Rendering: SVG generation is pure string formatting (sub-millisecond);
  PNG generation via PIL, no measured bottleneck at this session's
  pattern sizes (up to 500 dots).
- No profiling of large photographs / 24k+ trace points / `kolam109`-scale
  patterns was done this session - nothing in this session's new code
  touches that path (see Section 5 of `PROJECT_STATE.md`'s Session 18
  entry, "What was explicitly NOT done").

## 10. Tests

| Stage | Count |
|---|---|
| Before this session | 171 passed |
| After this session | **200 passed** |
| New this session | 29 (`tests/test_render.py` ×7, `tests/test_novelty.py` ×10, `tests/test_generation_api.py` ×12) |
| Regressions | 0 |

## 11. Known limitations

- **Generation validity (M4.2)**: 0/120 in this session's benchmark -
  the single most important open item, see Section 12.
- **M5 not started** - see `docs/M5_STRUCTURAL_GRAMMAR.md`.
- **Real-photo ML domain gap (M4.1, unchanged from Session 16)**: no-dot
  false-positive rate still 100% for the ML detector; classical remains
  default.
- **`degrade_v3` classical-recall-collapse confound (M4.1, unchanged)**:
  still unresolved, flagged in `docs/M4_2_EVALUATION.md`.
- **`GenerationConstraints`'s `symmetry`/`complexity`/`stroke_count`
  fields are not real constraints** - no search loop exists yet to
  satisfy them; this is explicitly M5-E's job, not started.
- **No frontend/API surface for the new M4.2 generation code** - by
  deliberate scope decision (the task's own instruction against
  spending the majority of effort on frontend polish).

## 12. Next highest-value bottleneck

**A connectivity-seeking placement strategy for `select_novel_placements`.**
This is the single change that would move M4.2 from PARTIAL to COMPLETE,
and is a PREREQUISITE for M5-D/M5-E to produce anything usable, since
both would inherit the same 0%-valid result if built on top of the
current placement algorithm unchanged. Concretely: `select_novel_placements`
currently scores each candidate placement in isolation
(local growth + parity improvement, `_novel_score`) with no global view
of whether the result ends up as one connected component; a next
session should investigate either (a) a connectivity-aware scoring term
(e.g. reward placements that bridge currently-separate components), or
(b) a post-placement bridging pass that adds minimal extra structure to
merge components before the Eulerian check - the second option risks
looking like "repairing an invalid graph," so it would need to be
implemented as a distinct, clearly-labeled step (e.g. a
`generate_kolam_candidate(..., allow_bridging=True)` opt-in that reports
what it added), never a silent change to `generate_kolam`'s existing
"never repair" contract.
