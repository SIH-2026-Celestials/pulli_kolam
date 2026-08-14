# M4.2 Implementation Plan

Phase A deliverable. Written after auditing the existing M4.1 code
(`experiments/m4_1/*`), the frozen ML contract
(`engine/ml_contract.py`, `docs/ML_CONTRACT.md`), the canonical engine
(`engine/kolam_pattern.py`, `engine/dataset.py`, `engine/motifs.py`,
`engine/reconstruction.py`, `engine/validity.py`), and the existing
frontend (`frontend/frontend/`). This plan is the source of truth for
what M4.2 builds and why - see "Audit findings" for what was reused vs.
built new, and "Scope decisions" for where the full task brief's letter
was adapted to what actually exists in this repo.

## Audit findings

**M4.1 components - reused, not duplicated:**
- `engine/ml_contract.py` (`MLLatticeDetector` Protocol, `assert_conforms`) -
  frozen, used as-is. M4.2's model is a NEW implementation of this SAME
  contract, not a new contract.
- `experiments/m4_1/peak_detect.py` (`detect_peaks`, greedy NMS) -
  resolution-agnostic already (operates on whatever 2D array it's
  given), reused unmodified for the 128×128 heatmap.
- `generate_synthetic_photos.py`'s `render_clean`/`lattice_to_pixel_transform` -
  reused unmodified (the actual kolam-rendering code); M4.2's data
  generator wraps it with a new, more controlled degradation function,
  exactly the pattern `experiments/m4_1/generate_training_data.py`
  already established.
- `engine/image_io.py`'s `Preprocessed`/`Lattice` types and
  `_fit_lattice_coords` - reused (imported, not reimplemented),
  matching M4.1's own adapter pattern.
- The M4.1.1/M4.1.2 diagnostic findings (`diagnostics/`,
  `experiments/m4_1/diagnostics/`) - the entire justification for this
  phase's 128×128 requirement; not re-derived here.

**M4.1 components NOT reused (replaced for M4.2):**
- `experiments/m4_1/model.py`'s `DotHeatmapNet` - a plain 4-conv-block
  encoder with no decoder, producing 32×32 via 3 maxpools. Cannot
  produce 128×128 without a decoder path (M4.1.2 confirmed this exact
  resolution is required) - replaced by a new encoder-decoder model
  (Phase B).
- `experiments/m4_1/train.py`'s `DotHeatmapDataset` - hardcoded to
  `MODEL_INPUT_SIZE=256`/`STRIDE=8`. M4.2 uses a new dataset class
  parameterized by the new model's actual input/output sizes.
- `experiments/m4_1/generate_training_data.py`'s pattern list (18
  patterns, kolam19+kolam29 only) - M4.2 scales this up substantially
  (Phase C) and adds kolam109.

**Backend**: no REST API or server exists anywhere in this repository.
`CLAUDE.md`'s "Future backend architecture" section names FastAPI as
the intended framework; FastAPI, uvicorn, and pydantic are already
installed in this environment (verified: 0.115.5 / 0.32.1 / 2.13.4) -
not a new dependency being introduced, just not yet declared in
`requirements.txt` (fixed as part of this work, same pattern used for
`torch` in M4.1).

**Frontend**: `frontend/frontend/` is a real, working React 19 + Vite 8
app (`react-router-dom` for routing, plain CSS, **no TypeScript, no
state-management library**). Existing pages include a fully-built
`/analyze` page (`src/pages/Analyze/Analyze.jsx`) - but it is a STATIC
"scientific monograph" walkthrough over precomputed dataset kolams
(`src/data/kolams.js`), explicitly labeled as showing only what the
deterministic pipeline already computed offline, with Stage 5
("GENERATION") explicitly marked future work. It is not an upload/live-
detection UI and was NOT built to become one - deliberately, per
`CLAUDE.md`'s Phase-1 frontend rule ("do not fake image-analysis
functionality... if backend analysis is not connected yet, clearly
label the interface"). **This page is not modified.** M4.2 adds a NEW
page for the live upload/detect workflow instead of retrofitting it in.

## Scope decisions (where this plan adapts the task brief to reality)

1. **API client will be plain JavaScript** (`src/lib/api/*.js`), not
   TypeScript - the project has no TypeScript tooling anywhere
   (confirmed: no `typescript` dependency, no `tsconfig.json`).
   Introducing a TS toolchain for one feature would be a much larger,
   unrelated change than this task warrants. The client is still
   centralized (not scattered `fetch()` calls) and documents its
   shapes via JSDoc comments - the actual goal ("typed," in spirit) is
   met without the tooling change.
2. **New page, not a rewrite of `/analyze`** - see audit above.
   Route: `/detect`.
