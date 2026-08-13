# M4.1.2 Target Resolution Representation Check

Pure representation experiment — no CNN, no checkpoint, no torch, no
retraining, no dataset expansion. Follows up M4.1.1
(`diagnostics/M4_1_HEATMAP_DIAGNOSIS.md`), which found the trained
model's 32×32 heatmap matches its own training target almost exactly
(MSE 0.002–0.003) and that the TARGET itself — not the model, not
`peak_detect.py` — loses individual-dot identity at this dataset's real
density. This experiment asks, in isolation from any model: **at what
heatmap resolution do the actual ground-truth dot coordinates become
individually separable under the existing Gaussian-blob target
encoding?**

Full machine-readable results: `experiments/m4_1/diagnostics/target_resolution_report.json`.
Visualizations (reproducible, not committed as a rule but present on
disk): `experiments/m4_1/diagnostics/target_resolution_viz/`.

## Method

1. Surveyed **every already-generated ground-truth JSON** in the
   project (`experiments/m4_1/data/{train,val,test}/`,
   `synthetic_photos/`, `synthetic_photos_heldout/` — 179 files, no new
   images generated). Found the corpus's actual density range: **180 to
   500 dots per image**, with a **bimodal gap** — kolam19-based images
   cluster 180–224 dots, kolam29-based images cluster 444–500 dots,
   nothing in between. This gap is a property of the existing dataset,
   not something this experiment could fill without generating new data
   (explicitly out of scope).
2. Selected 3 representative images from what already exists:
   `kolam19_k280_v0` (180 dots, lowest available), `kolam19_k180_v5`
   (208 dots, mid), `kolam29_k45_v3` (500 dots, highest available).
3. For each, reimplemented the target-heatmap construction **locally in
   the diagnostic script** (not modifying `model.py`/`train.py`),
   mirroring their exact coordinate-scaling and Gaussian-blob logic
   (max-combination, not sum), generalized to resolutions 32×32, 64×64,
   128×128, 256×256. Sigma held fixed at **1.2 heatmap-cells** — the
   exact value `experiments/m4_1/model.py` uses at 32×32 — across every
   resolution tested, to isolate "does resolution alone help" from "did
   we also change the blur convention."
