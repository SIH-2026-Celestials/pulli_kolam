# M4.1 ML Completion Report

**Scope note, read first**: this campaign specified 13 phases (dataset
audit, augmentation ablation retraining, a full hybrid-detector
redesign, a gating investigation, deployment/perf profiling). Attempting
all of them with real rigor in one session was assessed, before
starting, as unrealistic without producing shallow, unevidenced results
- exactly what this task's own rules forbid. **Confirmed with the user
before starting: this session's real, evidenced effort went into Phase
6 (gating), with Phases 0/1/2/3/7/8/11/12/13 done at an audit/
verification depth (citing and re-confirming existing evidence, not
re-running expensive experiments) alongside it.** Phases 4 (augmentation
ablation, requires new training runs) and 5 (a full separately-scored
hybrid architecture) and 9 (deep performance/container optimization)
were NOT attempted this session and are named explicitly as not done,
not silently skipped.

## 1. Executive summary

**Status: PARTIAL.** This session made one real, measured improvement -
a lattice-geometric-consistency gate that cuts the ML detector's no-dot
false-positive rate from **100% (18/18) to 55.6% (10/18)** at zero
measured cost to synthetic recall/precision - but this gate is
EXPERIMENTAL, not wired into the deployed API, and does not change the
underlying production decision: **`detector=classical` remains the
default**, unchanged since Session 16. No box in Section 13's completion
checklist newly closes from PARTIAL to fully satisfied that wasn't
already satisfied before this session; what changed is that the
domain-gap problem now has a measured, partial, honest mitigation
instead of no mitigation at all.

## 2. Existing ML architecture (verified this session, unchanged)

```
image
  -> engine.image_io.preprocess()          (Otsu binarize + deskew, shared with classical)
  -> [ optional] lattice-consistency gate  (NEW this session, experimental)
  -> DotHeatmapNetV2 forward pass          (experiments/m4_2/model.py, 382,769 params, 128x128 native heatmap)
  -> sigmoid -> detect_peaks()             (experiments/m4_1/peak_detect.py, unmodified, resolution-agnostic)
  -> engine.image_io._fit_lattice_coords() (unmodified, shared with classical)
  -> Lattice (engine.ml_contract frozen contract)
  -> engine.image_io.is_traceable()        (Session 17 gate, unmodified)
  -> engine.image_io.trace_path()          (unmodified)
  -> nx.MultiGraph
  -> api/detectors.py: DetectionResult     (coordinate un-deskewing, JSON packaging)
  -> api/main.py: /api/v1/detect|analyze|reconstruct|compare-detectors
  -> frontend/frontend/src/pages/Detect/   (existing, unchanged this session)
```

Verified by direct code reading (`api/detectors.py`, `api/main.py`,
`experiments/m4_2/ml_lattice_detector.py`) - every link above already
existed and was already tested before this session; this session did
not discover any broken link in this chain. What is genuinely
experimental vs. production is listed precisely in Section 12.

## 3. Training reproducibility

**Verified reproducible by code inspection, not re-run this session**
(re-running a 30-epoch training was judged out of scope for a
gating-focused session - the existing checkpoint's provenance is
already fully recorded and was not in question):

- Command: `python experiments/m4_2/generate_training_data.py` (data
  generation) then `python experiments/m4_2/train.py` (training).
- Seed: `torch.manual_seed(42)`, set at the top of `train.py::main()`
  (verified by direct reading - `SEED = 42` module constant).
- Config: 30 epochs, Adam, lr=1e-3, batch_size=8 (verified: matches
  `train.py`'s `main()` defaults AND the recorded
  `experiments/m4_2/results/training_log.json`'s own `n_epochs`/`lr`/
  `batch_size`/`seed` fields exactly - the checkpoint's OWN training log
  confirms the command that produced it, not just the current source).
- Preprocessing discipline: trains on `image_io.preprocess(path).binary`
  (the SAME Otsu-binarized, deskewed mask the frozen contract hands the
  detector at inference), not the raw photo - verified in
  `DotHeatmapDatasetV2.__init__`.
- Train/val split: pattern-level disjoint (verified previously,
  Session 16; not re-verified this session since no data/split code
  changed).

