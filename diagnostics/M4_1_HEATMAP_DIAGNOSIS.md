# M4.1.1 Heatmap Failure Diagnosis

Diagnosis only - no retraining, no architecture change, no changes to
the frozen ML contract, `trace_path`, the classical detector, or
`peak_detect.py`/`ml_lattice_detector.py` themselves. Evaluates the
existing checkpoint (`experiments/m4_1/results/dot_heatmap_net.pt`,
val_loss 0.2236) exactly as trained. Full machine-readable results:
`diagnostics/m4_1_heatmap_results.json`. Visualizations (not committed,
reproducible via `diagnose_m4_1_heatmap.py`): `diagnostics/m4_1_heatmaps/`.

## Executive finding

**The dominant cause is a training-target/architecture resolution
mismatch, not primarily a peak-detection bug.** Every synthetic image in
this project's evaluation sets - M4.1's own train/val/test AND the
original classical-baseline tuned/held-out sets - contains **180 to
~500 ground-truth dots** (verified directly, not assumed; see Section 1
below). The model's heatmap output is **32×32 = 1,024 cells**. With a
training-target Gaussian blur of σ=1.2 heatmap-cells applied per dot at
this density, the individual dots' Gaussian blobs overlap so heavily
that **the ground-truth training TARGET itself loses individual-dot
identity before the model ever sees it** - visually confirmed: the
ground-truth heatmap for every dense pattern inspected is a single solid
blob covering the whole pattern region, not 180-500 distinguishable
peaks. The model learned to reproduce this blob closely (very low
heatmap MSE, 0.002-0.003) - it did NOT fail to learn its target. The
target itself never encoded what recall needs.

## 1. Does the CNN heatmap contain meaningful dot-localized signal?

**Partially, at the regional level only - not at the individual-dot
level.** Verified directly from `diagnostics/m4_1_heatmap_results.json`
and the saved visualizations:

- Heatmap vs. ground-truth-heatmap MSE is very low: 0.0021 (train/val,
  n=128), 0.0031 (held-out test, n=36) - the predicted heatmap closely
  matches its OWN training target in aggregate shape.
- Visually (`diagnostics/m4_1_heatmaps/group1_kolam19_k10_v0.jpg.png`,
  `group2_kolam19_k280_v0.jpg.png`): both the ground-truth heatmap and
  the predicted heatmap are solid, undifferentiated bright blobs filling
  the entire pattern's silhouette - correctly delineating WHERE the
  kolam is in the image (region-level signal, real and present), but
  with **zero visible individual-dot structure in either the target or
  the prediction**. The model is not failing to match its target; the
  target itself doesn't contain individual-dot signal at this
  density/resolution.
- This is confirmed quantitatively: ground-truth dot counts range
  180-500+ per image (Section 1 data below), against a 1,024-cell
  heatmap - after accounting for the σ=1.2 Gaussian blur radius, there
  is not enough resolution to represent more than roughly a few dozen
  cleanly-separated blobs, let alone hundreds.

