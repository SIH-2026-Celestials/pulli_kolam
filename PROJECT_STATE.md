# PULLI — Project State (handoff document)
**Read this first in any new session, before touching code.**
Last updated: session 15 (M4.1.2 target-resolution check). M4.1
(session 13) result unchanged: the learned lattice detector is worse
than the classical detector on every measured axis and does not
generalize to real photographs — recommendation is NOT to integrate it.
Session 14 diagnosed WHY (see Section 11's correction, below the
original Session 13 report, and `diagnostics/M4_1_HEATMAP_DIAGNOSIS.md`):
a training-target/heatmap-resolution mismatch with this dataset's real
dot density (180-500+ dots/image). Session 15 quantified that mismatch
directly (no CNN involved at all — a pure target-representation check,
see "Session 15" below and
`experiments/m4_1/diagnostics/TARGET_RESOLUTION_REPORT.md`): the
current 32×32 architecture's target recovers only 5-28% of true dots as
distinguishable peaks even in the ideal noise-free case; 128×128 is the
minimum resolution that recovers 100% across the observed density
range. Do not assume a trained model in this repo means ML detection is
production-ready; it explicitly is not, per measured evidence. No
retraining or production integration has occurred at any point in
sessions 13-15.

Work from sessions 4-12 lives on branch `feature/generation-pipeline`
(pushed to origin, not yet merged to `master`) —
`git log --oneline master..feature/generation-pipeline` to see them, or
PR compare link: https://github.com/SIH-2026-Celestials/pulli_kolam/pull/new/feature/generation-pipeline

## Session 15 — M4.1.2 Target Resolution Representation Check (COMPLETE)

**Experiment name**: Target-resolution representation check (pure
representation experiment — no CNN, no checkpoint, no torch, no
retraining, no dataset expansion). Follows up session 14's finding that
the training TARGET itself, not the model or peak detector, loses
individual-dot identity.