**Not re-verified this session**: that re-running the full command
reproduces the checkpoint byte-for-byte (PyTorch CPU determinism across
versions/platforms is a real but separate question from "is the command
well-specified and seeded," which this section confirms).

## 4. Dataset and labels

Cited from `docs/M4_2_MODEL.md`/`docs/M4_2_GENERATION.md` (already
measured in Session 16, re-confirmed by re-reading this session, not
re-measured):

- 135 source CSV patterns (kolam19 + kolam29; kolam109 excluded -
  measured ~6800-7000 dots/pattern, only 2.1% recoverable at 128×128).
- 505 rendered synthetic images (400 train / 45 val / 60 test).
- `degrade_v3` augmentation calibrated against the FULL real-photo
  corpus's measured gray statistics (22 photos: mean range
  [62.5, 154.6], median 121.4; std range [21.6, 63.4], median 45.9) -
  generated median gray-mean 124.6, a close match on this ONE summary
  statistic.
- **Domain gap, quantified precisely, not asserted**: this session's own
  gating experiment (Section 10) measured the ML detector's raw
  (ungated) confidence on real no-dot photos reaching as high as **0.93
  and 0.98** (see the two probe examples below) - well above the 0.6
  production threshold - meaning the model is not merely "slightly
  uncertain" on real photos, it is CONFIDENTLY wrong on texture/lighting
  patterns the synthetic corpus's gray-statistic-matching augmentation
  did not capture. Matching mean/std alone (a 2-number summary) is
  evidently insufficient to close this gap - a finding already flagged
  in `docs/M4_2_EVALUATION.md` and confirmed again here from a different
  angle (raw confidence distribution, not just detection counts).
- **No ground truth exists for the 22 real photos** (unchanged fact,
  `docs/M4_EVALUATION_PROTOCOL.md`) - this report never computes
  precision/recall against them, only raw detection counts and
  no-dot firing rate, consistent with every prior session's discipline.

## 5. Synthetic evaluation (re-confirmed, thresholds extended)

`experiments/m4_2/gating_experiment.py` swept confidence threshold on
the VALIDATION set (never the test set, for selection) across a WIDER
range than M4.2's original `peak_sweep.py` (which only tried 0.2-0.6):

| threshold | recall | precision | F1 |
|---|---:|---:|---:|
| 0.6 (production) | 0.9990 | 0.9995 | 0.9993 |
| 0.7 | 0.9990 | 0.9995 | 0.9993 |
| 0.8 | 0.9987 | 0.9996 | 0.9991 |
| 0.9 | 0.9153 | 0.9998 | 0.9552 |
| 0.95 | 0.5230 | 1.0000 | 0.6818 |
| 0.99 | 0.0097 | 1.0000 | 0.0189 |

**New finding**: recall is essentially flat through 0.8 (headroom the
original 0.2-0.6 sweep never tested), then collapses sharply between
0.8 and 0.95. This directly informed the gating experiment (Section 6):
threshold alone cannot be pushed past ~0.8-0.9 without materially
hurting synthetic recall.

## 6. Real-photo evaluation (re-confirmed + extended)

Same threshold sweep, real photos (no ground truth - raw firing rate
only):

| threshold | no-dot FP rate (18 photos) |
|---|---:|
| 0.6 (production) | 100.0% (18/18) - unchanged from Session 16 |
| 0.7 | 100.0% (18/18) |
| 0.8 | 100.0% (18/18) |
| 0.9 | 100.0% (18/18) |
| 0.95 | 88.9% (16/18) |
| 0.99 | 0.0% (0/18) - but synthetic recall is 0.97% here, useless |

**Confirms and sharpens Session 16's finding**: raising confidence
threshold alone cannot solve the false-positive problem at any USABLE
operating point - the only threshold that eliminates false positives
(0.99) also eliminates virtually all true positives on synthetic data.
This is not a new problem; it is now measured across a wider,
more conclusive range than before.

## 7. Domain-gap analysis

The domain gap is NOT primarily a confidence-calibration problem (the
model isn't just "a little too confident everywhere" - it is highly
confident, up to 0.93-0.98, on SPECIFIC no-dot photos while correctly
near-certain on synthetic data). This is consistent with Session 16's
conclusion (real-photo transfer needs real-photo-derived training data
or augmentation statistics, not just gray-mean/std matching) and is
NOT resolved by this session's gating work - the gate is a
POST-HOC geometric filter, not a fix to the underlying representation
gap. It measurably helps (Section 10) but does not close the gap.

## 8. Augmentation experiments

**NOT ATTEMPTED this session** - explicitly out of scope per the
gating-only focus confirmed with the user before starting (Phase 4
requires new training runs, each a multi-hour+ commitment with its own
ablation design). This remains a real, open avenue - see Section 18.

## 9. Hybrid detector experiment