3. **Training data scale**: "use the available corpus responsibly" and
   "substantially more source patterns" - scaled from M4.1's 18
   patterns to 135 (100 train / 15 val / 20 test), chosen to stay
   within a CPU-trainable time budget (this machine has no CUDA,
   verified in M4.1). This is an explicit, documented scope choice, not
   an attempt at "production-scale" training.
   **kolam109 is excluded from this scale-up**, based on a direct
   measurement made during Phase C (not assumed): kolam109 patterns
   average ~6800-7000 dots (15-35x denser than kolam19/29), and recover
   only 2.1% of dots as distinct local maxima at 128×128 (40.5% even at
   256×256) - the M4.1.2 target-resolution justification for choosing
   128×128 was only validated up to 500 dots, so kolam109 would be
   trained against a density this project has no evidence 128×128 can
   represent. This is a new, evidence-based scope finding from this
   session, not a limitation carried over from M4.1.
4. **Compare-mode difference overlay**: implemented as a real,
   functional green/blue/red dot overlay (the core signal requested),
   without additional visual polish beyond what's needed to read it
   correctly.
5. **`auto` detector mode**: not implemented, per the task's own
   explicit instruction not to.

## Model architecture (Phase B)

- Input: grayscale `Preprocessed.binary` (same contract input as
  M4.1's detector - see `docs/ML_CONTRACT.md`, unchanged), resized to a
  new fixed `MODEL_INPUT_SIZE`.
- A small U-Net-style encoder-decoder: encoder downsamples via maxpool,
  decoder upsamples via transposed convolution with skip connections,
  producing a **native 128×128 single-channel heatmap** - the network
  itself outputs 128×128, never an upsampled 32×32 (per the task's
  explicit rule).
- Exact layer sizes, parameter count, and full docstring-level
  documentation of the coordinate convention, sigma, and heatmap
  semantics: `experiments/m4_2/model.py` (Phase B deliverable).

## Target generation

128×128 Gaussian targets, same `max`-combination convention as M4.1
(`experiments/m4_1/model.py`'s `make_gaussian_heatmap`), sigma
**configurable** (a module constant, not hardcoded inline), default
value chosen from the M4.1.2 target-resolution experiment's own
findings (`experiments/m4_1/diagnostics/TARGET_RESOLUTION_REPORT.md`) -
not an arbitrary new guess.

## Loss function

BCE-with-logits against the Gaussian target (same convention as M4.1,
which is standard for keypoint-heatmap regression) - kept identical in
kind to M4.1 since M4.1.1/M4.1.2 diagnosed the TARGET RESOLUTION as the
problem, not the loss function; changing the loss function too would
confound the comparison.

## Peak extraction / coordinate conversion

`experiments/m4_1/peak_detect.py`'s `detect_peaks`, reused unmodified.
Coordinate conversion (heatmap cell → original image pixel) follows the
exact pattern M4.1's `ml_lattice_detector.py` established, generalized
to the new model's input/output sizes.

## Contract integration

A new `experiments/m4_2/ml_lattice_detector.py`, structurally identical
in role to M4.1's (same `MLLatticeDetector` Protocol, same
`assert_conforms` call, same collapse-to-empty convention for the
documented `trace_path` blocker) but pointing at the new model/
checkpoint. `engine/ml_contract.py` is NOT modified.

A small `Detector` abstraction is added (Phase F) so the API layer can
treat classical/ML uniformly - a thin wrapper, not a new contract
system: `ClassicalDetector.detect(image_path) -> DetectionResult` and
`MLDetector.detect(image_path) -> DetectionResult`, both returning the
same plain-data `DetectionResult` shape.

## Model serialization format

`torch.save(model.state_dict(), ...)` - identical convention to M4.1
(`experiments/m4_1/results/dot_heatmap_net.pt`), no new serialization
scheme introduced.

## Inference API / REST endpoints

New minimal FastAPI service, `api/main.py` (new top-level `api/`
directory - no existing backend to integrate into). Endpoints exactly
as specified in the task brief: `POST /api/v1/detect`,
`/analyze`, `/reconstruct`, `/compare-detectors`, `GET /api/v1/health`,
`/model`. Detailed request/response contracts: `docs/M4_2_API.md`
(Phase N deliverable).

## Frontend integration

New page `src/pages/Detect/Detect.jsx` + route `/detect`, new API
client `src/lib/api/*.js`. Existing pages, routing, and styling
conventions reused (same CSS class patterns as `Analyze.css`, same
`archival-frame`/`label-tech` visual language already established
elsewhere in the app - no new design system introduced).

## Fallback behavior

Classical detection is the default and the only detector used unless
explicitly requested (`detector=ml` or `detector=compare` in the
request). If the ML checkpoint fails to load or inference raises, the
API returns an explicit error (HTTP 503 with a clear message) - **no
silent fallback to classical when ML was explicitly requested**, per
the task's rule 10 ("no silent fallback") and rule 11 ("all inference
failures must be explicit and observable").

## Tests

Per-phase focused tests (model shape/determinism, target separability,
peak detection, contract conformance, API endpoints, one integration
test image→API→canonical engine→JSON). Full list: Phase K below. Core
`tests/` suite (123 tests) is not modified.

## Evaluation gates

`experiments/m4_2/evaluate_m4_2.py` - classical vs. ML, same four
populations M4.1 used (synthetic val/test, real in-scope, real no-dot),
same metrics categories the task lists. Decision rule: ML becomes the
default ONLY if it shows a measured improvement; otherwise it stays
available (`detector=ml`) but classical remains default. No result is
assumed before this script actually runs.