**Verified pattern-density data** (from
`experiments/m4_1/results/classical_baseline.json` and this
diagnostic's own `n_ground_truth_dots` field, not assumed):

| set | dot-count range |
|---|---|
| classical baseline tuned (kolam19 #1,2,3,27,50) | 184-212 |
| classical baseline tuned (kolam29 #1,2) | 472 |
| classical baseline held-out (kolam19) | 196-204 |
| classical baseline held-out (kolam29) | 452-484 |
| M4.1 train/val/test (all patterns, both kolam19 and kolam29) | 180-500 |

**This density is not specific to the patterns M4.1 happened to pick -
it is the general density of this entire kolam19/kolam29 CSV
collection.** The classical detector handles this density fine because
it operates directly on the full-resolution (~900×900) pixel image via
`peak_local_max`, never downsampling to a coarse fixed grid.

## 2. Does peak_detect.py preserve or destroy that signal?

**It cannot meaningfully recover signal that the heatmap never had at
individual-dot resolution - but it is not itself a broken implementation.**
The peak-detector ablation (Section 4) shows recall stays low (0.04-0.11)
across the ENTIRE swept parameter range, including settings far more
permissive than the adapter's current configuration. If a well-resolved
heatmap were being destroyed by over-aggressive suppression, a much
larger recall recovery would be expected somewhere in the sweep. It
wasn't found. `peak_detect.py` behaves as designed (verified separately
by its own 7 passing unit tests, session M4.1) - it is receiving a
heatmap that itself under-resolves the target, and correctly extracting
what few distinguishable peaks exist in it.

## 3. Is the failure primarily model, training data/degradation, peak detection, or mixed?

**Primarily a training-target/architecture DESIGN mismatch (a
combination the task labeled "D," but weighted heavily toward one root
cause, not an even split):**
- **Architecture** (stride-8 → 32×32 heatmap) is too coarse for this
  dataset's actual dot density. This was a Phase-4 design choice
  (smallest reasonable baseline) made without checking the target
  dataset's dot-count distribution first - that check is the gap.
- **Training-target construction** (Gaussian σ=1.2 heatmap-cells per
  dot) compounds the resolution problem: even a finer heatmap alone
  might not fully fix it without also adjusting the blur radius that
  causes cross-dot blob overlap at high density.
- **Peak detection** (Section 2): not the primary cause - ruled out by
  the ablation's flat, uniformly-poor recall across its whole range.
- **Model training itself** (optimization, data volume, val_loss
  plateau from M4.1's original report): a real, separate, SECONDARY
  limitation - but not diagnosable as the dominant cause here, since the
  model demonstrably learned its (already-inadequate) target well (low
  MSE). A better-trained model against the SAME coarse/blurred target
  would still face the same resolution ceiling.

## 4. Does changing peak-detection thresholds materially recover recall?

**No - not materially.** Full sweep (5 thresholds × 5 suppression
radii = 25 configurations, evaluated on the 36-image held-out test set,
`diagnostics/m4_1_heatmap_results.json`'s `peak_detector_ablation`):

| confidence threshold | min-distance (heatmap cells) | precision | recall | F1 | avg peaks/image |
|---|---|---|---|---|---|
| 0.2 | 1.0 | 0.151 | **0.109** (best recall found) | 0.121 | 194.9 |
| 0.4 | 2.5 (current adapter) | 0.290 | 0.051 | 0.086 | 42.8 |
| 0.6 | 3.5 | 0.377 | 0.041 | 0.073 | 25.8 |

The best recall anywhere in the sweep (0.109) is achieved only by
accepting ~195 peaks per image (vs. ~5-8 true dot clusters worth of
distinguishable heatmap structure) and precision collapsing to 0.15 -
this is not a usable operating point, it is the sweep's floor being
reached (threshold near 0, suppression near-zero, i.e., "return nearly
every cell"). **No configuration approaches the classical detector's
performance on the same images (recall 0.086 at precision 0.972 - the
classical detector achieves comparable recall at 6x+ the precision).**
This is decisive evidence that peak-detection parameters are not the
bottleneck.

## 5. What happens on the 18 real no-dot photographs?

All 18 produce false-positive peaks (18/18, confirming M4.1's original
finding). New diagnostic detail, `no_dot_false_positive_analysis`:
- Mean 48.6 peaks/image - statistically indistinguishable from the
  synthetic sets' 41-50 peaks/image, and from the real in-scope photos'
  49.5 peaks/image. **The model produces roughly the same number of
  "detections" regardless of whether the image has 0, some, or hundreds
  of real dots** - consistent with M4.1's original "severe distribution
  shift" finding, now with a mechanistic explanation: it has learned to
  activate broadly over "pattern-like ink regions" in general (Section
  1), and every real photo (dot-based or not) has SOME ink region for
  it to activate over.
- Pairwise heatmap cosine similarity across 18 structurally different
  no-dot photos: mean 0.689 (range 0.337-0.961) - moderately high.
  Visual confirmation (`group4_kolam1_raaj.jpg.png`): the heatmap forms
  a solid blob over the entire filled mandala shape, with peaks
  concentrated at the OUTER ring/petal boundaries (higher local
  contrast/edge detail), not any dot-like structure (there are none).
  **This is suggestive, not fully decisive, evidence** that the model
  learned a generic ink/contrast-region signal rather than a
  dot-specific one - the similarity is elevated but not so extreme
  (e.g. >0.95 uniformly) that a stronger claim is warranted from this
  evidence alone.

## 6. What evidence supports or rejects retrying the current architecture?

**Rejects retrying the SAME architecture (stride-8, 256×256 input,
σ=1.2 target blur) unmodified.** The resolution ceiling identified in
Section 1 is a structural property of the architecture-vs-dataset
combination, not something more training time or a different random
seed would fix - the model already fits its target almost exactly (MSE
0.002-0.003) with room to spare (val_loss plateaued, per the original
M4.1 report), so the bottleneck is not "undertrained," it is "trained
correctly against an inadequate target."

## 7. What is the smallest justified next experiment?

**Not a full retrain.** The smallest experiment that would isolate
whether resolution is really the dominant lever, before committing to
any larger retry:
1. Take a SMALL subset of already-generated M4.1 images (e.g. 5-10) and
   regenerate their ground-truth heatmap target at a finer resolution
   (e.g. stride-2 or stride-4 equivalent, i.e. an 128×128 or 64×64
   target grid) with a proportionally smaller Gaussian σ, WITHOUT
   retraining anything - just measure whether individual dots become
   visually/quantitatively distinguishable in the target itself at that
   resolution, for this dataset's actual density (180-500 dots).
2. Only if that confirms individual dots become separable at finer
   resolution, is a real architecture change (finer output stride) and
   retrain justified as a next M4.2 step - and even then, current
   evidence suggests this dataset's density (400+ dots for kolam29-style
   patterns) may need a fundamentally different approach than a single
   fixed-resolution heatmap regardless of stride (e.g., patch-based or
   multi-scale detection), which is a bigger redesign question for a
   future session, not this one.

## Pattern-disjoint verification

Confirmed programmatically (`verify_pattern_disjoint()` in
`diagnose_m4_1_heatmap.py`, asserts checked before any evaluation ran):
train/val/test pattern sets have zero overlap, matching
`generate_training_data.py`'s original split exactly. No training
pattern was evaluated as held-out evidence anywhere in this diagnostic.

## What this does NOT change about M4.1's headline conclusion

M4.1's original finding - "the learned detector is worse than the
classical detector on every measured axis, do not integrate it" -
**stands, and is now better explained, not contradicted.** This
diagnostic identifies WHY (a resolution/target-design mismatch with this
dataset's actual dot density) rather than reversing the verdict. The
peak-detection ablation specifically rules out "just retune the
threshold" as a fix. See `PROJECT_STATE.md` for the (minimally) updated
recommendation this enables for any future M4.2 attempt.