4. Measured, objectively (not visually): local-maxima count (3×3
   neighborhood max, threshold 0.2), nearest-neighbor spacing in
   cell-units, the ratio of that spacing to sigma, percentage of dots
   with a neighbor within 2σ/3σ, and literal cell-collision count
   (dots whose rounded integer cell coincides with another's).

## Results

| image | n_dots | resolution | local maxima | local-max/n_dots | median NN/σ | % within 2σ | % within 3σ | % cell-collided |
|---|---|---|---|---|---|---|---|---|
| kolam19_k280_v0 | 180 | 32 | 50 | 0.28 | 0.87 | 100.0 | 100.0 | 6.1% |
| kolam19_k280_v0 | 180 | 64 | 155 | 0.86 | 1.73 | 84.4 | 100.0 | 0.0% |
| kolam19_k280_v0 | 180 | **128** | **180** | **1.00** | 3.46 | 0.0 | 0.0 | 0.0% |
| kolam19_k280_v0 | 180 | 256 | 180 | 1.00 | 6.93 | 0.0 | 0.0 | 0.0% |
| kolam19_k180_v5 | 208 | 32 | 52 | 0.25 | 0.97 | 100.0 | 100.0 | 3.8% |
| kolam19_k180_v5 | 208 | 64 | 178 | 0.86 | 1.94 | 92.3 | 100.0 | 0.0% |
| kolam19_k180_v5 | 208 | **128** | **208** | **1.00** | 3.88 | 0.0 | 0.0 | 0.0% |
| kolam19_k180_v5 | 208 | 256 | 208 | 1.00 | 7.76 | 0.0 | 0.0 | 0.0% |
| kolam29_k45_v3 | 500 | 32 | 26 | 0.05 | 0.58 | 100.0 | 100.0 | **28.2%** |
| kolam29_k45_v3 | 500 | 64 | 146 | 0.29 | 1.17 | 100.0 | 100.0 | 0.0% |
| kolam29_k45_v3 | 500 | **128** | **500** | **1.00** | 2.34 | 0.0 | 94.8 | 0.0% |
| kolam29_k45_v3 | 500 | 256 | 500 | 1.00 | 4.67 | 0.0 | 0.0 | 0.0% |

("local-max/n_dots" = 1.00 means the target heatmap has exactly one
distinguishable peak per true dot — full recoverability, in the ideal
noise-free target itself, before any model or peak detector is
involved.)

## A. At what resolution do individual dots become spatially separable?

**128×128** is the first resolution where local-maxima count exactly
equals the true dot count for every density tested (180, 208, AND 500
dots) — visually confirmed too
(`target_resolution_viz/kolam29_k45_v3.png`: 32×32 and 64×64 are
solid/mottled blobs with no visible individual dots; 128×128 shows
individually distinguishable points; 256×256 is crisp and clean).

## B. Is 32×32 fundamentally incapable of representing the current dot density?

**Yes, confirmed quantitatively, not assumed.** At 32×32 the target
heatmap recovers only **25-28% of true dots** as distinct local maxima
for kolam19-density patterns (50/180, 52/208) and a mere **5%** for the
densest kolam29 pattern (26/500) — with 28.2% of that pattern's dots
literally colliding into the same integer cell. This is an information
ceiling in the TARGET ITSELF, independent of any model or training
choice — no amount of retraining the current 32×32 architecture could
exceed it.

## C. Is 64×64 sufficient, or is 128×128 required?

**64×64 is a large improvement but not sufficient across the full
observed density range; 128×128 is required.** At 64×64, kolam19-density
patterns recover 86% of dots as distinct maxima (155/180, 178/208) —
better, still incomplete, and still 84-92% of dots have a neighbor
within 2σ (crowded). At 64×64 the densest kolam29 pattern recovers only
**29%** (146/500) — clearly insufficient. 128×128 recovers 100% for
every density tested.

## D. What target sigma would be reasonable at the candidate resolution?

At 128×128 with the current σ=1.2 cells: kolam19-density patterns are
fully separated with wide margin (0% within even 3σ). The densest
kolam29 pattern reaches 100% local-maxima recovery (every dot gets its
own peak) but **94.8% of dots still have a neighbor within 3σ** — blobs
touch/overlap at the edges even though each has a distinguishable
center. Two reasonable options, not a single forced answer: **(a)** keep
σ=1.2 at 128×128 (sufficient for peak COUNT, tighter margin for
peak SEPARATION on the densest patterns) or **(b)** move to 256×256,
which reaches 0% within-3σ for every density tested at the SAME σ=1.2 —
a more comfortable margin without needing to shrink sigma at all. This
experiment does not select between them; it reports both are
evidence-supported, with 256×256 being the safer choice if compute
allows.

## E. Does this evidence justify changing the architecture/output stride?

**Yes.** The current architecture's actual output resolution (32×32,
stride-8) recovers only 5-28% of ground-truth dots as distinguishable
target peaks in the ideal, noise-free target itself — before any CNN
imperfection, training data limitation, or peak-detector tuning enters
the picture. This is a hard ceiling that no amount of retraining the
current architecture can exceed, directly corroborating M4.1.1's
diagnosis. Moving to at least 128×128 (a 4× finer output grid than
today) is justified by direct, objective measurement — not speculation.

## Explicit answers required by the task

- **A**: 128×128 (first resolution with exact local-maxima/dot-count
  match across the full observed density range).
- **B**: Yes — 32×32 is fundamentally incapable (5-28% recovery, up to
  28.2% literal cell collisions).
- **C**: 64×64 is insufficient (29-86% recovery, density-dependent);
  128×128 is required for full separability.
- **D**: σ=1.2 cells works at 128×128 for peak COUNT everywhere tested;
  256×256 gives more separation margin at the same σ for the densest
  patterns. Not resolved to one answer — both reported.
- **E**: Yes, justified by direct measurement, not by assumption or by
  a wish to retry a CNN — the current 32×32 architecture has a hard,
  measured information ceiling.

## What this does NOT do

This experiment does not retrain anything, does not select a production
resolution, does not touch the classical detector, `trace_path`, or the
frozen ML contract, and does not conclude a CNN retry is guaranteed to
succeed even at 128×128 — it establishes only that the REPRESENTATION
(target encoding) could in principle support individual-dot recovery at
128×128+, which is a necessary but not sufficient condition for a future
learned detector to work. Whether a small CNN could actually learn to
predict such a target well is a separate, unanswered question requiring
an actual training experiment this task explicitly does not authorize.