**Methodology**: Surveyed all 179 already-generated ground-truth JSON
files across `experiments/m4_1/data/{train,val,test}/`,
`synthetic_photos/`, and `synthetic_photos_heldout/` (no new images
generated) to find the corpus's real dot-density range: 180-500 dots/
image, with a bimodal gap (kolam19-based: 180-224; kolam29-based:
444-500; nothing between). Selected 3 representative images spanning
this range (180, 208, 500 dots). Reimplemented the existing target-
heatmap construction (`experiments/m4_1/model.py`'s coordinate-scaling
+ Gaussian-blob logic) LOCALLY inside a new diagnostic script
(`experiments/m4_1/diagnose_target_resolution.py`), generalized to
resolutions 32×32/64×64/128×128/256×256, sigma held fixed at 1.2 cells
(the model's actual trained value) throughout to isolate "does
resolution alone help." Measured objectively: local-maxima count vs.
true dot count, nearest-neighbor spacing in cell-units relative to
sigma, and literal cell-collision count.

**Objective findings** (full table:
`experiments/m4_1/diagnostics/TARGET_RESOLUTION_REPORT.md`):
- 32×32 (current architecture): recovers only **5-28%** of true dots
  as distinguishable target peaks (26/500 for the densest pattern, up
  to 28.2% literally colliding into the same cell) — a hard ceiling in
  the target itself, independent of any model or training choice.
- 64×64: improves to 86% recovery for kolam19-density (180-224 dots)
  but only **29%** for kolam29-density (500 dots) — still insufficient
  across the full range.
- 128×128: **100% recovery for every density tested** (180, 208, 500
  dots) — local-maxima count exactly equals true dot count. The minimum
  sufficient resolution found.
- 256×256: also 100% recovery, with a more comfortable separation
  margin (0% of dots within 3σ of a neighbor, vs. 94.8% still-touching
  at 128×128 for the densest pattern).

**Conclusion**: The current 32×32 architecture has a measured,
objective information ceiling that no amount of retraining could
exceed. 128×128 is the minimum resolution that makes individual-dot
recovery possible in principle; 256×256 gives more margin at the
densest observed patterns. This confirms (does not merely repeat)
session 14's diagnosis with a direct, model-free measurement.

**Recommended next step**: NOT a full retrain. If this direction is
pursued in a future session: first confirm a finer-output-resolution
architecture (targeting ≥128×128, e.g. reduced stride and/or larger
model input) can actually be trained to reproduce a target at that
resolution before any full retrain — this experiment establishes only
that the REPRESENTATION could in principle support individual-dot
recovery, not that a small CNN can learn to predict it. Still
recommend evaluating this against option 2 in Session 13's Section 13
(deprioritizing the ML-detection direction) given the scale of change
implied.

Tests: core `tests/` 123/123 passing (unchanged), `experiments/m4_1/tests`
16/16 passing (unchanged). Retraining performed: NO. Production
integration performed: NO.

## Session 13 — M4.1 Learned Lattice Detection Baseline — RESEARCH REPORT (COMPLETE)

**Bottom line: the learned detector is worse than the classical
detector on every measured axis, including its own held-out test set,
and does not generalize to real photographs at all.** This is a
negative result, reported in full per the task's explicit "possible
conclusions... learned detector is worse... synthetic improvement does
not transfer to real photographs" — both apply here, both are measured,
neither is softened.

### 1. Hypothesis

Can a small learned vision model (CNN) improve dot/lattice detection on
low-contrast/low-light kolam photos, while producing output that
satisfies the existing, frozen `Lattice.pixel_positions` contract with
zero changes to the deterministic downstream engine? Motivated by
session 12's M4.0 finding that the ONE genuine real-photo failure case
in scope (`kolam2_tshrinivasan.jpg`) had visible dots the classical
detector still missed.

### 2. Dataset

- **Synthetic (Tier A, used for training)**: 164 newly generated images
  (`experiments/m4_1/data/`), rendered from real, already-validated
  kolam19/kolam29 CSV patterns via `generate_synthetic_photos.render_clean`
  (reused unmodified) + a new `degrade_v2` pipeline.
- **Real (Tier B, evaluation only, never trained on)**: the existing
  22-photo corpus (session 12), 4 in-scope / 18 `NO_VISIBLE_DOT_MARKERS`.

### 3. Synthetic generation methodology

`experiments/m4_1/generate_training_data.py`: rotation ±15°, scale
0.85-1.15×, mild perspective, background tint (5 floor-color options),
brightness/contrast pushed toward the two REAL measured low-contrast
failures (`kolam2_tshrinivasan.jpg`: mean 62.5/std 21.6;
`kolam_naduveetu_meenakshisundaram.jpg`: mean 72.6/std 63.4), variable
Gaussian blur/noise, real JPEG re-encode at variable quality, variable
dot/line size. A per-image `severity ∈ [0,1]` drives brightness/
contrast/blur/noise together.

**Important caveat discovered during evaluation, not hidden**: this
degradation pipeline turned out considerably harsher than intended.
Even the UNMODIFIED classical detector's recall collapsed on these sets
(0.086-0.18) versus its 1.0/0.9995 on the original, gentler
`generate_synthetic_photos.py` degradation. The dataset is not
"realistic phone photo" difficulty — it is closer to worst-case/
adversarial difficulty. This confounds the learned-vs-classical
comparison on `m4_1_val`/`m4_1_test`: both detectors struggle there, so
those two sets are less informative than `synthetic_tuned`/
`synthetic_heldout` (gentler, and also never seen by the learned model)
for judging real-world-relevant performance.

### 4. Train/validation/test split

Pattern-level disjoint (train: 18 patterns, val: 5, test: 9 — kolam19
+ kolam29 pattern numbers never repeat across splits), and disjoint from
every pattern already used by the classical tuned/held-out sets. Disjoint
seed ranges per split. Full pattern IDs and per-image severity/gray
stats: `experiments/m4_1/data/split_manifest.json`. Train: 108 images
(18×6 variants), val: 20 (5×4), test: 36 (9×4).

### 5. Classical baseline (measured, `experiments/m4_1/results/classical_baseline.json`)

| set | recall | precision | mean loc. error (px) |
|---|---|---|---|
| synthetic_tuned (7 img, original gentle degradation) | 1.0000 | 0.9997 | 0.72 |
| synthetic_heldout (8 img, original gentle degradation) | 0.9995 | 0.9997 | 0.77 |
| m4_1_val (20 img, harsh degrade_v2) | 0.180 | 0.948 | 1.08 |
| m4_1_test (36 img, harsh degrade_v2, true held-out) | 0.086 | 0.972 | 0.94 |

Real photos: no pixel-exact ground truth (unchanged from session 12);
6/18 (33%) `NO_VISIBLE_DOT_MARKERS` images produce false-positive
detections.

### 6. Learned baseline (measured, same files)

| set | recall | precision | mean loc. error (px) |
|---|---|---|---|
| synthetic_tuned | 0.069 | 0.357 | 4.27 |
| synthetic_heldout | 0.055 | 0.321 | 3.60 |
| m4_1_val | 0.038 | 0.241 | 3.92 |
| m4_1_test (true held-out) | 0.051 | 0.290 | 3.99 |

**The learned model is worse than the classical detector on every one
of these 8 numbers**, including on `synthetic_tuned`/`synthetic_heldout`
where the classical detector is near-perfect and the comparison is
completely uncontaminated by the harsh `degrade_v2` confound above.

### 7. Model architecture

`experiments/m4_1/model.py`: `DotHeatmapNet`, 60,641 parameters. 4 conv
blocks (16→32→64→64 channels), 3× maxpool (stride 8 total), 1×1 conv
head → single-channel heatmap logits at 32×32 (input 256×256). Trained
40 epochs, Adam lr=1e-3, BCEWithLogitsLoss against a Gaussian heatmap
target (σ=1.2 heatmap-cells), batch size 8, CPU only. Best val_loss
0.2236 (epoch ~33; loss plateaued from epoch ~9 onward — the model
converged to a poor local solution early and did not meaningfully
improve with more epochs). **Trains on `preprocessed.binary`** (the
same Otsu-binarized, deskewed mask `detect_lattice` receives) — NOT the
raw photo — to avoid a train/inference distribution mismatch (a bug
caught and fixed before this run; see the earlier draft's mistake,
corrected in `DotHeatmapDataset`).

### 8. Metrics

Per `docs/M4_EVALUATION_PROTOCOL.md`: precision/recall/mean localization
error at 6.0px tolerance (unchanged convention), reported per set,
never blended. `CONFIDENCE_THRESHOLD=0.4` and the NMS suppression
radius were fixed BEFORE any evaluation run against `m4_1_test` or the
real photos — not tuned post-hoc (task's explicit rule).

### 9. Real-photo results (`experiments/m4_1/results/real_photo_comparison.json`)

| file | classical | learned | human estimate |
|---|---|---|---|
| kolam2_tshrinivasan.jpg | 1 | 48 | ~25-30 |
| kolam_attur1_infofarmer.jpg | 12 | 52 | ~4 clearly visible (unresolved discrepancy, see Phase 2 note) |
| kolam_naduveetu_meenakshisundaram.jpg | 0 | 54 | ~100-150 |
| muggu_kollam_sirensongs.jpg | 4 | 44 | ~20-30 |

**The learned detector outputs a near-constant 44-54 "detections" on
every real photo regardless of content** — a textbook severe
distribution-shift signature (trained only on clean synthetic renders;
real photos have camera noise/JPEG/background/resolution statistics the
training data never modeled). NO_VISIBLE_DOT_MARKERS false-positive
rate: classical 6/18 (33%, unchanged from session 12), **learned 18/18
(100%)** — the learned detector fires on every single no-dot photo.

### 10. Downstream results (`experiments/m4_1/results/downstream_test.json`)

No crashes for either detector on any population (0/36, 0/8, 0/4 —
confirms the sparse-detection-collapses-to-empty adapter design avoids
the known `trace_path` blocker in practice, not just in unit tests).

| population | classical fully-connected | learned fully-connected |
|---|---|---|
| m4_1_test (36) | 6/36 | 6/36 (tied, but see below) |
| synthetic_heldout (8) | 6/8 | 0/8 |
| real_in_scope (4) | 1/4 | 0/4 |

The learned detector "reaches motif analysis" MORE often than classical
(36/36, 8/8, 4/4 vs. classical's 6/36, 8/8, 2/4) — but this is
misleading, not a success: it reaches that stage because it almost
always returns ≥3 detections (even garbage ones), while classical's
sparser, more honest detections on hard images often correctly return
too few nodes to proceed at all. "Reached a later pipeline stage" ≠
"succeeded" — **fully-connected-graph rate, the more meaningful measure,
favors classical or ties everywhere, never favors learned.**

**Direct answer to Phase 9's question ("does better perception → better
structural analysis actually happen?"): no evidence of that here —
worse perception did not produce better structure, and the
appearance of "reaching more pipeline stages" was a false positive
signal, not genuine improvement.**

### 11. Failure analysis

- **Severe distribution shift, synthetic→real.** The clearest, most
  decisive signal (Section 9): near-constant output regardless of real
  photo content. The model learned something specific to its narrow
  synthetic training distribution, not a generalizable dot-detection
  concept.
- **Underfitting even on synthetic held-out data.** Even on
  `synthetic_tuned`/`synthetic_heldout` (gentle degradation, closest to
  "realistic"), the model badly underperforms classical (recall
  0.055-0.069 vs. 0.9995-1.0). val_loss plateaued by epoch ~9 of 40 and
  never meaningfully improved.
  **CORRECTED by a follow-up diagnostic (M4.1.1, `diagnose_m4_1_heatmap.py`,
  full report `diagnostics/M4_1_HEATMAP_DIAGNOSIS.md`)**: the original
  framing above ("too little data/capacity") is not what the evidence
  actually shows. Every image in every evaluation set — M4.1's own AND
  the original classical-baseline sets — has 180-500+ ground-truth
  dots (verified directly), against only a 32×32=1,024-cell heatmap
  output. At that density, the training TARGET itself (Gaussian σ=1.2
  heatmap-cells per dot) already merges into one undifferentiated blob
  before the model ever sees it (visually confirmed). The model fits
  that blob almost exactly (heatmap MSE 0.002-0.003 against its own
  target) — it is not undertrained or too small for its task, it
  learned its target very well; **the target itself never encoded
  individual-dot identity at this resolution.** A peak-detector
  threshold/suppression-radius sweep (25 configurations) confirmed this
  is not primarily a peak-extraction bug either — best achievable
  recall anywhere in the sweep is ~0.109, still far below classical, and
  only at a ~195-peaks-per-image precision collapse. Root cause is a
  Phase-4 architecture/target-design choice (heatmap resolution too
  coarse for this dataset's actual, now-measured, dot density), not a
  data-volume or peak-detection problem. **This does not change the
  headline recommendation (do not integrate the learned detector) — it
  replaces the "why" with a more precise, evidenced explanation.**
- **Two real implementation bugs were found and fixed during Phase 5/6
  testing** (full detail preserved from the in-progress log, condensed
  here): (a) an NMS suppression-radius unit-conversion bug that turned
  1 true dot into ~9 spurious detections (fixed, verified against a
  synthetic 5-point ground-truth case); (b) a PyTorch↔MKL OpenMP DLL
  conflict causing hard process crashes the first time both libraries'
  native code paths run in one process (mitigated with
  `KMP_DUPLICATE_LIB_OK=TRUE`, verified not to silently corrupt output
  for this workload before relying on it — see Phase 5 investigation
  notes preserved in git history of this file). **Neither bug explains
  the negative headline result** — both were fixed before the Section
  5-10 numbers above were measured; the poor performance is a genuine
  modeling-capacity/data-scale/domain-gap result, not an artifact of a
  bug that's still present.
- **The `degrade_v2` synthetic pipeline was too harsh** (Section 3),
  confounding the `m4_1_val`/`m4_1_test` comparison specifically — this
  makes classical's OWN numbers on those two sets look worse than its
  real-world capability (known-good: 1.0/0.9995 on gentler synthetic
  data), so the fairest classical-vs-learned comparison is Section 6's
  `synthetic_tuned`/`synthetic_heldout` rows, where the gap is just as
  large and uncontaminated by this confound.

### 12. Limitations

- Real-photo evaluation has no pixel-exact ground truth (unchanged
  since session 12) — Section 9's real-photo numbers are detection
  counts and qualitative failure signatures, not precision/recall.
- Training set is small (108 images, 18 unique patterns) by ML
  standards — this experiment cannot distinguish "CNNs fundamentally
  can't help here" from "this particular tiny model/dataset combination
  wasn't enough," and does not claim to.
- `degrade_v2`'s difficulty calibration (Section 3) needs revisiting —
  it overshot "realistic hard photo" into something closer to
  worst-case synthetic noise, which is a methodology flaw worth fixing
  before any future retry, not a finding about ML's potential.
- Single architecture, single hyperparameter setting tried — no
  architecture search, no data augmentation ablation, no learning-rate
  sweep. This is explicitly the smallest reasonable baseline the task
  asked for, not an optimized one.
- OpenMP mitigation (`KMP_DUPLICATE_LIB_OK=TRUE`) is an acknowledged
  environment workaround, not a production-grade fix (Section 11).

### 13. Recommendation for M4.2

**Do not proceed to integrate this learned detector into the
pipeline.** The evidence does not support it, and the task's own
"strict rule" is to report exactly this outcome when the numbers say
so, not to reach for a positive spin.

Two legitimate paths forward, both explicitly conditional on new
evidence, neither decided here:
1. **Retry with materially more scale** — **UPDATED by the M4.1.1
   diagnostic** (`diagnostics/M4_1_HEATMAP_DIAGNOSIS.md`): more
   data/epochs alone will NOT fix this, since the diagnostic shows the
   model already fits its (inadequate) training target almost exactly.
   Before any full retrain, the smallest justified next step is a
   cheap, no-retrain check: regenerate a handful of existing images'
   ground-truth heatmap target at finer resolution (e.g. a 128×128 or
   64×64 grid with a proportionally smaller Gaussian σ) and verify
   individual dots actually become distinguishable at this dataset's
   real density (180-500+ dots/image) BEFORE committing to an
   architecture change and full retrain.
2. **Abandon the ML-detection direction for now** and revisit M4's
   original Section 10 boundary decision — the classical detector,
   despite its own real limitations (session 12), was not beaten by
   this attempt, and "no measured improvement yet" is a valid basis for
   deprioritizing this specific avenue in favor of other project
   priorities.

Either way: the frozen `Lattice.pixel_positions` contract, the
adapter pattern (`engine/ml_contract.py` + a separate
`experiments/*/`-scoped detector module), and the evaluation protocol
(`docs/M4_EVALUATION_PROTOCOL.md`) all worked exactly as designed and
need no rework — only the model/data/training need reconsideration if
this direction is pursued further.

**Strict rules honored throughout**: `engine/image_io.py` and every
other deterministic-core file are untouched; `trace_path`'s known
`IndexError` blocker (documented session 12) was NOT fixed;
`generate_synthetic_photos.py` was reused, not modified; every metric
in this report is measured and reproducible from the committed
`experiments/m4_1/results/*.json` files, none fabricated; the negative
result is reported in full, not minimized.

Tests: core `tests/` suite 123/123 passing (unchanged, untouched).
M4.1 experiment tests: `experiments/m4_1/tests/` 16/16 passing (run with
`KMP_DUPLICATE_LIB_OK=TRUE python -m pytest experiments/m4_1/tests/`).

## Session 12 — M4.0 Data Readiness (full text below, also the canonical copy)

## Session 12 — M4.0 Data Readiness (full text below, also the canonical copy)

# M4.0 DATA READINESS REPORT

Companion to session 11's M4 Readiness Report (below, unchanged). This
session executes that report's two entry conditions: (1) expand the
real-photo sample, (2) freeze the ML-output -> deterministic-engine-input
contract. **No model code was written and no training occurred**, per
this session's explicit scope.

### 1. Real-photo corpus size

23 files in `real_photos/` (5 from session 11 + 18 new this session).
1 (`ithayakkamalam_pulli_mayooranathan.jpg`) is excluded as a confirmed
digital rendering, not a photograph — session 11 had already reached
this conclusion but never recorded it in `MANIFEST.md`; that gap is
fixed this session. **22 genuine, individually-verified real
photographs** in the evaluation corpus, within this task's 15-30
target range.

### 2. Source/attribution status

All 22 verified individually on their own Wikimedia Commons file
description page before download (author, license, EXIF/format
evidence) — the same methodology session 11 established, applied again
this session, including its own documented rejections: 4 candidates
checked and excluded (`Ithayakkamalam - 1/2.jpg` and
`Kolam-Pulli oodu-Tamil-culture.jpg`: Photoshop-authored digital
artwork, not photographs; `MargaliKolam-1.jpg`: no verifiable EXIF/camera
data, excluded as unverifiable rather than included at lower confidence).
Full source/license/attribution record: `real_photos/MANIFEST.md`.
Licenses: CC BY-SA (3.0/4.0), CC BY 2.0, Public Domain — all permit
reuse with attribution, attribution recorded per file. Cameras/dates
span 2001-2023, Sony/Canon/Nikon/Samsung/HTC/Lenovo/mobile and
mirrorless, resolutions 340x263 to 9248x6936.

### 3. In-scope image count

**4 of 22 (18%)** genuinely depict a visible pulli/dot lattice:
`kolam2_tshrinivasan.jpg`, `kolam_attur1_infofarmer.jpg`,
`kolam_naduveetu_meenakshisundaram.jpg`, `muggu_kollam_sirensongs.jpg`.
This low in-scope rate is itself a finding, not noise — see Section 13.

### 4. NO_VISIBLE_DOT_MARKERS count

**18 of 22 (82%)**: `pulli_kolam_ramdhaya.jpg`, `kolam1_raaj.jpg`,
`kolam_aruppukottai_tanandaraj.jpg` (painted peacock scene, not a dot
kolam at all), `kolam_attur12_infofarmer.jpg`, `kolam_attur5_infofarmer.jpg`,
`kolam_bangalore_moed.jpg`, `kolam_diamond_aiswarya.jpg`,
`kolam_floral_salem_thamizhpparithi.jpg` (marigold-petal offering
rangoli), `kolam_house_tamilnadu_vadakkan.jpg` (line-only sikku kolam),
`kolam_india06_mckaysavage.jpg`, `kolam_india09_mckaysavage.jpg`,
`kolam_india12_mckaysavage.jpg` (Om symbol, no dot grid),
`kolam_paris_dalbera.jpg` (painted exhibition mandala with tribal-mask
motifs, not a dot kolam), `kolam_patteeswaram_dalbera.jpg` (dense
paisley/leaf linework, no individually resolvable dots),
`kolam_pongal_uthandi_tagooty.jpg` (decorative "eye" motifs, not a pulli
grid), `kolam_sandpainting_mckaysavage.jpg`,
`kolam_thiruvananthapuram_vism.jpg` (line-only woven star kolam),
`rangoli_32dots_rachana.jpg` (fully filled geometric mosaic — despite
its title claiming an underlying 32-dot grid, no individual dots are
visible in the finished, filled artwork). Every one of these is
classified `NO_VISIBLE_DOT_MARKERS` by direct visual inspection (Read
tool, this session), not inferred from detector output — consistent
with session 11's "do not call this an ML failure" rule.

### 5. Low-contrast cases

Of the 4 in-scope photos: `kolam2_tshrinivasan.jpg` (gray mean 62.5,
std 21.6 — the original, already-documented case) and
`kolam_naduveetu_meenakshisundaram.jpg` (gray mean 72.6, std 63.4 — a
NEW, independently discovered low-light case this session) both have
visually confirmed dots that the deterministic detector fails on (0-1
raw pixel detections against a photo with visibly many more dots than
that). This is now **n=2** low-light/low-contrast failures, not n=1 —
directly relevant to session 11's condition 1 ("expand the sample
before sizing a dataset effort"): the failure mode is confirmed to
recur, not a one-off.

### 6. Other failure modes (new this session)

- **`kolam_attur1_infofarmer.jpg`: a clean SUCCESS.** 12/12 dots
  detected, lattice fit succeeded. First real (non-synthetic) photograph
  in this project's history where the deterministic pipeline's dot
  detection stage worked correctly end to end. Its connected component
  did not cover all nodes (`level2_connected = False`), which is a
  separate, downstream (stroke-tracing/connectivity) question, not a
  detection failure — out of this session's ML-boundary scope (dot
  detection only, per `docs/M4_EVALUATION_PROTOCOL.md` Section 2).
- **`muggu_kollam_sirensongs.jpg`: a PARTIAL detection** (4 dots found,
  visibly more present in the photo; decent contrast, gray mean 133.1 —
  not obviously a contrast problem, cause not conclusively determined
  this session, reported honestly as unresolved rather than guessed).
- **A newly discovered, reproduced-in-the-wild crash**:
  `kolam_india12_mckaysavage.jpg` (a `NO_VISIBLE_DOT_MARKERS` photo — an
  Om symbol with no real dots) produced exactly 2 spurious pixel
  detections and 0 fitted lattice coordinates — the precise asymmetric
  `Lattice` shape documented as a blocker in `docs/ML_CONTRACT.md`
  Section 5 (originally found via constructed adversarial testing this
  session, BEFORE this photo was even run) — and it crashed
  `image_io.trace_path` with `IndexError`, confirmed by
  `validate_real_photos.py`. This is significant: the blocker is not
  confined to genuine-dot photographs. Any photo producing 1-2 spurious
  blob detections — including one with NO real dots at all — can crash
  the pipeline. **Not fixed this session** (strict rule: do not modify
  `trace_path`); listed as a blocker in Section 8.
- Several `NO_VISIBLE_DOT_MARKERS` photos still produced nonzero
  detection counts from the deterministic detector (`kolam_india06`: 4,
  `kolam_pongal_uthandi_tagooty`: 6, `rangoli_32dots_rachana`: 36,
  `kolam_thiruvananthapuram_vism`: 11, `kolam_aruppukottai_tanandaraj`:
  1) — all almost certainly false positives from grout lines, dry
  leaves, fabric/newspaper texture, or the regular geometric edges of
  filled color blocks, NOT real dots (confirmed absent by direct visual
  inspection). This is evidence the detector's false-positive surface is
  broader than "genuine dot photos with degraded contrast" — worth
  keeping in mind if a future false-positive-rate metric is measured
  against this corpus.

### 7. Ground-truth schema

Defined in `docs/M4_EVALUATION_PROTOCOL.md` Section 1 — two tiers.
Tier A (synthetic photo proxies, `synthetic_photos/` +
`synthetic_photos_heldout/`): unchanged, pixel-exact, rendered from
already-validated CSV patterns. Tier B (real photos, new this session):
deliberately coarser and uncertainty-labeled — `in_scope`,
`dots_visible_to_human`, `visible_dot_count_estimate` (explicit
estimate, never fabricated precision), `dot_center_annotations` (`null`
where a photo is too degraded to annotate reliably — "mark it
appropriately rather than inventing coordinates"), `annotation_uncertainty_note`,
`failure_stage`. No Tier B photo was hand-annotated with precise pixel
coordinates this session — the schema is defined, per Phase 2's own
scope ("before collecting a large dataset, define exactly what
constitutes ground truth"), not yet populated at scale.

### 8. ML interface contract

Frozen in `engine/ml_contract.py` (a zero-dependency `typing.Protocol` +
`Callable` type alias matching `detect_lattice`'s exact signature,
`Preprocessed -> Lattice`, plus `assert_conforms()`, a structural
shape-invariant checker) and `docs/ML_CONTRACT.md` (full specification:
input/output types, coordinate system and normalization, ordering,
missing/duplicate/out-of-image detections, empty/minimum-point
convention, and error behavior). `detect_lattice` itself verified to
satisfy the frozen `Protocol` (`isinstance(detect_lattice,
MLLatticeDetector) == True`).

**One concrete blocker documented, not fixed**: `trace_path` crashes
with `IndexError` on a `Lattice` with 1-2 `pixel_positions` but 0
`lattice_coords` — reproduced both by direct construction (this
session's contract tests) AND organically in the wild (Section 6,
`kolam_india12_mckaysavage.jpg`). `assert_conforms()` cannot catch this
by itself (0 coords is a legal value of its shape invariant) — this is
explicitly called out in both `docs/ML_CONTRACT.md` and the test suite
so it isn't mistaken for a complete guard.

### 9. Contract tests

`tests/test_ml_contract.py`, 6 tests, all passing: a hand-built mock
detector (hardcoded output, no detection algorithm at all) proven to
drive `trace_path` + graph construction + `validity.check_validity` +
`motifs.induce_motif_set_adaptive` with ZERO changes to any of those
functions; the empty-detection convention matches `detect_lattice`'s
own; the documented blocker is reproduced directly (`pytest.raises`)
and the recommended safe convention (collapse 1-2-point detections to
fully empty) is proven to avoid it.

### 10. Deterministic baseline metrics

`validate_real_photos.py` (new this session) run against all 22 in-scope
candidates, reporting the three levels `docs/M4_EVALUATION_PROTOCOL.md`
Section 3 defines, kept separate:

- **Level 1 (dot detection)**: no pixel-exact real-photo ground truth
  exists yet (Section 7) so no precision/recall number is reported for
  real photos — only raw counts (Section 5/6) and the qualitative
  success/fail/partial per in-scope image. Synthetic-corpus precision/
  recall is unchanged from session 11 (dot recall 1.0000 tuned / 0.9995
  held-out) — not re-measured this session, nothing in the codebase
  that would affect it changed.
- **Level 2 (graph construction)**: 21/22 completed without crashing;
  1/22 crashed (Section 6). Of the 4 in-scope images, 1 fully connected
  lattice+graph (`kolam_attur1`), 2 zero-detection (no graph to be
  connected/disconnected), 1 partial-detection-but-not-fully-connected
  (`muggu_kollam_sirensongs`).
- **Level 3 (full analysis)**: not separately blocked by anything found
  this session; not run to completion on any image with zero detected
  nodes (nothing to analyze), consistent with the protocol.

### 11. Proposed evaluation protocol

Unchanged from `docs/M4_EVALUATION_PROTOCOL.md` (this session's own
output) — localization tolerance 6.0px (matching the existing synthetic-
corpus convention), three separate levels never blended into one
"accuracy" number, Tier A vs Tier B ground truth kept distinct.

### 12. Proposed dataset size/rationale

- **Synthetic (Tier A) is the primary training-data lever, not real
  photos.** `kolam_data/Kolam19 Images/` alone has 400 source images
  (kolam29/kolam109 collections also available) — ample material to
  generate synthetic photo proxies at whatever volume is needed, with
  perfect ground truth, at far lower cost than real-photo annotation.
- **Augmentation should be calibrated to THIS session's measured real
  failure statistics**, not guessed: `kolam2_tshrinivasan.jpg` (gray
  mean 62.5, std 21.6) and `kolam_naduveetu_meenakshisundaram.jpg`
  (gray mean 72.6, std 63.4) give concrete brightness/contrast targets
  for a synthetic low-light/low-contrast augmentation pass — grounded in
  Section 5's evidence, not an arbitrary degradation range.
- **Real photos (Tier B) are not yet a viable training set** — only 4
  in-scope examples exist despite a 22-photo collection effort (an 18%
  in-scope rate, Section 3). At that rate, reaching even 50 in-scope
  real training examples would require collecting roughly 275+ candidate
  photos — a real, now-quantified cost (previously unknown before this
  session). Recommend real photos be used exclusively as a small,
  never-trained-on TEST set for real-world generalization checking, not
  as training data, until/unless a much larger collection effort is
  separately justified.
- **Train/val/test split (proposed, not implemented)**: synthetic data
  for train + a synthetic held-out split for validation (mirroring the
  existing `synthetic_photos` / `synthetic_photos_heldout` split
  already used for the deterministic baseline); the 4 in-scope real
  photos reserved as a test-only sanity check, explicitly too small for
  a statistically meaningful test metric alone but valuable as a
  qualitative reality check.
- **Transfer learning**: not decided — explicitly deferred, this is an
  architecture question and out of this session's scope.
- Dataset size, split, and augmentation are a PROPOSAL for the next
  session to execute, not implemented this session.

### 13. Remaining blockers

**Blocking for ML entry: none newly found.** Session 11's 0-blocking
conclusion stands. The items below are conditions/technical debt to
track, not blockers:

1. **`trace_path` IndexError on asymmetric `Lattice`** (Sections 6, 8) —
   a small, well-understood, NOT-yet-applied guard fix (analogous to
   `detect_lattice`'s own existing `< 3` guard). Now confirmed to occur
   organically, not just in constructed adversarial tests — raises this
   from "theoretical" to "observed in the collected corpus." Should be
   fixed before real ML-detector integration begins, since an ML
   detector reporting low-confidence/sparse detections is a plausible,
   even likely, real output shape.
2. **In-scope real-photo rate is low (18%)** — not a pipeline defect
   (Section 4: these are genuinely non-dot-grid kolam/rangoli styles),
   but it means future real-photo collection for Tier B purposes is
   expensive per in-scope example — factor this into any future
   collection-effort sizing (Section 12).
3. **`muggu_kollam_sirensongs.jpg`'s partial-detection cause is
   unresolved** — flagged honestly rather than guessed; worth a closer
   look (not done this session) before assuming it's the same
   low-contrast failure mode as the other two.
4. Everything already listed as non-blocking in session 11's Section 9
   (novel generation 0/5, motif-selection-granularity gap, branch not
   merged to `master`) is unchanged and still non-blocking.

### M4.0 Entry Decision

# M4.0 DATA + CONTRACT READY

Both of session 11's conditions have been acted on:
1. Real-photo sample expanded 4x in-scope count (1 -> 4), corpus size
   4x overall (5 -> 22... 23 with the excluded file) — genuinely larger,
   though the low in-scope rate (Section 13, item 2) means "expand
   further" remains open-ended rather than fully closed; this session's
   expansion is a substantial, evidenced step, not a token gesture.
2. ML-output -> engine-input contract frozen (`engine/ml_contract.py`,
   `docs/ML_CONTRACT.md`), proven substitutable via 6 passing contract
   tests, with one concrete pre-existing blocker discovered, reproduced
   twice (constructed + organic), documented, and explicitly NOT fixed
   (per this session's own strict rule).

**Recommendation for the next session, before writing any model code**:
fix the `trace_path` asymmetric-`Lattice` guard (item 1 above) as a
small, isolated, well-justified deterministic-engine change — it is now
a demonstrated real-world crash risk, not a hypothetical — then proceed
to M4.1 (architecture/training).

---
Tests: 123/123 passing (117 from session 11 + 6 new
`tests/test_ml_contract.py` tests this session).

## Session 11 — M4 Readiness Report (full text below, also the canonical copy)

# M4 READINESS REPORT

## 1. Executive Summary
The deterministic engine (data model, motif induction, D4 symmetry,
reconstruction, structural generation) is mature, tested (117/117,
deterministic across repeated runs — verified twice, identical result),
and its multiplicity accounting is now verified correct at every layer
that was checked, including via direct adversarial construction of
`nx.MultiGraph` edge keys (not inferred from counters). The image-input
pipeline has been tested against real, non-synthetic photographs for the
first time this project cycle, and the results are decisive: **every
real-photo failure observed traces to the SOURCE PHOTO lacking usable
dot information (no visible markers, or markers destroyed by low
contrast) — not to a defect in the deterministic graph/motif engine
itself.** This distinction is the central finding of this report and
directly defines the M4 ML boundary (Section 10): ML belongs at the
image-to-lattice boundary, not inside the structural engine.

## 2. Current Deterministic Baseline
`CSV → KolamPattern → nx.MultiGraph → motif induction (3 selection
modes) → D4 symmetry → reconstruction / structural generation → validity
checking`. 117 tests, all passing, confirmed deterministic (test suite
run twice, byte-identical pass count both times). Architecture and full
session history: see the rest of this file below this report.

## 3. Multiplicity Verification
**PASS**, with direct evidence, not inference. This session constructed
5 adversarial cases and inspected actual `nx.MultiGraph` edge keys:
- Case A (doubled relative edge, one placement) → 2 parallel edges, 2 distinct keys. Confirmed.
- Case B (cross-placement accumulation) → 3 parallel edges, 3 distinct keys. Confirmed.
- Case C (motif N=2 + residual M=3) → 5 physical edges via `reconstruct_kolam`. Confirmed.
- Case D (duplicate motif placements 2+2 + residual 2) → 6 physical edges, sum NOT collapsed. Confirmed.
- Bonus (over-production 5 vs. target 2) → capped at 2, excess of 3 explicitly reported (`capped_excess`), never silently dropped. Confirmed.

**Conclusion**: `build_candidate_graph` and `reconstruct_kolam` correctly
materialize multiplicity in every case tested — no bug found. The
previously-flagged gap (`induce_motif_set_adaptive`'s own selected
placements can still physically over-explain if fed into
`build_candidate_graph` WITHOUT going through `reconstruct_kolam`'s
independent re-capping) is real but is a property of motif-selection
POINT granularity, not of these two graph-construction functions — it
only affects the motif-only code path (`generate_kolam`/
`motif_only_report` called directly on `induce_motif_set_adaptive`
output), not reconstruction. Both facts are now backed by passing tests
(5 new this session), not assertion.

## 4. Real Photograph Findings
5 real, licensed Wikimedia Commons photographs individually verified
(author/license/EXIF); 1 excluded after visual inspection revealed it
was synthetic clipart despite passing the metadata check. 4 genuine
photographs characterized in full:

| photo | dims | gray mean/std | Otsu thresh | fg fraction | R (dot radius est.) | dots detected | dots visible to human | classification |
|---|---|---|---|---|---|---|---|---|
| pulli_kolam_ramdhaya.jpg | 1280×960 | 121.1 / 31.2 | 168.0 | 0.9461 | 236.8 | 0 | **0** — floral line kolam, no dot markers by design | **NO_VISIBLE_DOT_MARKERS** + BACKGROUND (heavily textured stone floor inflates fg fraction) |
| kolam1_raaj.jpg | 344×293 | 99.3 / 53.6 | 132.0 | 0.7840 | 40.0 | 0 | **0** — solid-filled colored mandala, no dot markers by design | **NO_VISIBLE_DOT_MARKERS** |
| kolam2_tshrinivasan.jpg | 1727×2081 | 62.5 / 21.6 | 77.0 | 0.8273 | 156.6 | 0 (1 before Task A's crash-guard fix; crashed before that) | ~25-30, estimated by eye from a blurry low-light photo — **not a precise/reliable ground truth, stated as an estimate, not fabricated as exact** | **LOW_CONTRAST** + LIGHTING (grayscale mean 62.5, no clean bimodal separation — the one case where dots genuinely exist and detection still fails) |
| kolam_sandpainting_mckaysavage.jpg | 3226×2138 | 154.6 / 51.2 | 156.0 | 0.5192 | 225.2 | 0 | **0** — dense crosshatch fill, no discrete dot markers visible anywhere | **NO_VISIBLE_DOT_MARKERS** + **PERSPECTIVE** (clear oblique/raking camera angle, not overhead) + BACKGROUND (unpaved dirt floor) |

**Foreground-fraction finding, not previously checked this precisely**:
all 4 photos — not just the one that crashed — show an implausibly high
"ink" fraction under Otsu (52-95%, vs. a real kolam trace which should
occupy a small single-digit-to-low-double-digit fraction of a well-lit
photo). This means EVERY real photo's binarization is compromised to
some degree, not just the low-contrast one; it's just that 3/4 photos
would fail anyway (no dots exist to find), so the binarization defect
was masked by the more fundamental DOT_VISIBILITY problem there.

**3/4 failures are `NO_VISIBLE_DOT_MARKERS`, not pipeline bugs** — real
kolam photography spans styles the dot-lattice model doesn't claim to
cover (line-only, filled/colored, hatch-filled). **1/4 (`kolam2`) is a
genuine pipeline limitation** on a photo that DOES have the right
underlying structure — this is the one real, in-scope gap.

## 5. Dense Pattern Findings
**RESOLVED this session cycle** (session 10, re-confirmed unchanged this
session — no code touched here that would affect it). Root-caused via
direct visualization (0 spurious detections, 120/484 dots missed, 99.2%
of those below `threshold_abs`) to a threshold anchored to the single
largest/least-degraded dot in the image. Fixed
(`THRESHOLD_ABS_FRAC` 0.75→0.65). Re-validated on the full 15-image test
set: tuned dot recall 0.9803→**1.0000**, held-out 0.9413→**0.9995**,
zero regression on any sparse pattern.

## 6. Benchmark Integrity
- Synthetic benchmark (15 images, tuned): dot recall **1.0000**, dot
  precision 0.9997.
- Held-out benchmark (8 images, disjoint kolam numbers, disjoint seed
  range, generator code unchanged): dot recall **0.9995**, dot precision
  0.9997. The tuned/held-out gap that existed before this session's
  Task B fix (0.9803 vs 0.9413) has closed to near-zero (1.0000 vs
  0.9995) — evidence the fix generalizes, not just fits the one worst
  case it was diagnosed from.
- 15-pattern CSV motif-induction benchmark: recall 96.41%, compression
  2.72x (multiplicity-exact, corrected this session cycle, decomposed
  honestly — not attributed entirely to better induction; see session
  10 log below).
- All benchmark scripts (`validate_*.py`) are deterministic, fixed-seed
  where randomness is used, and re-runnable from source data — verified
  by literally re-running them this session and reproducing consistent
  results.

## 7. Novel Generation Status
**Unchanged since M3.7, not re-touched this session**: 0/5 valid
candidates in the reproducible evaluation set (`validate_novel_generation.py`).
Every candidate demonstrates real D4 structural symmetry (33-54%
coverage) and 0/5 duplicate their source pattern, but none reach full
Eulerian validity or full connectivity — a known, honestly-reported
limitation (no connectivity-seeking strategy in the greedy placement).
**This is explicitly a POST-M4 item, not a blocker** — see Section 8.

## 8. M4 Blocking Issues

| # | item | status | evidence |
|---|---|---|---|
| 1 | Multiplicity accounting | **PASS** | Session 10: ported Counter-based exact accounting to `induce_motif_set`/`induce_motif_set_adaptive`/`mdl_gain`/`compression_ratio`. Verified via re-measurement (96.41% recall, 2.72x compression) with an honestly-decomposed delta. |
| 2 | Physical multiplicity materialization | **PASS** | This session (Section 3): 5 adversarial cases, actual MultiGraph keys inspected directly, all correct. |
| 3 | Synthetic benchmark | **PASS** | Section 6: dot recall 1.0000, precision 0.9997. |
| 4 | Held-out benchmark | **PASS** | Section 6: dot recall 0.9995, precision 0.9997, gap to tuned set nearly closed. |
| 5 | Real photograph ingestion | **PARTIAL** | Section 4: pipeline correctly and safely handles (no crash) photos lacking dot markers; genuinely fails on the one photo type it should theoretically handle (low-contrast, dots present). Sample size is small (n=1 for the in-scope failure mode) — real, but not yet a large-sample-verified problem. |
| 6 | Dense-pattern robustness | **PASS** | Section 5: root-caused and fixed, re-validated with no regression. |
| 7 | Novel generation | **FAIL (as a generation feature), NOT BLOCKING for M4** | 0/5 valid — see Section 7. M4's own stated purpose is comparing learned vs. structural representations, not shipping a generator; this failure doesn't prevent that comparison. |
| 8 | Validity checking | **PASS** | `check_validity`/`diagnose_validity`/`check_self_consistency` unmodified this session, still the hard, unmodified gate for CSV data; extensively tested across all prior sessions. |
| 9 | Dataset integrity | **PASS** | `docs/DATA_FORMAT.md`'s CSV semantics audit (session 5) stands, unchanged; three collections (kolam19/29/109), format fully documented and reproducibly loaded. |
| 10 | Reproducibility | **PASS** | Full test suite run twice this session, byte-identical 117/117 both times. All `validate_*.py` scripts are fixed-seed/deterministic. |
| 11 | Evaluation methodology | **PASS, WITH ONE CAVEAT** | Recall/compression are now honestly labeled and multiplicity-exact (session 10); the compression delta was explicitly decomposed to avoid a misleading "induction got better" narrative. Caveat: real-photo evaluation sample is small (5 photos, 1 in-scope failure case) — a methodology, not a defect, but worth naming as a real limit on how much Section 4's finding can generalize. |
| 12 | Deterministic baseline reproducibility | **PASS** | Same evidence as #10 — this session's own test runs are the direct proof, not a claim. |

**Blocking count: 0.** Item 5 (real photograph ingestion) is the one
PARTIAL and is exactly what defines the M4 ML boundary (Section 10) —
it is the reason to enter M4, not a reason to delay it.

## 9. Non-Blocking Technical Debt
- Novel generation's 0/5 validity (Section 7) — a real engine limitation, explicitly post-M4.
- `induce_motif_set_adaptive` placements can still physically over-explain if used directly with `build_candidate_graph`/`generate_kolam`, bypassing `reconstruct_kolam`'s independent cap (Section 3) — narrow, already-documented, not exercised by any current benchmark path.
- Low-contrast/low-light binarization (Section 4, `kolam2`'s root cause) is diagnosed, not fixed at the CV level — this is intentionally left for the M4 ML boundary (Section 10) rather than patched with more classical-CV heuristics.
- Small real-photo sample size (Section 8, item 11's caveat).
- `feature/generation-pipeline` branch still not merged to `master`.

## 10. Proposed ML Problem
**Current deterministic pipeline:**
```
photo → preprocess (grayscale, deskew, Otsu binarize)
      → detect_lattice (distance-transform + local-maxima dot detection)
      → trace_path (skeletonize + hub-based edge tracing)
      → KolamPattern-compatible nx.MultiGraph
      → graph analysis (motifs, symmetry, validity, reconstruction)
```

**Proposed M4 boundary, directly evidenced by Section 4 — not chosen
without evidence:**
```
photo → ML/CV component: robust dot-lattice detection under
        low-contrast/low-light conditions (a LOCALIZED, well-scoped
        detection/segmentation problem, not full scene understanding)
      → normalized dot-position output (same contract detect_lattice
        already produces — Lattice.pixel_positions / .lattice_coords)
      → UNCHANGED deterministic engine (trace_path, KolamPattern, graph
        analysis) — no other stage needs to change
      → analysis
```

**Why THIS problem, not another**: every real-photo failure in Section
4 traced to either (a) no dots existing in the source at all
(3/4 — not an ML problem, no ground truth to learn from, out of scope
entirely) or (b) dots existing but invisible to a fixed global Otsu
threshold under low contrast (1/4 — the ONE photo where the deterministic
downstream pipeline, once given correct dot positions, would work
unmodified, since `trace_path`/`KolamPattern` construction were never
implicated in any failure). This is the smallest, most evidenced ML
problem: **robust dot detection under adverse lighting**, not
segmentation, not perspective correction (perspective was only observed
alongside `NO_VISIBLE_DOT_MARKERS` on one photo, never alone or as the
sole blocker on a photo that otherwise had detectable dots), not stroke
extraction (never implicated — `trace_path` was never reached as a
failure point in any of the 4 real photos, since detection always failed
first).

## 11. M4 Entry Decision

# M4 READY WITH CONDITIONS

Minimum conditions before ML implementation begins:
1. **Expand the real-photo sample before training-data collection
   decisions are made.** n=5 (1 in-scope failure case) is real evidence
   of the FAILURE MODE, but not yet a large enough sample to size a
   dataset-collection effort against. Get more low-contrast/low-light
   real kolam photos (ideally 15-30) specifically to confirm the
   failure rate and characterize the difficulty distribution before
   committing to an ML approach's scope.
2. **Confirm the ML boundary contract explicitly** (Section 10): the
   ML component's OUTPUT must be a drop-in match for
   `Lattice.pixel_positions`/`.lattice_coords`'s existing shape, so
   `trace_path` and everything downstream remains genuinely unchanged.
   This should be written down as an interface contract before model
   work starts, not discovered during integration.
3. Do not treat Section 9's non-blocking debt items as needing
   resolution first — they are correctly separated from the M4 gate and
   should not be allowed to creep into scope.

Do not begin ML implementation until conditions 1-2 are satisfied.

---
Tests: 117/117 passing, run twice this session for reproducibility
confirmation, both runs identical.



## Session 10, Item 3 (Task A + Task B — both executed this session, not deferred again)

**Task A — first real (non-synthetic, non-bundled) photograph test,
ever, in this project's history:** 5 real, licensed photos fetched from
Wikimedia Commons Category:Kolam, individually verified (author,
license, EXIF/format evidence) via each file's own Commons page, NOT
assumed from category listings or search snippets — those proved
unreliable (the task's own suggested example, "Pongal Kolam.jpg" by
"Thamizhpparithi Maari," does not match Commons' actual record: real
author is "Chenthil," description says "Chettinadu Style," not
Pulli/dot-grid — not used). One candidate that passed the metadata check
turned out, on VISUAL inspection, to be a synthetic digital dot graphic
with no drawn strokes at all — excluded from the real-photo set, flagged
rather than silently used. Files + full license/attribution record:
`real_photos/` (`MANIFEST.md`).

RAW first-attempt `build_graph()` result, no pre-tuning, on the 4
confirmed real photographs:
- 3/4: zero dots detected (no visible dot markers in the source pattern
  — consistent with the corpus-wide finding from session 4 that many
  real kolam styles/photos don't use visible pulli).
- 1/4 (the one photo where dots ARE visually present): **CRASHED** —
  `numpy.linalg.LinAlgError: Singular matrix`, not just a bad result.

Root-caused (same discipline as every prior session): that photo is
genuinely low-light/low-contrast (grayscale mean 62.5/255, std 21.6, no
clean bimodal separation) — Otsu's global threshold misclassified 82.7%
of the image as "ink," collapsing dot detection to a single spurious
blob. Every synthetic test photo in this project, however degraded with
blur/noise/rotation, was always well-lit and high-contrast — genuinely
poor lighting was never modeled or tested before this real photo.
**Fixed** (small, scoped, NOT a full binarization overhaul):
`detect_lattice` now treats fewer than 3 candidate dot pixels as
degenerate input (a 2D affine fit is underdetermined below that) and
returns a clean empty result instead of crashing. This makes the
OUTCOME safe; it does NOT fix the underlying low-contrast binarization
failure, which remains open (see below). 4 new regression tests.

**Task B — kolam29-scale (dense) dot-detection: diagnosed AND fixed,**
not just measured again. Visualized detected vs. ground-truth dot
positions on the documented worst held-out case (kolam29_k50, dot
recall 0.752): 0 spurious detections, 120/484 real dots missed entirely
— a pure recall problem, not merging or crossing-point confusion.
99.2% of the 120 missed dots have their OWN distance-transform value
below the detector's `threshold_abs` — a genuine intensity-gate
rejection (min_distance suppression was checked and ruled out: the
minimum true nearest-neighbor spacing, 17.6px, is well above
min_distance=11px). **Root cause**: `threshold_abs = 0.75 * R` where
`R = dist.max()` is the GLOBAL max distance-transform value anywhere in
the image — effectively the size of the single largest/least-degraded
dot. Dense patterns render dots smaller in absolute pixels than sparse
ones, so the same absolute blur/JPEG degradation eats a proportionally
bigger bite, pushing many real dots below a threshold anchored to the
single largest dot in the image.

**Fixed**: `THRESHOLD_ABS_FRAC` lowered from 0.75 to 0.65 (new named
constant in `engine/image_io.py`, was an inline literal). Verified
across ALL 15 synthetic-photo images (7 tuned + 8 held-out), not just
the worst case: every kolam19 (sparse) pattern UNCHANGED; every kolam29
(dense) pattern dramatically improved (kolam29_k50: 75.2%→99.6%,
kolam29_k20: 88.9%→100%, kolam29_k80: 88.7%→99.8%, kolam29_k1/k2 tuned:
94.3%/92.0%→100%/100%), at most a 0.2pt precision cost on one pattern
for +11pt recall. **Full official `validate_image_io.py` re-run, both
batches:**

| | avg dot recall (before → after) | avg dot precision |
|---|---|---|
| tuned set | 0.9803 → **1.0000** | 0.9997 (unchanged) |
| held-out set | 0.9413 → **0.9995** | 0.9997 (unchanged) |

The "kolam29-scale detection is the actual weak point" finding from
sessions 4/8 is now resolved, not just re-confirmed. 2 new regression
tests (kolam29_k50 must stay >0.99 recall; kolam19 sparse guard rail).

Tests: 110 → 112 (Task A) → included above. Combined with Items 1-2:
**106 → 112 total this session.** All green, zero regressions anywhere.

## Still open after session 10
1. Low-contrast/low-light binarization (Task A's root cause) is
   diagnosed but NOT fixed — Otsu's global threshold has no way to
   handle a genuinely dark, low-contrast photo. A real fix would need
   adaptive/local thresholding (e.g. `cv2.adaptiveThreshold`) or a
   contrast-normalization preprocessing step — not attempted this
   session, scoped out as a separate, larger effort.
2. Every real photo tested (all 5, all styles) either has no visible
   dots or is the one low-contrast case — genuinely challenging, diverse
   real-world conditions have now been sampled, but the sample is still
   small (5 images, 1 usable for dot-lattice testing at all). More real
   photos, especially well-lit ones WITH visible dots, would meaningfully
   extend this.
3. The accounting-vs-materialization gap from Items 1-2 (build_candidate_graph
   can still physically over-explain from induce_motif_set_adaptive's
   placements) remains unfixed, as explicitly scoped.
4. `feature/generation-pipeline` branch still not merged to master.

## Session 10 summary (Items 1-2: relabel + port multiplicity fix upstream + re-measure)

**Item 1 (relabel, committed alone first):** every historical "recall"/
"compression ratio" number tied to `induce_motif_set`/
`induce_motif_set_adaptive`/MDL-gating was relabeled "distinct-edge" in
this file. Numbers unchanged by this step — labeling only.

**Item 2 (port the multiplicity fix upstream, then re-measure):**
Ported the same principle already applied to `reconstruct_kolam`
(session 9) into `engine/motifs.py` itself: `_stamped_edges`,
`_build_candidates`, `induce_motif_set`, `mdl_gain`, and
`induce_motif_set_adaptive` now track coverage via `Counter` (per-edge
STRAND count), not plain `set`s of distinct pair identity. Uses Python's
native `Counter.__and__` (min-per-key intersection) and `-`/`-=`
(positive-only difference) — exact multiplicity semantics with no
hand-rolled accounting. `compression_ratio`'s `raw_size` also corrected
from `n_distinct_edges * EDGE_UNIT_COST` to
`G.number_of_edges() * EDGE_UNIT_COST` (true strand count), matching the
now-multiplicity-exact residual/motif cost terms on the same basis.
Backward compatible: both `mdl_gain` and `compression_ratio` still
accept a plain `set` (treated as 1 strand per entry) for old callers.

**Corrected numbers, same 15 patterns, `validate_mdl.py` (unchanged
script — the fix alone changes what it reports):**

| metric | OLD (distinct-edge, mislabeled) | NEW (multiplicity-exact) | delta |
|---|---|---|---|
| avg recall | 90.3% | **96.41%** | **+6.1 pts** |
| avg compression ratio | 2.40x | **2.72x** | +0.32 (see caveat below) |
| avg motifs used | 19.6 | **30.80** | +11.2 (more motifs now needed to actually satisfy full multiplicity, not just touch a pair once) |
| total wall time, 15 patterns | ~unmeasured precisely before | **129.3s** | kolam109 patterns now ~20-30s each (more candidates evaluated) |
| patterns beating old radius=1 baseline on recall | mixed | **15/15** | |
| patterns beating old radial=1 baseline on compression | mixed | **15/15** | |

**Recall's improvement is single-cause and clean**: the distinct-pair
basis (`n_total`/`len(residual)`) is UNCHANGED in `validate_mdl.py`'s own
script code — only the CRITERION for "when is a pair removed from
residual" changed (now requires full multiplicity satisfied, not first
touch). The +6.1pt improvement is a real, directly-attributable
consequence of the fix.

**Compression's improvement is NOT single-cause — decomposed and
reported honestly, not conflated**: `raw_size`'s basis ALSO changed
(distinct pairs → true raw strand count), independent of the
residual/motif-selection fix. Measured separately: using the NEW motif
selection/residual but the OLD (distinct-pair) raw_size basis gives
**2.16x** (WORSE than the old 2.40x — the residual cost term alone got
more expensive, correctly, since strand deficits are no longer
undercounted). Only with the ALSO-corrected raw_size basis (true strand
count, bigger, since ~20-25% of real edges are double strands per
DATA_FORMAT.md) does the ratio come out to 2.72x, higher than before.
**The headline "compression went up" is real for the final, fully-corrected
formula, but do not describe it as "the induction got more efficient" —
part of the change is a bigger, more honest denominator AND numerator
basis, not purely better motif selection.**

**New finding, discovered while verifying the fix, not anticipated —
accounting fix ≠ physical materialization fix:** `induce_motif_set_adaptive`'s
own internal Counter-based accounting is now correctly multiplicity-exact,
but `build_candidate_graph` (which turns `MotifPlacement`s into an
actual `nx.MultiGraph`) still blindly re-stamps EVERY point in a selected
placement, with no memory of what the accounting layer capped/credited
during selection. Verified directly on real kolam19#1 data: accounting
reports 94.7% recall / 2.13x compression (healthy), but the MATERIALIZED
graph from `build_candidate_graph(placements, dots)` still has **82
over-explained pairs, 420 strands produced vs source's 312** (35%
excess). This is a real, separate gap from what Item 2 asked to fix
(explicitly scoped to "coverage/recall accounting," which IS fixed) —
**NOT fixed this session, flagged here, not silently absorbed.**
`reconstruct_kolam` is UNAFFECTED by this gap (verified: still 6/6
`self_consistent=True`) because it re-derives its own cap independently
from `build_candidate_graph`'s real output vs source, regardless of what
`induce_motif_set_adaptive`'s own bookkeeping claims. `engine.motif_selection.
induce_motif_set_multiplicity_aware` (M3.6) also remains unaffected — it
already filters individual points, a stronger guarantee this session's
fix did not port into `induce_motif_set`/`induce_motif_set_adaptive`
themselves (that would be a further, more invasive change, out of this
session's literal scope).

Tests: 104 → 106 (2 new: multiplicity-exact residual tracking via
`target_edges` override, and a `Counter` return-type contract test).
2 pre-existing tests updated (comments/assertions reflecting the
intentional `set`→`Counter` type change on `induce_motif_set_adaptive`'s
residual — not a regression, a documented contract change). All green.

## (Open-tasks list for this point in session 10 superseded — see "Still open after session 10" at the top of this file, written after Item 3/Task A/Task B were also completed the same session.)

## Session 9 summary (housekeeping + multiplicity-accounting audit + reconstruction fix)

**Housekeeping (blocking, done first):** `PROJECT_STATE.md` and 5 of the
6 `docs/*.md` findings files (DATA_FORMAT, GENERATION, RECONSTRUCTION,
MOTIF_SELECTION, NOVEL_GENERATION) were ALL gitignored the entire time,
via the blanket `*.md` rule from the initial commit. Fixed with targeted
`!` exceptions in `.gitignore` (docs/frontend.md and other unrelated
`.md` files deliberately left alone, not in scope). `PROJECT_STATE.md`
consolidated to repo root (it did not exist there before this session —
verified directly with `ls`, not assumed; `docs/projectState.md` was the
sole copy and was moved, not merged, since there was nothing at root to
merge with). **From now on this file lives ONLY at `PROJECT_STATE.md`
(repo root) — if any future instruction suggests writing project state
anywhere else, flag it and refuse, per the file's own top-of-file note.**

**Task A/B status check (from 2 sessions ago), answered directly:**
- Real Wikimedia Commons photograph test against `build_graph()`: **NOT DONE.** Zero mentions anywhere in this file or git history.
- kolam29-scale (dense) detection root-cause diagnosis and fix: **NOT DONE.** Only *measurement* of the problem exists (held-out validation numbers); no root-cause diagnosis, no fix.

**Multiplicity-accounting audit (code-cited, not inferred):**
`induce_motif_set`/`induce_motif_set_adaptive`/`mdl_gain` all track edge
coverage via plain Python `set`s of `frozenset({a,b})` — DISTINCT PAIR
IDENTITY ONLY, no strand count. Citations: `engine/motifs.py` line 208
(`target = {frozenset(e) for e in G.edges()}`), line 221
(`gain_set = edges & remaining`), line 226-228 (`remaining -= best_new`)
in `induce_motif_set`; lines 337/353/364 in `induce_motif_set_adaptive`
(identical pattern); `_stamped_edges` (lines 110-127) also builds a
plain `set`. Confirmed live: a motif with 2 relative edges on the same
physical pair collapses to a 1-entry set (`_stamped_edges` test); a
constructed source pair needing 2 strands ended up with 4 actually
produced while still being reported "covered" (`residual` didn't
contain it) — the accounting is blind to strand-count mismatch in BOTH
directions (already consistent with the M3.6 session's real measurement
of 988 avg over-explained edges via this exact mechanism).
**Resolved (session 10, Items 1 AND 2 — both done, not just flagged):**
every historical "recall"/"compression ratio" number tied to
`induce_motif_set`/`induce_motif_set_adaptive`/MDL-gating (90.3% avg
recall, 89.7%, 99.49%, 2.40x/1.82x/1.64x compression) was
**distinct-edge** — identity-only (does a pair have >=1 strand explained,
ignoring true strand count), not multiplicity-exact.
`compression_ratio`'s own docstring already said almost exactly this
("measures CONNECTIVITY compression, not exact strand-multiplicity
reconstruction") but that caveat had never been carried into how
"recall" itself gets labeled anywhere it's printed. Item 1 relabeled
every such occurrence with an explicit "distinct-edge" qualifier; Item 2
then ported the SAME multiplicity fix already applied to
`reconstruct_kolam` (session 9) upstream into `induce_motif_set`/
`induce_motif_set_adaptive`/`mdl_gain`/`compression_ratio` themselves,
and re-measured. **Real corrected numbers, real delta, both reported
below** ("Session 10 summary") — not just flagged as an open decision
anymore.

**Reconstruction fix (`engine/reconstruction.py`, scoped and applied,
per explicit instruction):** `reconstruct_kolam` previously copied
`build_candidate_graph`'s motif contribution into the final candidate
UNCAPPED, then added residual deficit on top — so an over-explained pair
(two placements each independently touching it) ended up with MORE
strands in the reconstructed candidate than source has, even though
residual correctly added zero. Fixed: candidate now takes
`min(motif_contribution, source_multiplicity)` per pair, always; excess
is reported explicitly in the new `capped_excess` field, never silently
dropped. **Re-ran all 6 patterns with `check_self_consistency` — the
literal exit criterion — 6/6 True**, all fast (kolam109#1: 1.3s,
kolam109#26: 11.6s — `diagnose_validity`'s O(k²) matching, which hung
10+ min on kolam109 two sessions ago, never triggers post-fix, since the
candidate now always exactly equals source, always already valid, so its
odd-degree list is always empty — verified with actual timing, not
assumed; no approximate-matching workaround was needed this time).
Verified separately: 0 "phantom" edges (motif claiming a pair source
lacks entirely) across all 4 non-kolam109 patterns checked — the fix
only ever caps excess, never removes a real edge. 1 new regression test
(`test_reconstruction_caps_over_explained_motif_strands`).

Tests: 103 → 104. All green, zero regressions.

## Open tasks (session 9 list — superseded, see "Open tasks (session 10..." above for current status)
Items 1 and 3 below were resolved in session 10 (see above); kept here
only as historical record of what session 9 handed off. Do not treat
this block as current.

## Session 8 summary (M3.6 multiplicity-aware selection + M3.7 novel generation + M3 Gate)
Full M3 program now complete and stopped at the gate, per instructions
(NOT proceeding to ML without this report existing first).

**M3.6** (`engine/motif_selection.py`, `docs/MOTIF_SELECTION.md`): fixes
the over-explanation bug M3.5 exposed. `induce_motif_set_multiplicity_aware`
structurally guarantees `accumulated[e] <= source[e]` for every edge
(never a heuristic) by rejecting, never clipping, any candidate stamp
that would exceed source's real per-edge strand count.
`induce_motif_set_eulerian_aware` adds parity-improvement scoring on top
of the same hard constraint. Measured on the same 6-pattern set as M3.5:
mode A (old, unmodified) over-explains an average of 988 edges/pattern;
modes B/C have zero, always. Real design bug found and fixed during
development (see module docstring): per-individual-point scoring made
every fresh motif type score negative on its lone first instance since
the rule cost wasn't yet amortized — fixed by scoring at the motif-TYPE
level while still filtering multiplicity per individual point within an
accepted group. Structural consequence found and verified (not assumed):
because B/C guarantee no over-explanation, motif+residual reconstruction
built from either ALWAYS reaches exact multiplicity match with source
(verified on 4/6 patterns) — meaning "motif+residual valid" cannot
distinguish B from C at all; the meaningful comparison is motif-ONLY
behavior (odd-degree count: A=596 avg, B=557, C=344 — C wins on every
single pattern).

**M3.7** (`engine/novel_generation.py`, `docs/NOVEL_GENERATION.md`):
genuinely distinct from reconstruction, enforced at the type level —
`select_novel_placements` never receives a source graph at all, so there
is nothing to copy a residual from, even by accident (verified directly:
`reconstruct_kolam(source, [])` still reproduces source exactly via
residual; `generate_novel_kolam` on the identical layout with a library
from that same source does not). Real bootstrap bug found and fixed:
reusing M3.6's `_parity_delta` directly made every layout's first-ever
edge score negative (a degree-0 node's first edge always "looks like"
breaking even parity under that function's semantics) — n_edges=0 on
every test until a dedicated `_novel_score` was written that treats a
first-ever touch as pure growth, not a tradeoff. 5-candidate evaluation
(`validate_novel_generation.py`): 0/5 valid, 0/5 fully connected, 0/5
duplicate their source pattern (strict edge-multiset check, explicitly
NOT a claim of artistic novelty) — reported plainly as the honest
current ceiling of a small (8-12 motif), single-source, no-lookahead
greedy library.

Tests: 93 → 103 (13 in `test_motif_selection.py`, 10 in
`test_novel_generation.py`). All green, zero regressions across the
whole M3.6/M3.7 addition.

**M3 GATE**: see the session's final chat report for the full 6-question
answer (discover motifs? reconstruct known Kolams? generate valid novel
candidates? how often valid? major limitations? what's available for
ML?). Short version: motif discovery and reconstruction both work and
are well-measured; novel generation runs correctly end-to-end but does
not yet reach validity (0/5 in the evaluation set) — this is the honest
state M4 would need to either accept as a baseline to beat, or address
structurally before ML entry.

## Open tasks (session 8, carried forward)
1. Novel generation validity is 0/5 — no connectivity-seeking strategy,
   small single-source libraries, no backtracking. The gate does not
   require 100% validity to proceed to ML (per the task's own M4
   readiness checklist), but this number should not be quietly assumed
   to have improved without re-measuring.
2. `select_novel_placements`/`induce_motif_set_multiplicity_aware`'s
   group-then-filter design has a known scoring subtlety (a group's
   value is judged on its full point list's potential even though some
   points get filtered post-hoc) — see docs/MOTIF_SELECTION.md.
3. M4 readiness checklist (from the task's own instructions) has NOT
   been explicitly walked item-by-item against current repo state in
   this session — do that first in any session considering M4 entry,
   don't assume the gate items are satisfied just because M3 finished.
4. `feature/generation-pipeline` branch still not merged to master (6
   commits now) — merge or continue on it, don't fork a parallel branch.

## Session 7 summary (M3.5 — real-data reconstruction, NOT novel generation)
New: `engine/reconstruction.py` — `reconstruct_kolam(source, placements,
residual_policy="exact")` (motif-only candidate, via the unmodified
`build_candidate_graph`, + the EXACT deficit of source edges no
placement explained, copied back verbatim with correct multiplicity;
explicitly NOT novel generation — dot layout is always
`source.dot_points`, residual is always real source edges) and
`motif_only_report` (the honest contrast baseline, reusing
`generate_kolam` unchanged + edge-recall measurement). `docs/RECONSTRUCTION.md`
documents the three-way distinction (motif explanation / reconstruction
/ novel generation) and states explicitly that motif+residual
reconstruction is NOT novel generation.

**Real finding, measured across all 6 requested patterns (kolam19/29/109
× {1, 26}), consistent at every scale**: motif-only is always
disconnected and invalid (41-800 components). Motif+residual always
reaches full connectivity (1 component) AND 100% distinct-edge agreement
with source — the residual mechanism works exactly as designed. But
motif+residual is **still Eulerian-invalid on all 6 patterns**, because
of a previously-undiscovered mechanism: overlapping motif windows can
stamp a dot pair MORE times than source actually has ("over-explanation")
-- residual only ever ADDS missing strands, never removes excess ones.
Concretely: kolam109 #1 goes from 1736 odd-degree nodes (motif-only) to
1528 (motif+residual) but never to 0; total strands end up 16248 vs
source's 12992 (+3256 excess). Documented in RECONSTRUCTION.md as a
known limitation, not silently fixed (task explicitly deferred motif-
discovery optimization to a future session).

**Scalability finding, discovered while running the experiment, not
theorized**: `diagnose_validity`'s odd-vertex matching is O(k²)
shortest-path computations. At kolam109 scale k reaches 1500+ — a first
attempt at the full `reconstruct_kolam` pipeline on kolam109 was killed
after 10+ minutes of CPU time with no result. `validate_reconstruction.py`
works around this by computing the same required fields via the same
real engine functions minus that one diagnostic call — not a different
algorithm, just skipping an optional field this experiment doesn't need.
The full pipeline (with diagnosis) remains correct and tested at
kolam19-scale. **Optimizing `diagnose_validity` for large k is
unaddressed — flag before running it unconditionally on a kolam109-scale
graph in a future session.**

Tests: 70 → 80 (10 new in `tests/test_reconstruction.py`: exact
reconstruction of a known synthetic pattern, motif-only disconnection,
residual restoration, multiplicity preservation, Eulerian validity after
restoration, non-mutation of source pattern and motifs, determinism,
motif-only vs. reconstruction stay distinguishable, unsupported
`residual_policy` raises, real-pattern dot-layout consistency). All
green, zero regressions.

## Open tasks (session 7, carried forward)
1. Over-explanation is unaddressed: reconstruct_kolam's residual step
   only adds missing strands, never removes excess ones from overlapping
   motif windows. This is THE blocker for ever reaching full validity via
   this decomposition, on every pattern tested, not just an edge case.
2. `diagnose_validity`'s O(k²) matching does not scale to kolam109-size
   odd-vertex counts (1500+) — needs either an algorithmic fix or a
   documented size guard before it's called unconditionally again on
   large graphs.
3. Novel generation (motifs on an unseen dot layout, no residual
   fallback) is still fully unstarted — and per this session's findings,
   attempting it before fixing over-explanation would likely fail for
   the same underlying reason reconstruction still fails.
4. `feature/generation-pipeline` branch is pushed but not merged — merge
   or continue building on it, don't start a parallel branch by mistake.

## Session 6 summary (structural generation, Phase 2 — NOT ML, NOT image generation)
New: `engine/generated_kolam.py` (`GeneratedKolam` — deliberately separate
from `KolamPattern`, since a generated candidate has no CSV provenance to
report honestly; see docs/GENERATION.md for the full reasoning).
`engine/generation.py` extended (unmodified `apply_motif` preserved) with
`build_candidate_graph`, `reconstruct_dot_trace`, `generate_kolam` — the
full pipeline: `MotifPlacement` rules (the exact type induction already
returns) + a dot layout -> candidate `nx.MultiGraph` (edges added one at
a time, never `compose`, so multiplicity across DIFFERENT placements
targeting the same pair can't be silently collapsed) -> unconditional
`check_validity`/`diagnose_validity` -> (only if valid) deterministic
`nx.eulerian_circuit`/`eulerian_path` traversal to an ordered dot trace.
`validity.py`'s dispatch extended to also accept `GeneratedKolam`
directly (`check_validity(candidate)` works like `check_validity(pattern)`
already did). Trace reconstruction is DOT-LEVEL ONLY — half-integer
loop-around point reconstruction was explicitly deferred (not
justifiable from graph topology alone: the same dot pair can be
double-stranded with one strand on each side of a skipped dot, so which
side isn't determined by the graph — see DATA_FORMAT.md's own concrete
example). `docs/GENERATION.md` documents the objective, API, construction,
multiplicity, validation, trace-reconstruction, and limitations, with a
worked synthetic example.

**Real-data experiment finding (honest, not adjusted to look better)**:
feeding kolam19 pattern 26's 8 MDL-gated-induced motifs into
`generate_kolam` on the source pattern's own 200-dot layout produced an
**invalid** candidate — 32 connected components, 12 odd-degree nodes, 6
corrections needed (228/276 distinct edges, 324/360 strands recovered).
This is the expected consequence of MDL-gating stopping once no further
motif pays for itself (by design, from session 4) — it does not
guarantee coverage or connectivity, and `generate_kolam` does not
currently compensate for that gap (e.g. by falling back to the
induction's own `residual` edge list). This is a real, exposed
limitation for the next session to pick up, not a bug in this session's
work.

Tests: 60 -> 70 (10 new in `tests/test_generation.py`, covering
determinism, the known-valid synthetic case, multiplicity preservation,
D4 placement, overlapping-motif accumulation, invalid-candidate
rejection, `check_validity` agreement, deterministic traversal, and
non-mutation of both source motifs and a real loaded `KolamPattern`).
All green, zero regressions, no existing test modified.

## Open tasks (session 6, carried forward)
1. Loop-around / half-integer trace reconstruction — explicitly deferred,
   not started. Needs a real geometric rule (not just graph topology) to
   pick a side; DATA_FORMAT.md's existing double-strand example shows why
   topology alone is insufficient.
2. Generation currently has no gap-filling / residual-edge fallback for
   partial motif coverage — this is why the kolam19 #26 real-data
   experiment came back invalid. Not attempted this session (task
   explicitly said "do not optimize yet").
3. No motif selection/search/diversity strategy exists — `generate_kolam`
   builds exactly what it's given, in order. Choosing good motifs for a
   target output is future work, explicitly out of scope this session.

## Session 5 summary (canonical KolamPattern data model)
New: `engine/kolam_pattern.py` (the `KolamPattern` dataclass — the single
canonical representation: pattern_id, collection, raw_trace, trace_points,
dot_points, edges, edge_multiplicity, graph, bounding_box) and
`engine/dataset.py` (`load_kolam(collection, pattern_id)` /
`load_dataset(collection)` — the ONE loader; owns all CSV-specific
interpretation, delegates the actual dot/edge extraction to
`graph_io.extract_dot_sequence`/`dot_sequence_to_multigraph`, doesn't
reimplement them). `docs/DATA_FORMAT.md` documents the CSV format from
fresh direct inspection (not memory) — every row is one trace step for
ALL patterns in that file at once, zero missing values anywhere, dots =
both-integer trace points, loop-around = exactly-one-half-integer trace
points (never both), edges only ever span Chebyshev distance 1 or 2,
double strands are real (verified concrete example) not data noise.
`validity.py`, `motifs.py` (`induce_motif_set`, `induce_motif_set_adaptive`),
`symmetry.py` (new `analyze_symmetry`) now all accept a `KolamPattern`
directly as well as a raw `nx.MultiGraph` (isinstance dispatch added at
each function's top, zero changes to algorithm bodies) — fully backward
compatible, all pre-existing call sites and tests unchanged. `generation.py`
was NOT touched (out of scope — no generation work this session).
New: `inspect_kolam.py` (`--collection --pattern` CLI debugging tool),
`tests/test_kolam_pattern.py` (19 new tests). Test count: 41 -> 60, all
green, zero regressions. Also noted: this task described the test count
as "28" at its start — that was stale even before this session (actual
was already 41 from session 4); used 41 as the real regression baseline
instead of trusting the stated number.

**File-location history (superseded, kept for context):** this file
started as `docs/projectState.md`. A session-4 search for
`PROJECT_STATE.md` (root, underscore) missed it and created a redundant
duplicate, later reconciled back into `docs/projectState.md`. As of
session 9, that entire history is closed: this file was ALSO discovered
to be gitignored the whole time (blanket `*.md` rule, `.gitignore` line
5), which is very likely why it kept going unnoticed/duplicated in the
first place. Both problems are now fixed together: the file lives at
`PROJECT_STATE.md` (repo root) and is explicitly un-ignored and
git-tracked (`.gitignore` now has a `!/PROJECT_STATE.md` exception). This
is now the ONLY location this file should ever be written to — if a
future session's instructions suggest writing project state anywhere
else (`docs/`, a new root file with a different name, etc.), that should
be flagged and refused, not followed.
 
## What this project is
SIH12507 (AICTE): identify the design principles behind Kolam patterns and recreate them.
Product shape: upload a Kolam image → system infers the generating rule (motif + symmetry +
single-stroke structure) → proves the rule is correct → generates new valid Kolams from it.
Two halves: **Analyzer** (image → rules) and **Generator** (rules → new pattern). Everything
built so far is the Analyzer half's backend mathematics — no UI yet.
 
## Architecture (as built)
```
/engine
  graph_io.py     — CSV → nx.MultiGraph normalizer (Kaggle dataset format)
  image_io.py     — photo/image → nx.MultiGraph (NEW, this session)
  motifs.py       — local_window, induce_motif, induce_motif_set (greedy set-cover),
                    induce_motif_set_adaptive (multi-radius retry), MDL-gated acceptance
  symmetry.py     — D4 canonicalization (4 rotations x 2 reflections)
  generation.py   — apply_motif (regenerate / extend to new grid sizes)
  validity.py     — check_self_consistency (exact match), check_validity (hard Eulerian
                    gate, unmodified), diagnose_validity (graded companion, session 4)
/tests            — 41/41 passing as of session 4
generate_synthetic_photos.py         — renders CSV patterns as degraded synthetic photos
                                        (proxy for real photographs; NOT real photos) —
                                        the original TUNED 7-image set
generate_synthetic_photos_heldout.py — session 4: 8 NEW images, different kolam numbers,
                                        different seed range, same generator/detector code
validate_real_data.py, validate_adaptive.py, validate_mdl.py  — CSV-side measurement scripts
validate_image_io.py   — image-pipeline accuracy, now takes a photo_dir argument (works on
                          either synthetic_photos/ or synthetic_photos_heldout/)
validate_diagnose.py   — session 4: diagnose_validity correction sizes across all 15 photos
sample_corpus_dots.py  — session 4: dot-marker presence check across the bundled corpus
```
 
## Critical design decision, stated once so it doesn't get re-litigated
**No ML/CNN anywhere in the core engine.** Lattice detection, motif matching, symmetry,
validity checking are all deterministic graph theory / classical CV. This was a deliberate
choice, not a gap. Only genuinely open question on this front: whether image-derived
low-confidence regions eventually want a learned confidence score layered on top — not yet
needed, not yet built.
 
## The self-correction discipline (say this explicitly in the pitch)
Four separate times, a number or check was trusted, then caught being wrong by testing it
against itself, then fixed:
1. **Eulerian gate**, early on: a hand-built synthetic test generator produced a pattern that
   FAILED its own single-stroke validity check (2 disconnected components, odd-degree
   vertices from dangling boundary edges). Conclusion: don't hand-tune synthetic ground
   truth — use real, pre-verified data instead (→ pivoted to the Kaggle dataset).
2. **Compression ratio formula**: originally divided total edges by one motif's size,
   silently assuming 100% coverage at zero placement cost. With real distinct-edge recall
   at 28%, the reported 164x distinct-edge compression ratio was fiction. Fixed to
   `raw_size / (motif_rules + placements + residual_edges)`, consistent edge-identity basis.
   (All "recall"/"compression ratio" figures in this section are DISTINCT-EDGE metrics —
   see the relabeling note under "Real measured numbers on record" below.)
3. **Coverage-vs-compression conflation**: adding motifs to maximize distinct-edge recall
   (via a `max_motifs_per_radius` count cap) was implicitly treated as the same objective as
   minimizing description length. It isn't — adaptive multi-radius induction won on
   distinct-edge recall (89.7%→99.5%) but LOST on distinct-edge compression on 15/15 patterns
   (1.82→1.64). Fixed by replacing the count cap with MDL-gated acceptance (add a motif only
   if it has positive net description-length gain) — this landed at 90.3% distinct-edge
   recall, 2.40x distinct-edge compression (better than both priors on compression), with
   6/15 patterns getting slightly LOWER distinct-edge recall than the old greedy version,
   correctly, because the gate refuses trades that don't pay for themselves. Proven with a
   dedicated test (`rejects_expensive_one_off_despite_recall_gain`).
4. **Image-pipeline validity gate mismatch**: even near-perfect image reconstruction
   (>94% edge recall) fails the strict Eulerian gate on 4/7 synthetic photos, because parity
   is fragile to 1-2 multiplicity errors. Motif induction degrades gracefully on the same
   imperfect input (0.885→0.744); the hard gate does not. **Fixed in session 4**:
   `diagnose_validity(G)` added to validity.py as an unmodified companion to the strict
   `check_validity` gate — Route Inspection Problem correction (odd-degree vertices,
   minimum-weight matching via shortest-path distance, `nx.min_weight_matching`), reporting
   exactly which nodes/edges are implicated. Run against all 15 synthetic photos (7 tuned +
   8 held-out, see below): 10/15 fail the strict gate, but the correction size is **not**
   uniformly small — it splits sharply by pattern density. kolam19 (sparse) failures average
   1.2 corrections (max 3): small, localized, genuinely supports "the gate was the wrong
   tool for this data" for that density class. kolam29 (dense) failures average 53.0
   corrections (max 62), touching ~25-28% of all nodes: NOT small or localized — a real
   reconstruction gap, not just gate oversensitivity. **Do not claim "the gate is just too
   strict" as a blanket statement — it's true for kolam19-scale patterns, false for
   kolam29-scale ones.**
## Real measured numbers on record (all checked per-pattern, not just averaged)
| Metric | Value | Source |
|---|---|---|
| CSV-based motif induction, MDL-gated: avg DISTINCT-EDGE recall (not multiplicity-exact — see note below) | 90.3% | validate_adaptive.py + MDL gating, 15 patterns across kolam19/29/109 |
| CSV-based, MDL-gated: avg DISTINCT-EDGE compression ratio (not multiplicity-exact — see note below) | 2.40x | same run |
| CSV-based, MDL-gated: motifs needed | 19.6 avg | same run |
| Image pipeline, dot detection (TUNED set, 7 photos) | precision 0.9997 / recall 0.9803 | generate_synthetic_photos.py, kolam19_k1/2/3/27/50 + kolam29_k1/2 |
| Image pipeline, edge tracing, exact-multiplicity (TUNED set) | precision 0.9758 / recall 0.9487 | same 7 photos |
| Image pipeline, dot detection (HELD-OUT set, 8 new photos, session 4) | precision 1.0000 / recall 0.9413 | generate_synthetic_photos_heldout.py, new kolam numbers, seed 7000+, detector code UNCHANGED |
| Image pipeline, edge tracing, exact-multiplicity (HELD-OUT set) | precision 0.9234 / recall 0.8825 | same 8 photos |
| — held-out degradation is concentrated in kolam29 (dense) patterns | kolam19 held-out ≈ tuned-set numbers; kolam29_k50 outlier: dot recall 0.752 | see below |
| Corpus sampling: bundled JPGs with visible dot markers | 0/30 (0%) | sample_corpus_dots.py, 10 each kolam19/29/109, seed 42 |
| Real dataset validity gate pass rate (CSV source) | 100% (15/15) | expected — dataset is pre-verified |
| Real (non-CSV) bitmap test, kolam19-26.jpg | FAILED — 88/227 odd-degree nodes | no visible dot markers — now known to be the NORM for this corpus, not an outlier |
| diagnose_validity correction size, kolam19 (sparse) failures | avg 1.2, max 3 | 10/10 kolam19 photos across both batches |
| diagnose_validity correction size, kolam29 (dense) failures | avg 53.0, max 62 (~25-28% of nodes) | 5/5 kolam29 photos across both batches |

**Resolved this session (session 4) — do not re-run these as if still open:**
- Held-out validation: done. Real, moderate, density-concentrated degradation confirmed
  (not catastrophic, not zero — see table above). Tuning-on-test-set risk was real but
  modest, and specific to the denser pattern class.
- Corpus sampling: done, decisively. 0/30 sampled bundled JPGs have visible dots, no
  exceptions across all 3 families. The entire "Images" corpus is line-only matplotlib
  renders (matches plot_kolam.py's own rendering code — no markers drawn).
- `diagnose_validity`: built, tested (3 dedicated tests), run against all 15 synthetic
  photos. Density-dependent finding above.

## Open tasks (check status at start of next session — may or may not be done)
1. Dot-marker-optional fallback mode for image_io.py — now a real priority, not
   hypothetical: the corpus sampling result above means this is needed for essentially
   ANY use of the bundled Images corpus as a real-image test source, not an edge case.
2. Improve dense-pattern (kolam29-scale, ~13px dot spacing) detection specifically — this
   is now the identified actual weak point (held-out numbers + diagnose_validity both point
   here), not the pipeline generally.
3. Still fully open, not started: any user-facing interface (Streamlit per the 12-hour plan,
   or React+FastAPI per the 60-day plan); wiring generation into a full "here's your new
   Kolam" user flow; a real (non-synthetic, non-dataset) photographed test image, which
   nobody has been able to test against yet — still the single largest untested risk.
## Reference documents already produced (should exist in the repo or chat history)
- War Room engineering report (full A-Z analysis, math formulation, algorithm comparison)
- 12-hour MVP implementation plan (Streamlit, local-first, no backend)
- 60-day production plan (React+FastAPI+Postgres, week-by-week)
- Product overview + feature roadmap (Tier A/B/C future features)
- Differentiation pitch vs. KolamNet/KolamNetV2 (classification-only) and the GAN-based
  Hugging Face tool (no correctness guarantee) — the core claim is: infer backward to the
  rule AND prove it's correct, which neither existing approach does.
## The one-sentence status if asked "where are you"
The core induction engine is done and rigorously validated on real dataset data (41 tests,
four self-caught-and-fixed bugs, MDL-gated motif selection). The image-input pipeline is
built and held-out-validated: ~90-100% accuracy on sparse (kolam19-scale) synthetic photos,
meaningfully lower and more variable on dense (kolam29-scale) ones — a real, now-measured
weak point, not a guess. The bundled dataset's own JPGs are confirmed (30/30 sampled) to have
no visible dot markers, so a dot-optional fallback is now a known real requirement, not a
hypothetical. Zero user interface exists yet. The single biggest untested risk remains a real
(non-synthetic, non-bundled) photograph — still nobody has tried one.
 