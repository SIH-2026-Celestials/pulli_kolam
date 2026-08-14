# M4.1 ML Investigation - Status Summary

**This document does not report new experiments.** M4.1 (and its
follow-ons M4.1.1, M4.1.2, and M4.2) already ran to completion across
PROJECT_STATE.md sessions 13-16, with real, executed, reproducible
experiments and a pre-committed evaluation gate. This document exists
so a reader following the standard M4.1-A through M4.1-F task structure
can find the answer to each phase without re-running work that already
has evidence, and so nobody mistakes "this doc is short" for "this
milestone wasn't done."

## Where each phase's answer already lives

| Phase | Question | Answer | Evidence |
|---|---|---|---|
| M4.1-A Data audit | What data exists, is it enough for supervised training? | 22 real photos (18% in-scope), insufficient alone; 400+ CSV patterns exist and were used to generate synthetic training photos instead | `PROJECT_STATE.md` Session 12 (M4.0 Data Readiness), Session 16 §"Training data" |
| M4.1-B Classical baseline | Freeze deterministic CV as baseline | `engine.image_io.detect_lattice`/`trace_path`, unmodified throughout | `experiments/m4_1/classical_baseline.py`, `experiments/m4_1/results/classical_baseline.json` |
| M4.1-C Model investigation | Which architecture? | Started at 32×32 encoder-only CNN (M4.1) - lost to classical on every metric. Diagnosed root cause (M4.1.1): heatmap resolution too coarse to individuate dots at this dataset's density. Quantified fix (M4.1.2): 128×128 minimum. Built and trained (M4.2): 128×128 U-Net, 382,769 params | `experiments/m4_1/model.py`, `diagnostics/M4_1_HEATMAP_DIAGNOSIS.md`, `experiments/m4_1/diagnostics/TARGET_RESOLUTION_REPORT.md`, `experiments/m4_2/model.py`, `docs/M4_2_MODEL.md` |
| M4.1-D Synthetic training data | Render CSV geometry into synthetic photos | Done twice - `experiments/m4_1/generate_training_data.py` (`degrade_v2`) and `experiments/m4_2/generate_training_data.py` (`degrade_v3`, recalibrated against the full real-photo corpus's measured gray statistics) | `docs/M4_2_MODEL.md` §"Training data" |
| M4.1-E Training | Reproducible, source-disjoint, no leakage | Pattern-level disjoint train/val/test (verified via set-intersection assertion), fixed seed 42, checkpointing | `experiments/m4_2/train.py`, `experiments/m4_2/results/training_log.json` |
| M4.1-F ML evaluation | Classical vs. ML vs. hybrid, on dot detection AND downstream structure | Classical vs. ML (no separate hybrid variant was built - see "What was not investigated" below) across 4 populations: synthetic val, synthetic test, real in-scope, real no-dot | `docs/M4_2_EVALUATION.md` (full table + honest confound discussion) |

## The result (unchanged, still the current, evidenced answer)

- **Target-resolution problem: SOLVED.** M4.1's 32×32 architecture
  recovered only 5-28% of true dot identity as distinguishable target
  peaks at this dataset's real density (180-500+ dots/image) - a
  measured ceiling in the training target itself, not a training
  failure (`TARGET_RESOLUTION_REPORT.md`). M4.2's 128×128 U-Net fixed
  this directly: synthetic recall jumped from ~0.05-0.07 to 0.998-0.999
  on held-out synthetic data of the same kind.
- **Real-photo domain-gap problem: NOT SOLVED.** No-dot false-positive
  rate is unchanged at 18/18 (100%) between M4.1 and M4.2. Real
  in-scope over-detection is wildly inconsistent (58-563 detections
  against human estimates of 4-150). Fixing the resolution problem did
  not fix synthetic-to-real transfer - these are separable problems,
  and only one was solved.
- **Decision (pre-committed, not post-hoc)**: `docs/M4_2_EVALUATION.md`'s
  decision rule (ML must beat classical on test recall, F1, AND no-dot
  FP rate) was written before the evaluation ran. Condition 3 failed
  (1.0 > 0.333 no-dot FP rate) → `recommend_ml_as_default = False`.
  **`detector=classical` remains the production default** in `api/`
  and everywhere else in this codebase.

This satisfies the M4.1 GATE's option B exactly: *"ML is shown not to
beat classical CV, but provides a useful complementary component"* - the
128×128 architecture is a genuine, measured advance on the
representation problem, available behind `detector=ml`/`detector=compare`
for continued experimentation, without being promoted to default absent
evidence it should be.

## What was NOT investigated (real gaps, stated plainly)

- **Hybrid CV+ML (M4.1-C option D)**: not built. The closest existing
  analog is the API's `detector=compare` mode
  (`api/detectors.py`), which runs both and reports both - it does not
  fuse them into a single combined detector (e.g. ML proposes
  candidates, classical's lattice-fit / confidence gating filters them).
  This is a legitimate, still-open direction if real-photo transfer is
  revisited (see `docs/M4_2_EVALUATION.md`'s "Recommendation for next
  steps").
- **Segmentation-based detector (M4.1-C option C)**: not attempted.
  Heatmap regression (M4.1/M4.2) was chosen first as the smaller,
  more directly interpretable option; a segmentation-based approach was
  never ruled out for lack of merit, only not yet tried.
- **The `degrade_v3` classical-recall-collapse confound**: flagged in
  `docs/M4_2_EVALUATION.md`, still unresolved. Classical's own recall on
  M4.2's harsher synthetic test set (0.11-0.20) is far below its
  established gentle-degradation performance (1.0/0.9995) - this
  partly confounds the synthetic ML-vs-classical comparison and needs
  its own M4.1.1-style diagnostic before being trusted further.

## Why this session did not re-run M4.1

Re-running M4.1-A through M4.1-F would require either (a) new real-photo
ground-truth labels this repository does not have, which would not
change the evidenced conclusion above, or (b) a fresh synthetic
experiment answering a question sessions 13-16 didn't already answer -
and the one clear open question (real-photo domain transfer) needs
real-photo-derived training data or augmentation statistics, which is a
data-collection effort, not a re-run of the existing pipeline. Per this
project's explicit rule against fabricating results or re-litigating a
settled, evidenced conclusion, M4.1 is treated here as **COMPLETE**
(with a documented negative-to-mixed result), and this session's actual
new engineering effort went into M4.2 (see `docs/M4_2_GENERATION.md`).
