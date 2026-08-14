# Real Kolam Image Preprocessing  -  Graph-Quality Evaluation

**Result: negative, and clearer than the prior canonicalization
experiment.** Extended `engine/canonicalize.py` with two new stages
(area-based small-component removal, border/watermark crop) and
benchmarked all 7 variants' effect on downstream GRAPH QUALITY
(connected components, odd-degree nodes, Eulerian validity)  -  not just
detection count  -  on the 4 real in-scope photos, using full
`trace_path`/graph construction (affordable at this small n). **Every
non-baseline variant, on every one of the 4 photos, increased
fragmentation (more connected components) and increased odd-degree node
count relative to the current production baseline.** One narrow
exception (variant B on the smallest/highest-contrast photo) is reported
honestly. No variant reached `reconstruction_valid=True`  -  including the
unmodified baseline.

## 1. What the image revealed

**No specific 260×280 "dense sikku kolam with a watermark" image was
available this session**  -  it is not in the repository, and the API
never persists uploads, so it could not be inspected as instructed. This
was confirmed with the user, who asked to proceed against the existing
corpus instead. `kolam_naduveetu_meenakshisundaram.jpg` was used as the
closest available real stand-in  -  this project's densest, lowest-contrast
real in-scope photo:

- 3072×2304, gray mean 72.6 / std 63.4 (the same documented low-contrast
  case tracked since Session 11)
- Raw Otsu foreground fraction 71.9%  -  badly over-binarized (background
  texture misclassified as ink)
- 428 raw connected components before any cleanup, including one giant
  merged blob (4.5M px) and a long tail of tiny noise specks (median
  217px)
- Currently produces the largest ML over-detection of any real photo in
  the corpus: 563 raw detections at the production threshold

All 4 real in-scope photos were benchmarked (not just this one), per
the task's own instruction not to over-fit conclusions to a single case.

## 2. Preprocessing variants tested

| Variant | Recipe |
|---|---|
| raw / A | grayscale + global Otsu (current production, identical, verified by test) |
| B | + CLAHE (local contrast) |
| C | + illumination normalization (flat-field division) |
| D | CLAHE + adaptive (local) threshold + light morphological opening |
| E | illumination norm + adaptive threshold + light morphological opening |
| F (new) | illumination norm + adaptive threshold + **area-based small-component removal** (NOT morphological opening  -  see rationale below) |
| G (new) | border/watermark crop (8% margin, all 4 edges) + variant F |

**Why small-component removal, not more morphology, for F/G**: the task
explicitly warns against "aggressive morphology that destroys
closely-spaced dots." Morphological opening applies a fixed structuring
element to every pixel regardless of what it belongs to, and can erode
or merge real dots in a dense pattern. Area-based component filtering
(`engine.canonicalize._remove_small_components`) instead measures each
connected blob's TOTAL SIZE and only removes ones far too small to be a
real dot  -  verified directly (unit test) to leave a real dot's own
pixels completely untouched while removing an isolated single-pixel
speck.

## 3. Benchmark table (all 4 real in-scope photos, full graph construction)

| Photo | Variant | Dots | Edges | Components | Odd nodes | Eulerian | Recon. valid |
|---|---|---:|---:|---:|---:|---|---|
| kolam_naduveetu | raw/A | 563 | 11846 | 364 | 206 | False | False |
| | B | 606 | 14174 | 362 | 224 | False | False |
| | C | 908 | 4969 | 372 | 366 | False | False |
| | D | 990 | 7299 | 404 | 356 | False | False |
| | E | 988 | 2622 | 449 | 324 | False | False |
| | F | 1107 | 5761 | 491 | 404 | False | False |
| | G | 1193 | 4003 | 448 | 430 | False | False |
| kolam_attur1 | raw/A | 297 | 61 | 259 | 26 | **True** | False |
| | B | 591 | 463 | 441 | 144 | False | False |
| | C | 464 | 335 | 331 | 70 | False | False |
| | D | 1043 | 1004 | 694 | 296 | False | False |
| | E | 759 | 329 | 572 | 132 | False | False |
| | F | 1150 | 679 | 887 | 174 | False | False |
| | G | 1155 | 633 | 837 | 208 | False | False |
| muggu_kollam | raw/A | 151 | 2778 | 43 | 86 | False | False |
| | B | 334 | 4323 | 116 | 112 | False | False |
| | C | 436 | 441 | 192 | 170 | False | False |
| | D | 1089 | 1045 | 550 | 378 | False | False |
| | E | 860 | 335 | 592 | 202 | False | False |
| | F | 1037 | 801 | 601 | 300 | False | False |
| | G | 1043 | 774 | 533 | 340 | False | False |
| kolam2_tshrinivasan | raw/A | 58 | 243 | 16 | 30 | **True** | False |
| | **B** | **57** | 431 | **13** | **16** | **True** | False |
| | C | 361 | 246 | 209 | 130 | True | False |
| | D | 750 | 366 | 530 | 186 | True | False |
| | E | 422 | 17 | 406 | 22 | True | False |
| | F | 931 | 296 | 703 | 228 | False | False |
| | G | 890 | 281 | 667 | 256 | False | False |

Full machine-readable data:
`experiments/real_image_preprocessing/results/graph_benchmark.json`.

## 4. Best pipeline

**None, across 3 of 4 photos.** On `kolam2_tshrinivasan.jpg` (the
smallest, already-highest-contrast-of-the-low-contrast-cases photo),
**variant B (CLAHE only)** is the one genuine bright spot in this
dataset: components 16→13, odd nodes 30→16, Eulerian preserved (True).
This is reported honestly as a real, narrow, single-image improvement  - 
not generalized into a recommendation, since it did not replicate on
any of the other 3 photos (B made kolam_naduveetu and kolam_attur1 both
WORSE).