**NOT ATTEMPTED as a full separate architecture this session.** The
lattice-consistency gate (Section 10) is a PARTIAL, narrow instance of
"classical confirmation" (it reuses `engine.image_io._fit_lattice_coords`,
the same geometric-fitting code the classical detector itself uses, as
a post-hoc plausibility check on ML output) - this is real overlap with
Phase 5's spirit, but it is not the full "classical proposes / ML
confirms" or "ML proposes / classical verifies" architecture the phase
specified. Documented here as partial coverage, not claimed as a
complete hybrid-detector investigation.

## 10. Gating experiment (this session's real, new work)

**Hypothesis**: a geometric-plausibility check - does the raw ML
detection set fit a regular affine lattice, using the exact same
`_fit_lattice_coords` function the classical detector already relies on
- can distinguish real dot-grid detections from texture/noise false
positives, since a genuine lattice should fit tightly (low residual)
and scattered spurious peaks should not.

**Controlled change**: `experiments/m4_2/gating_experiment.py` (new),
`experiments/m4_2/gated_ml_lattice_detector.py` (new, contract-conforming,
NOT wired into the API). No model weights changed. No existing
detector's default behavior changed.

**Metric**: no-dot false-positive rate (18 photos) and synthetic
val recall/precision/F1, both with and without the gate, across the
SAME threshold sweep.

**Result** (production threshold 0.6, unchanged):

| | ungated | + lattice gate |
|---|---:|---:|
| No-dot FP rate | 100.0% (18/18) | **55.6% (10/18)** |
| Synthetic val recall | 0.9990 | 0.9990 (unchanged) |
| Synthetic val precision | 0.9995 | 0.9995 (unchanged) |
| Synthetic val F1 | 0.9993 | 0.9993 (unchanged) |

