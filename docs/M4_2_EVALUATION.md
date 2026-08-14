# M4.2 Evaluation

**Result: mixed. Massive, decisive improvement on the exact problem
M4.1.1/M4.1.2 diagnosed (target-resolution/representation). No
improvement - arguably worse - on the problem that actually matters for
production (real-photo generalization). `detector=classical` remains
the default; ML stays experimental, per the pre-committed decision rule
below, which was fixed BEFORE these numbers were known
(`docs/M4_2_EVALUATION.md`'s earlier placeholder version, same file,
same git history).**

## Methodology

`experiments/m4_2/evaluate_m4_2.py` ran both the classical detector
(`engine.image_io.detect_lattice`, unmodified) and the M4.2 ML detector
(`experiments/m4_2/ml_lattice_detector.py`, peak-detection parameters
selected on the VALIDATION set only - see
`experiments/m4_2/results/peak_sweep.json`, never touched during
selection: threshold=0.6, min_distance=2.0 cells) on identical inputs
across the same four populations M4.1 used.

## Decision rule (fixed before results were known)

ML becomes the default ONLY if ALL of: (1) ML recall > classical recall
on the held-out test set, (2) ML F1 > classical F1 on the held-out test
set, (3) ML no-dot false-positive rate <= classical's. See git history
of this file for the pre-registered version.

## Results

| Metric | Classical | ML |
|---|---|---|
| Synthetic val recall | 0.1084 | **0.9990** |
| Synthetic val precision | 0.9961 | **0.9995** |
| Synthetic val F1 | 0.1114 | **0.9993** |
| Synthetic test (held-out) recall | 0.1998 | **0.9979** |
| Synthetic test (held-out) precision | **0.9998** | 0.9985 |
| Synthetic test (held-out) F1 | 0.1998 | **0.9982** |
| Localization error (px, 6px tolerance) | **0.77** | 2.74 |
| Inference latency (ms) | **19.1** | 125.2 |
| No-dot FP rate (18 real photos) | **0.333** | 1.000 |
| Real in-scope detections vs. human estimate | see below | see below |

Real in-scope photos (file: classical / ML / human estimate):
- `kolam2_tshrinivasan.jpg`: 1 / 58 / ~25-30
- `kolam_attur1_infofarmer.jpg`: 12 / 297 / ~4 (unresolved discrepancy, see M4.1 notes)
- `kolam_naduveetu_meenakshisundaram.jpg`: 0 / 563 / ~100-150
- `muggu_kollam_sirensongs.jpg`: 4 / 151 / ~20-30

Full machine-readable results: `experiments/m4_2/results/evaluate_m4_2.json`.

## Interpretation - read both halves, not just the winning one

### The synthetic numbers are real, but the comparison is confounded - same issue M4.1 already documented

Classical's recall on `experiments/m4_2/data/{val,test}` (0.11-0.20) is
dramatically lower than its own well-established, repeatedly-verified
performance on gentler synthetic degradation (1.0/0.9995, unchanged
since session 10-11, re-confirmed every session since). Despite
`degrade_v3` being deliberately recalibrated against the REAL photo
corpus's measured brightness/contrast distribution (`docs/M4_2_MODEL.md`
- generated median gray-mean 124.6 vs. real median 121.4, a close
match), **classical's recall still collapses on this set** - the same
confound M4.1's Session 13 Section 3 documented for `degrade_v2`
("even the classical detector's recall collapsed on that set"). This
session did not have scope to further diagnose exactly which
degradation axis (translation, blur, vignette, or an interaction)
causes this; it is reported as an observed, reproducible fact, not
explained away. **This means the synthetic-test recall/F1 comparison
above is NOT a clean apples-to-apples measurement of "ML vs. classical
at their best" - it partly reflects "ML trained-for-this-exact-hard-
distribution vs. classical never adapted to it."** The fairer, cleaner
signal from this session is Section "Real in-scope" below, and the
model-architecture question specifically (Section "What M4.2 actually
proved").

### The real-photo numbers are decisive and not confounded

Real photographs were never touched by training or parameter selection
for EITHER detector. Here the result is unambiguous: ML fires on
**18/18 (100%)** of photos with no real dots at all - identical to
M4.1's own already-bad 18/18, no improvement at all on this axis - and
on real in-scope photos, over-detects by a wide and
inconsistent margin (58-563 detections against estimates of 4-150,
compare M4.1's more uniform ~44-54 across all real photos). **M4.2's
real-photo behavior is not better than M4.1's, and arguably worse in
its unpredictability** - M4.1 at least produced a suspiciously
CONSTANT output (a diagnosable "generic artifact" signature); M4.2's
output is highly variable but still wildly wrong in magnitude.

### What M4.2 actually proved

The specific, narrow question M4.1.1/M4.1.2 raised - "is 32×32 output
resolution fundamentally incapable of representing this dataset's dot
density, and would 128×128 fix that" - is answered with direct,
strong, structural evidence: **yes, and yes.** Validation/test set
recall on the SAME kind of degraded synthetic image jumped from M4.1's
~0.05-0.07 to M4.2's ~0.998-0.999, and localization error, while higher
than classical's, stays well within the 6px tolerance. This is not a
confound - it is a controlled, direct comparison of the identical model
family/training recipe/data-generation process, varied only in output
resolution and architecture depth (M4.1: 32×32, encoder-only;
M4.2: 128×128, encoder-decoder). **The target-resolution fix worked
exactly as the diagnostic predicted it would, in the domain it was
tested in.**

**What M4.2 did NOT prove**: that this fix transfers to real
photographs. The real-photo domain gap M4.1 identified is fully intact
in M4.2, unimproved. Fixing the representation problem was necessary
but not sufficient - synthetic-to-real transfer is evidently a
SEPARATE, still-unsolved problem, not a downstream consequence of the
resolution issue this session addressed.

## Decision

Per the pre-committed rule: condition 3 (no-dot FP rate) fails
(1.0 > 0.333) - **`recommend_ml_as_default = False`** (computed
directly by `evaluate_m4_2.py`, not asserted by hand).
`detector=classical` remains the production default. The ML detector
remains available behind `detector=ml`/`detector=compare` for
continued experimentation, exactly as the task's own closing
instruction anticipates for a "loses again" outcome.

## Recommendation for next steps

1. **Do not tune the current gap away with more synthetic epochs** -
   the gap is a domain-transfer problem (synthetic-trained,
   real-evaluated), not a fit problem (M4.2 already fits its synthetic
   target excellently).
2. **The `degrade_v3` classical-recall-collapse confound deserves its
   own targeted diagnostic** (mirroring M4.1.1's methodology) before
   any future session trusts synthetic-only metrics from this
   generator again.
3. **Any future attempt at real-photo transfer should train on at
   least some real-photo-derived data** (e.g., domain adaptation, or
   augmentations derived from actual real-photo statistics beyond just
   matching gray mean/std, which this session showed is insufficient)
   rather than assuming a purely-synthetic pipeline will close the gap
   through better synthetic tuning alone.