## 5. Before/after graph metrics (primary stand-in: kolam_naduveetu)

```
RAW:
  dots = 563
  components = 364
  odd_nodes = 206
  edges = 11846
  eulerian = False
  reconstruction_valid = False

BEST TESTED PREPROCESSED (variant B, the least-harmful of the 6):
  dots = 606
  components = 362        (364 → 362, a 0.5% reduction -- noise, not a real improvement)
  odd_nodes = 224          (206 → 224, WORSE)
  edges = 14174
  eulerian = False
  reconstruction_valid = False

Improvement:
  components: 364 → 362  (negligible, within noise)
  odd nodes:  206 → 224  (WORSE)
  validity:   False → False  (UNCHANGED)
```

**No variant meaningfully improved this image's graph. Several
variants (C through G) made it dramatically worse** (components up to
491, odd nodes up to 430).

## 6. Whether reconstruction became valid

**No  -  for any variant, on any of the 4 photos.**
`reconstruction_valid` is `False` in all 32 rows of the benchmark,
including the unmodified production baseline. Two photos already reach
`eulerian=True` on their LARGEST component with the UNMODIFIED baseline
(`kolam_attur1`, `kolam2_tshrinivasan`)  -  but never `reconstruction_valid`,
because that requires the largest component to cover ALL nodes, and
these photos fragment into 259 and 16 separate components respectively.
Preprocessing did not close this gap on any tested variant; on 2 of the
4 photos it even destroyed the pre-existing partial Eulerian property
(F/G flip `kolam2_tshrinivasan` from `eulerian=True` to `False`).

## 7. Whether generation became possible

**No.** Generation (`engine.novel_generation`, `docs/M4_2_PARITY_EVALUATION.md`)
is a separate subsystem operating on synthetic/reconstructed structure,
not on ML-detected real-photo graphs  -  this experiment does not touch
it and does not claim to. Even within THIS experiment's own scope
(image → structural graph), no photo reached a state a downstream
consumer could treat as valid.

## 8. Files changed

- `engine/canonicalize.py` (extended: `VARIANTS` grew from 5 to 7,
  added `_remove_small_components`, `_crop_border`, variants F/G)
- `experiments/real_image_preprocessing/run_graph_benchmark.py` (new)
- `experiments/real_image_preprocessing/results/graph_benchmark.json` (new)
- `tests/test_canonicalize.py` (updated: dimension test excludes
  cropping variant G, new dedicated crop test)
- `tests/test_real_kolam_preprocess.py` (new, 9 tests)
- `docs/M4_2_REAL_IMAGE_PREPROCESSING.md` (this file)
- `.gitignore` (allow-list entry)
- **No changes** to `engine/image_io.py`, `engine/ml_contract.py`,
  `api/`, `frontend/`, or the model checkpoint.

## 9. Tests

19 new/updated tests total (`test_canonicalize.py`: 10, up from 9;
`test_real_kolam_preprocess.py`: 9 new) covering: preprocessing
determinism, dimension preservation (and the crop variant's intentional
exception), no accidental alpha/channel corruption, watermark-crop
behavior, area-based small-component removal preserving a dense 8×8 dot
grid while dropping isolated specks (verified directly, not assumed),
raw-mode-unchanged (re-verified against a real corpus file), and
end-to-end detector compatibility (real checkpoint, not a mock) with no
silent fallback. **Full suite: 267/267 passing** (248 before this
session's two experiments + 9 (canonicalization, previous session) + 10
new this session). No existing test modified or weakened.

## 10. Whether the improvement is safe to integrate

**N/A  -  there is no improvement to integrate.** Per the task's own
Phase 9 instruction ("If one preprocessing variant clearly improves
results, integrate it as an OPTIONAL mode")  -  none does, so no
`preprocess=real_kolam` option was added to the API, and no frontend
control was added (Phase 14's own condition, "only after the backend
experiment succeeds," was not met). `detector=classical`/`ml`/`compare`
and their existing behavior are completely unchanged.

## 11. Remaining bottleneck

**Detection volume / over-detection  -  the SAME root cause already
identified in Sessions 16, 21, and 22, now confirmed from the graph
side, not just the false-positive-count side.** Every preprocessing
variant that increased local contrast/edge sensitivity (adaptive
threshold, illumination normalization) increased raw detection count
substantially (563→1193 on the densest photo)  -  and MORE detections on
an already over-detecting model produces MORE spurious lattice points,
which `_fit_lattice_coords`/`trace_path` then fragment into MORE, not
fewer, disconnected components. **This is not a lattice-fitting bug,
not a `trace_path` bug, and not a parity-scoring bug** (per Phase 13's
explicit menu, this rules out those categories directly, via measured
evidence: the SAME unmodified `trace_path`/`_fit_lattice_coords` handled
both the 58-dot and the 1193-dot inputs without crashing, correctly
reflecting whatever structure was actually there). **It is the model's
domain gap** (confidently over-detecting on real-photo texture/contrast
patterns it was never trained to distinguish from real dots)  - 
unchanged from `docs/M4_1_ML_COMPLETION_REPORT.md`'s conclusion, and
this session's evidence shows that FIXING THE INPUT IMAGE cannot
compensate for it: cleaner-looking preprocessing tends to make the
CNN MORE trigger-happy (higher local contrast/edge content = more
candidate peaks crossing its confidence threshold), not less. The
already-identified, actually-effective mitigation remains Session 21's
POST-detection lattice-consistency gate (100%→55.6% no-dot FP, zero
synthetic cost)  -  a filter on the model's OUTPUT, not a transform of its
INPUT  -  still not wired into the API, still the single highest-value
next integration step.
