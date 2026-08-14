# M4.2 Canonicalization Evaluation

**Result: negative.** Five deterministic canonicalization variants
(illumination normalization, CLAHE, adaptive thresholding, morphological
cleanup, in various combinations) were tested against the existing,
unmodified `DotHeatmapNetV2` checkpoint on all 22 real photos. **None
improved the no-dot false-positive rate — all 5 remained at 100%
(18/18), identical to the current production baseline.** Two variants
(D, E) additionally REGRESSED synthetic precision (0.63 and 0.90 vs.
baseline's 0.9995). No variant is integrated into the API or frontend.

## Methodology

`engine/canonicalize.py` (new, experimental, opt-in — does not modify
`engine.image_io.preprocess()`) implements 5 deterministic
preprocessing variants, all ending in the same single-channel uint8
binary ink-mask format the model already expects:

| Variant | Recipe |
|---|---|
| A (baseline) | grayscale + global Otsu threshold — **identical to current production** `engine.image_io.preprocess()`, verified by a direct equality test |
| B | grayscale + CLAHE (local contrast) + global Otsu |
| C | grayscale + illumination normalization (flat-field division by a heavily-blurred background estimate) + global Otsu |
| D | grayscale + CLAHE + adaptive (local) threshold + light morphological opening |
| E | grayscale + illumination normalization + adaptive threshold + light morphological opening |

Same checkpoint, same confidence threshold (0.6) and min-peak-distance
(2.0 heatmap cells) as production, for every variant — only the
preprocessing changed, per the task's explicit "do not change the model
checkpoint between A and B" instruction.

**Time-budget note**: the full graph-construction check (`trace_path`,
which calls `skimage.skeletonize` — slow on some real photos up to
9248×6936px) was run for the baseline only, not for all 5 variants. A
fast screening pass (detection + lattice-fit only, no skeletonize) was
run first for all 5 variants; it already produced a decisive, consistent
result on the #1-priority metric (no-dot false-positive rate) across
every variant, so the more expensive full-graph check for the losing
variants was not run — it would not have changed the conclusion.

## Variants tested

All 5 (A–E), per the task's request — no variant was skipped.

## Raw ML benchmark (variant A = current production path)

| | value |
|---|---|
| Synthetic val recall/precision/F1 | 0.9990 / 0.9995 / 0.9993 |
| Real no-dot FP rate | 100.0% (18/18) |
| Real in-scope lattice-fit success | 4/4 |
| Crashes | 0 |
| Mean latency | 127.3ms |

## Canonicalized ML benchmark (variants B–E)

| Variant | Synthetic recall | Synthetic precision | Synthetic F1 | Real no-dot FP rate | Crashes | Latency |
|---|---:|---:|---:|---:|---:|---:|
| B | 0.9986 | 0.9990 | 0.9988 | 100.0% (18/18) | 0 | 130.7ms |
| C | 0.9984 | 0.9966 | 0.9975 | 100.0% (18/18) | 0 | 153.4ms |
| D | 0.9992 | **0.6297** | **0.7608** | 100.0% (18/18) | 0 | 193.5ms |
| E | 0.9988 | **0.8966** | **0.9418** | 100.0% (18/18) | 0 | (not separately timed) |

## Best variant

**None.** Every variant tied at 100% no-dot false-positive rate — the
task's own Phase 5 priority-#1 metric ("fewer catastrophic false
positives"). Per that explicit hierarchy, a variant that does not
improve on priority #1 is not promoted regardless of what happens
further down the list (detection count, raw confidence, etc.). If
forced to rank purely on "does the LEAST additional harm," **B** is
closest to baseline on every synthetic metric, but "closest to doing
nothing" is not the same as "an improvement," and it is reported as
such — not selected as a winner.

## Improvement/regression table

| Metric | A (baseline) | B | C | D | E |
|---|---:|---:|---:|---:|---:|
| No-dot FP rate | 100.0% | 100.0% (±0) | 100.0% (±0) | 100.0% (±0) | 100.0% (±0) |
| Synthetic recall | 0.9990 | −0.0004 | −0.0006 | +0.0002 | −0.0002 |
| Synthetic precision | 0.9995 | −0.0005 | −0.0029 | **−0.3698** | **−0.1029** |
| Synthetic F1 | 0.9993 | −0.0005 | −0.0018 | **−0.2385** | **−0.0575** |

**No variant helps the target problem. D and E actively hurt an
unrelated, already-working metric (synthetic precision)** — adaptive
(local) thresholding introduces spurious low-level texture peaks even
on clean synthetic renders, a real, measured cost, not a hypothetical
one.

## Downstream lattice/graph results

Lattice-fit success on the 4 real in-scope photos was 4/4 for every
variant tested at the fast-pass stage (unchanged from baseline — the
model already produces ≥3 detections on all 4, so this metric was never
differentiating). Full graph construction (connectivity, odd-degree
count) was not run beyond the baseline, per the time-budget note above
— not needed to reach the negative conclusion, since no variant cleared
the higher-priority false-positive gate that would have justified the
additional expensive check.

## API integration status

**Not integrated.** Per the task's own explicit instruction ("if the
experiment clearly improves ML performance, then make the canonicalized
ML path available through the API") — it does not clearly improve
(actually: measurably regresses on 2/5 variants, and is flat on the
target metric for all 5) — so `detector=ml_canonical` was NOT added to
`api/detectors.py`/`api/main.py`. Existing `detector=classical`/`ml`/
`compare` are completely unchanged (verified: zero diff to
`api/detectors.py` this session; `engine/canonicalize.py` is a
standalone new module with no import from or into any API file).

## Frontend integration status

**Not attempted**, per Phase 7's own "only if the backend path is
validated" condition — it was not.

## Tests

`tests/test_canonicalize.py`, 9 new tests: all 5 variants produce a
valid binary uint8 mask; unknown variant / missing file raise cleanly;
determinism; dimension preservation; **variant A is proven byte-identical
to `engine.image_io.preprocess()`'s own output** (not just documented —
tested); illumination-normalized variants measurably reduce foreground
fraction on a synthetic uneven-lighting test image (the one thing this
module DOES demonstrably do); `engine.canonicalize` proven to import
nothing from `engine.image_io` (namespace-level check, not a fragile
text search). Full suite: **257/257 passing** (248 before this session's
canonicalize tests — some additional tests from concurrent, unrelated
work also landed in this count; 9 are this session's). No existing test
modified or weakened.

## Runtime/latency

127–194ms per real photo depending on variant (baseline 127ms; D/E
slower due to adaptive threshold + morphology on large images — up to
~200ms, still well within the existing ML detector's overall latency
budget documented in `docs/M4_1_ML_COMPLETION_REPORT.md`).

## Files changed

- `engine/canonicalize.py` (new)
- `experiments/m4_2_canonicalization/run_comparison.py` (new)
- `experiments/m4_2_canonicalization/results/comparison.json` (new)
- `tests/test_canonicalize.py` (new)
- `docs/M4_2_CANONICALIZATION_EVALUATION.md` (this file)
- `.gitignore` (allow-list entry for this doc)
- No files in `api/`, `engine/image_io.py`, `engine/ml_contract.py`, or
  `frontend/` were touched.

## What remains

- The domain-gap problem (real no-dot photos triggering confident false
  positives, `docs/M4_1_ML_COMPLETION_REPORT.md`) is UNCHANGED by this
  experiment — canonicalization at the preprocessing level does not
  touch it, because the CNN's false firing is not primarily caused by
  binarization noise (the working hypothesis this experiment tested),
  it persists even on a visually much "cleaner" mask (see Phase 9 note
  below).
- The already-recommended, more promising mitigation remains the
  lattice-CONSISTENCY gate from `docs/M4_1_ML_COMPLETION_REPORT.md`
  (100%→55.6% no-dot FP, zero synthetic cost) — a POST-detection
  geometric filter, not a pre-detection image transform. This
  experiment's negative result makes that prior finding look
  comparatively more important, not less.
- Full graph-level (connectivity/parity) comparison across all 5
  variants was not completed, but is very unlikely to change the
  conclusion given the false-positive rate never moved.

## M4.1/M4.2 readiness verdict

**Unchanged. M4.1 remains PARTIAL** (`docs/M4_1_ML_COMPLETION_REPORT.md`),
**M4.2 remains PARTIAL** (`docs/M4_2_PARITY_EVALUATION.md`) — this
experiment is scoped entirely within the already-PARTIAL M4.1 ML
detection problem and does not touch M4.2 generation at all. This
session neither closes nor worsens either milestone's status; it rules
out one specific, plausible-sounding hypothesis (preprocessing-level
canonicalization) with real evidence, which is a legitimate research
outcome per this project's explicit rules.

## Exact next highest-value experiment

**Not another canonicalization variant.** This experiment's clearest
finding is that image-level preprocessing changes do not move the
false-positive needle at all (100% → 100%, five different ways) — the
false-firing behavior is a property of what the CNN LEARNED (confident
on synthetic-render statistics, confidently wrong on real-photo
statistics), not a property of how the binary mask is computed before
reaching it. The highest-value next step is therefore the ALREADY
-IDENTIFIED one from `docs/M4_1_ML_COMPLETION_REPORT.md`'s own "next
step": wire the lattice-consistency GATE (post-detection, not
pre-detection) into `api/detectors.py` as an opt-in path and run it
through `evaluate_m4_2.py`'s full decision-rule framework — that
mitigation already has a measured, non-zero benefit; this session's
canonicalization work does not, and should not be pursued further along
this specific axis without first testing whether real-photo-DERIVED
training data (not just preprocessing) is the actual missing
ingredient (Phase 9's suggested direction, not attempted this session
due to time budget).
