# M4.2 Model

Successor to M4.1's `DotHeatmapNet` (32×32 output, diagnosed and
rejected - see `PROJECT_STATE.md` sessions 13-15 and
`experiments/m4_1/diagnostics/`). This document describes
`experiments/m4_2/model.py`'s `DotHeatmapNetV2`.

## Why 128×128

`experiments/m4_1/diagnose_target_resolution.py` (session 15) measured,
directly and objectively (not assumed), that a Gaussian-blob dot target
recovers only 5-28% of true dots as distinguishable peaks at 32×32, for
this project's real dot-density range (180-500+ dots/image), while
128×128 recovers 100% for every density tested. Full evidence:
`experiments/m4_1/diagnostics/TARGET_RESOLUTION_REPORT.md`. M4.2 is the
first model built against that finding.

## Architecture

A small U-Net (encoder-decoder with skip connections) - **382,769
parameters**, native 128×128 output (not an upsampled 32×32):

```
input (1x256x256)
  -> enc1 (16ch, 256x256) ---------------------skip----------------+
  -> pool -> enc2 (32ch, 128x128) --------skip------+               |
  -> pool -> enc3 (64ch, 64x64) --skip--+           |               |
  -> pool -> bottleneck (96ch, 32x32)   |           |               |
  -> up1 -> concat(enc3) -> dec1 (64ch, 64x64) <-----+               |
  -> up2 -> concat(enc2) -> dec2 (32ch, 128x128) <-------------------+
  -> 1x1 conv head -> 1x128x128 heatmap logits
```

(enc1's own skip is not used - only enc2/enc3 feed the decoder, since
the decoder stops at 128×128 and never upsamples back to 256×256. See
`experiments/m4_2/model.py`'s `forward()` for the exact, authoritative
layer sequence - the diagram above is illustrative.)

Why NOT just upsample M4.1's 32×32 output to 128×128: upsampling a
coarse map cannot recover information that was never resolved in the
first place (M4.1's own architecture had no way to distinguish
individually-overlapping dots at 32×32 - see
`diagnostics/M4_1_HEATMAP_DIAGNOSIS.md`). The network must actually
compute at finer resolution, which requires a real decoder path with
skip connections carrying high-resolution detail back down from the
encoder - the defining architectural change from M4.1.

## Input / output contract

- Input: `Preprocessed.binary` (Otsu-binarized, deskewed mask - the
  same contract input M4.1 and the classical detector use, per
  `docs/ML_CONTRACT.md`), resized to `MODEL_INPUT_SIZE = 256`.
- Output: heatmap **logits** at `HEATMAP_SIZE = 128`
  (`OUTPUT_STRIDE = 2`). Callers apply `torch.sigmoid()` for a
  probability map, `BCEWithLogitsLoss` for training.
- Coordinate mapping: a point at original-image pixel `(px, py)` maps
  to heatmap cell `(px / fx / OUTPUT_STRIDE, py / fy / OUTPUT_STRIDE)`
  where `fx = original_width / MODEL_INPUT_SIZE`,
  `fy = original_height / MODEL_INPUT_SIZE` - identical scaling
  convention to M4.1, generalized to this model's own stride.

## Target generation

Gaussian blob per dot, `max`-combined (not summed - a dot's peak is
never diluted by a neighbor's), sigma **configurable**
(`SIGMA_CELLS = 1.2`, a plain module constant) - kept at the same value
`TARGET_RESOLUTION_REPORT.md` measured as sufficient for 100% recovery
at 128×128 across the full observed density range (180-500 dots), not
an arbitrary new guess.

## Training data

`experiments/m4_2/generate_training_data.py`: 135 source patterns (100
train / 15 val / 20 test), drawn from kolam19 (400 available) and
kolam29 (100 available). **kolam109 excluded** - measured directly
during Phase C to average ~6800-7000 dots/pattern (15-35× denser than
kolam19/29), recovering only 2.1% at 128×128 - a density regime never
validated at this resolution, so not silently included. Degradation
(`degrade_v3`) recalibrated against the FULL real-photo corpus's
measured gray-statistics distribution (22 photos, not just the 2
hardest M4.1 calibrated against) - generated median gray mean 124.6 vs.
real median 121.4, a close match, gentler than M4.1's `degrade_v2`.

Pattern-level disjoint train/val/test split (verified: zero pattern
overlap), disjoint seed ranges. 4 augmentation variants/pattern
(train), 3 (val/test): rotation, translation, scale, perspective,
brightness/contrast, blur, noise, JPEG re-encode, background tint,
dot/line-width variation.

## Peak extraction

`experiments/m4_1/peak_detect.py`'s `detect_peaks()`, reused
unmodified (resolution-agnostic). Parameters selected via
`experiments/m4_2/peak_sweep.py` on the VALIDATION set only (never
tuned against test) - selected values documented in
`experiments/m4_2/results/peak_sweep.json`.

## Serialization

`torch.save(model.state_dict(), ...)` →
`experiments/m4_2/results/dot_heatmap_net_v2.pt` - identical convention
to M4.1, no new format.

## Known environment requirement

Running this model's inference in the same process as
`engine.image_io`'s classical lattice-fit (`_fit_lattice_coords`,
MKL-linked `numpy.linalg.lstsq`) triggers a PyTorch/MKL OpenMP DLL
conflict (`OMP: Error #15`), first discovered in M4.1 and re-confirmed
during M4.2's API integration. `api/main.py` sets
`KMP_DUPLICATE_LIB_OK=TRUE` at import time as the permanent fix for the
API server process - verified in M4.1 not to silently corrupt output
for this workload before being relied on (see `PROJECT_STATE.md`
session 13). One-off scripts that combine both codepaths (tests,
evaluation scripts) must set this environment variable when invoked;
scripts that only ever touch one codepath do not need it.