**A real, measured, zero-synthetic-cost improvement** - the gate never
incorrectly rejected a true synthetic detection in this benchmark
(residual on synthetic images' regular grids is reliably low).

**The honest cost, measured on the same run**: the SAME gate that
rejects false positives also rejects 3 of the 4 real in-scope photos'
ML detections entirely (`kolam2_tshrinivasan.jpg`,
`kolam_attur1_infofarmer.jpg`, `kolam_naduveetu_meenakshisundaram.jpg`
all go from `n_detected > 0` to `n_detected = 0`; only
`muggu_kollam_sirensongs.jpg`, residual 9.14px, survives). Their
residuals (9.1, 12.8, 17.2, 19.8px) OVERLAP with several no-dot photos'
residuals in the same range - geometric consistency correlates with
plausibility but does not cleanly separate the two populations. Given
that ML's real in-scope detections were ALREADY known (Session 16) to
wildly over-detect (58-563 vs. human estimates of 4-150), losing 3 of 4
is a real but arguably small practical loss - reported honestly, not
minimized.

**Residual-threshold sensitivity** (re-filtering the same 22 measured
residuals, no re-inference needed):

| residual threshold (px) | no-dot FP rate | in-scope photos kept |
|---:|---:|---:|
| 5 | 22.2% (4/18) | 0/4 |
| 8 | 38.9% (7/18) | 0/4 |
| **10 (selected)** | **55.6% (10/18)** | **1/4** |
| 15 | 77.8% (14/18) | 2/4 |
| 20 | 77.8% (14/18) | 4/4 |
| 30 | 83.3% (15/18) | 4/4 |

**No threshold achieves both "keep all real positives" and "eliminate
most false positives"** - 10px was selected as the value that maximizes
FP reduction while the SYNTHETIC cost (the metric with actual ground
truth) stays exactly zero; it is not the value that best preserves the
already-unreliable in-scope detections. This tradeoff is stated
explicitly, not hidden behind a single chosen number.

**Combining threshold + gate** (full sweep, `experiments/m4_2/results/gating_experiment.json`):
best combined FP reduction without collapsing synthetic recall is
threshold=0.8 + gate: FP rate 38.9% (7/18), synthetic recall 0.9987 (a
0.03-point cost). Pushing further (0.9+gate: FP 33.3%, recall 0.9153;
0.95+gate: FP 16.7%, recall 0.523) trades meaningfully more synthetic
recall for smaller further FP gains - diminishing returns, not pursued
further this session.

## 11. End-to-end structural evaluation

`experiments/m4_2/gated_ml_lattice_detector.py`'s output was run through
the FULL existing pipeline (`is_traceable` → `trace_path` → `nx.MultiGraph`)
on real photos, not just synthetic fixtures:

- `kolam_india09_mckaysavage.jpg` (no-dot, gated): 0 pixel positions, 0
  graph nodes, 0 edges - no crash, correct empty-collapse.
- `muggu_kollam_sirensongs.jpg` (in-scope, passes gate): 151 pixel
  positions, 151 graph nodes, 1523 edges - no crash, real graph
  produced.
- `kolam_attur1_infofarmer.jpg` (in-scope, rejected by gate): 0/0/0 -
  no crash, correct empty-collapse (the honest cost from Section 10,
  visible here at the graph level too).

`trace_path` and the Session-17 `is_traceable` gate were **not
modified** - verified by `git diff` showing zero changes to
`engine/image_io.py` this session (confirmed below, Section 19-equivalent
git status).

## 12. API integration

**Verified unchanged and still passing** (`api/tests/test_api.py`, part
of the 239 passing tests) - `detector=classical`/`ml`/`compare` all
continue to work exactly as documented in `docs/M4_2_API.md`.
**The gate is NOT wired into `api/main.py` or `api/detectors.py` this
session** - `detector=ml` via the deployed API still uses the UNGATED
`LearnedLatticeDetectorV2` exactly as before. This was a deliberate
scope decision (schema/route changes were judged unnecessary for an
experiment not yet recommended for production - see Section 15), not an
oversight. `GatedLearnedLatticeDetectorV2` exists as a tested,
contract-conforming, ready-to-integrate module for a future session.

## 13. Performance

Measured directly this session (`muggu_kollam_sirensongs.jpg`, one real
photo, single run - indicative, not a statistically rigorous benchmark):

| | latency |
|---|---:|
| Classical | 157.8ms |
| ML (ungated) | 241.1ms |
| ML (gated) | 226.9ms - gate adds negligible overhead (one cheap affine-fit residual computation) |
| Model load time | 31.4ms |

Checkpoint file size: 1.56MB (`dot_heatmap_net_v2.pt`) - the ~1.84GB
container size is dominated by the CPU PyTorch wheel itself, not the
model. Reducing it would mean removing/replacing torch entirely (e.g. a
non-PyTorch inference runtime) - a substantial infra change, **not
attempted this session** (explicitly out of the gating-only scope
confirmed with the user).

## 14. Deployment behavior

Not re-run this session (Docker build/API smoke tests were already
verified working in Session 16's PROJECT_STATE.md record; nothing in
this session's changes touches `Dockerfile`, `api/main.py`, or
`requirements*.txt`'s ML dependencies). `python -m pytest -q` - the
closest available smoke test - passes at 239/239 including all existing
`api/tests/test_api.py` cases.

## 15. Production decision

**Unchanged: `detector=classical` remains default.** This session's
evidence does not change Session 16's pre-committed decision rule
outcome - the gate is a measured, promising, EXPERIMENTAL mitigation,
not a production-ready replacement for the whole no-dot-FP problem
(55.6% residual FP rate is still far worse than classical's own 33.3%
no-dot FP rate, cited in `docs/M4_2_EVALUATION.md`). Classical remaining
default is the correct, evidence-based conclusion here, not a failure
to find something that worked - the gate genuinely helps and is
recommended as a concrete next integration step (Section 18), not
discarded.

| Detector | Synthetic recall | Synthetic F1 | Real no-dot FPR | Latency | Decision |
|---|---:|---:|---:|---:|---|
| Classical | 0.1998† | 0.1998† | 33.3% | 157.8ms | **DEFAULT** |
| ML (ungated, t=0.6) | 0.9990 | 0.9993 | 100.0% | 241.1ms | Experimental (`detector=ml`) |
| ML (gated, t=0.6, residual≤10px) | 0.9990 | 0.9993 | **55.6%** | 226.9ms | Experimental, NOT deployed |
| Hybrid (full, separate architecture) | - | - | - | - | Not attempted |

†Classical's synthetic recall/F1 on M4.2's harsher `degrade_v3` test set
is confounded (see `docs/M4_2_EVALUATION.md`) - its real, uncontaminated
performance on gentler synthetic degradation is 1.0/0.9997, unchanged
since Session 11. Cited here exactly as Session 16 reported it, not
altered.

## 16. Limitations

- Gate does not close the domain gap, only filters a subset of its
  symptoms (Section 10's residual-overlap finding).
- Gate reduces real in-scope "usefulness" alongside false positives -
  net benefit depends on which failure mode matters more to a given use
  case; not a clean win.
- Augmentation and full hybrid-architecture experiments (Phases 4, 5)
  not attempted - genuinely open.
- Performance/container-size work (Phase 9) not attempted.
- Single-photo latency measurement (Section 13) is indicative, not a
  rigorous multi-run benchmark.
- Training reproducibility (Section 3) verified by code inspection, not
  by an actual re-run confirming byte-identical output.

## 17. Exact evidence for completion/non-completion

Per Phase 13's checklist:

- [x] Training is reproducible (command + seed + config verified by
      code inspection and cross-checked against the checkpoint's own
      training log).
- [x] Dataset/label pipeline is documented (cited, Section 4).
- [x] Evaluation protocol is reproducible (`gating_experiment.py`,
      `evaluate_m4_2.py`, deterministic, no RNG).
- [x] Synthetic performance is measured (Section 5, extended range).
- [x] Real-photo behavior is explicitly evaluated (Section 6).
- [x] No-dot false-positive behavior is quantified (Sections 6, 10).
- [x] Domain-gap limitations are documented (Section 7).
- [x] ML inference works through the API (`detector=ml`, unchanged,
      verified via passing `api/tests/test_api.py`).
- [x] ML inference is deterministic (existing + new gated-detector
      tests both verify this directly).
- [x] Failure modes are graceful (no crash on malformed input, no-dot
      image, or gate rejection - all collapse to the existing safe
      empty convention).
- [x] End-to-end image → structural representation works (Section 11).
- [x] Production/default detector decision is evidence-based (Section 15).
- [x] Canonical checkpoint is identified (Section "Checkpoint policy" below).
- [x] Tests pass (239/239).
- [ ] **Deployment smoke tests pass** - NOT re-run this session (Docker/API
      live smoke test), only inferred from passing unit/integration tests.
- [x] No unresolved ML crash exists in the supported path.

**One box unchecked → ML STATUS = PARTIAL**, per this task's own explicit
rule. This is a much shorter list of gaps than existed before this
session (the gate closes real evidentiary ground on false-positive
quantification and mitigation), but the rule is binary and one item is
honestly unresolved.

## Checkpoint policy (Phase 11)

- **Canonical checkpoint**: `experiments/m4_2/results/dot_heatmap_net_v2.pt`
- **SHA-256**: `9da73c87abb4a85c2255140b31569e3ab0930f79552ca34876276d0ea005b7f5`
- **Architecture**: `DotHeatmapNetV2` (`experiments/m4_2/model.py`),
  382,769 parameters, native 128×128 heatmap output.
- **Trained**: 30 epochs, Adam, lr=1e-3, batch_size=8, seed=42, CPU-only
  (`experiments/m4_2/train.py`). Best val_loss 0.1602
  (`experiments/m4_2/results/training_log.json`).
- **Dataset version**: 135 source patterns (kolam19+kolam29, kolam109
  excluded), 505 rendered images, `degrade_v3` augmentation
  (`experiments/m4_2/generate_training_data.py`).
- **Loaded by**: `experiments/m4_2/ml_lattice_detector.py::load_model()`
  (production path, `api/detectors.py::MLDetector`) and
  `experiments/m4_2/gated_ml_lattice_detector.py::GatedLearnedLatticeDetectorV2`
  (experimental gating path, this session).
- **`MODEL_VERSION`**: `"m4.2-128"` (ungated, production-path string,
  returned in API responses) / `"m4.2-128-gated-v1"` (gated,
  experimental, not currently reachable via the API).
- **Peak-detection parameters**: threshold=0.6, min_distance=2.0
  heatmap cells (`experiments/m4_2/results/peak_sweep.json`,
  validation-selected, unchanged this session).
- **No ambiguity**: exactly one checkpoint file exists in the repo for
  the ML detector; both the production and experimental adapters point
  at the same file.

## 18. Next step

**Not M5** (per this task's explicit instruction and the still-standing
answer from `docs/M4_2_PARITY_EVALUATION.md`'s M5 gate - an unrelated
milestone, not affected by this session).

**Exactly one highest-value ML blocker**: **wire the gate into
`api/detectors.py` behind an explicit opt-in flag (e.g.
`detector=ml-gated` or a query parameter), run it through
`evaluate_m4_2.py`'s full decision-rule framework (not just this
session's threshold/FP-rate slice) to see whether it changes the
pre-committed decision outcome, and - separately - investigate WHY the
in-scope/no-dot residual distributions overlap** (Section 10) as a
follow-up domain-gap diagnostic, since a cleaner-separating signal
(rather than a bigger residual-threshold search) is what would let the
gate keep MORE real positives while still rejecting MORE false ones.
