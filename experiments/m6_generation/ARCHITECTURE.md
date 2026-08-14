# M6 -- Architecture audit (Phase 0)

Traced by reading the actual code, not filenames. M4.2 and its checkpoint
(`experiments/m4_2/results/dot_heatmap_net_v2.pt`, `DotHeatmapNetV2`,
`experiments/m4_2/model.py`, `experiments/m4_2/ml_lattice_detector.py`)
are **not modified anywhere in M6** -- used only as a frozen verifier in
Phase 7, exactly as instructed.

## 1. What exactly represents a kolam?

Two distinct representations coexist in `engine/`, used for different
purposes -- M6 must not conflate them:

- **`engine.kolam_pattern.KolamPattern`**: a REAL, CSV-sourced pattern.
  Fields: `pattern_id, collection, raw_trace (dense float polyline),
  trace_points, dot_points: set[(int,int)], edges, edge_multiplicity,
  graph: nx.MultiGraph, bounding_box`. This is provenance-bearing (came
  from a specific row of a specific CSV) -- M6's generated candidates
  must NOT pretend to be one of these (same rule M5's `GeneratedKolam`
  already follows, see `engine/generated_kolam.py`'s module docstring).
- **`engine.generated_kolam.GeneratedKolam`**: a generation candidate,
  no provenance. Fields: `dot_points, graph: nx.MultiGraph, placements:
  list[MotifPlacement], edge_multiplicity, validity_result, diagnosis,
  dot_trace: list[(int,int)] | None`. **This is the type M6 must also
  produce** (via the same construction path `engine.generation.generate_kolam`
  already uses), so the existing renderer/validator/novelty code works
  unchanged.

## 2. How are dots represented?

Integer lattice coordinates `(x, y)`, always. Half-integer coordinates
appear ONLY in raw CSV traces (`KolamPattern.raw_trace`) as loop-around
detour geometry -- `engine.graph_io.extract_dot_sequence` strips these
before building `dot_points`/the graph. M6's generator never needs to
handle half-integer points; it operates entirely in integer-lattice
space, same as M5.

## 3. How are paths represented?

`GeneratedKolam.dot_trace`: an ORDERED list of integer dot coordinates
from `engine.generation.reconstruct_dot_trace`, which runs
`nx.eulerian_circuit`/`nx.eulerian_path` over the graph's largest
connected component. This is a DERIVED field, not something a generator
ever needs to emit directly -- once a valid graph exists, the trace is
computed deterministically. **M6's generator therefore only needs to
emit graph structure (dots + edges), not a path sequence** -- the path
falls out of validity for free.

## 4. How are edges/intersections represented?

`nx.MultiGraph`, not `nx.Graph` -- parallel edges (multiplicity) are
real and load-bearing (`engine.motifs`' module docstring: "two dots with
a genuine double strand... must be distinguished from two dots with a
single strand"). Edges are stored as `frozenset({a, b})` keys with
integer counts when multiplicity matters (`KolamPattern.edge_multiplicity`,
`GeneratedKolam.edge_multiplicity` -- both `dict[frozenset, int]`).
Kolam patterns have NO edge crossings in the graph-theoretic sense (a
"crossing" in the visual rendering is just two strands passing near the
same point without sharing a node) -- there is no crossing-avoidance
constraint anywhere in the existing validator; M6 does not invent one
(explicit instruction: don't invent constraints the repo doesn't
define).

## 5. What does the M5 placement scorer consume?

`engine.learned_scoring.PlacementScorer` (MLP, 16 -> 32 -> 16 -> 1,
1089 params) consumes a **fixed 16-dim hand-engineered feature vector
per CANDIDATE PLACEMENT** (`engine.learned_scoring.extract_features`):
motif length, touched-node counts (new vs. existing), local parity
delta, connectivity effect (merge/extend/isolate counts), global parity
effect (odd-degree before/after/delta), contribution strand count,
whether any real structure exists yet, progress fraction, global
odd-degree fraction. It does **not** consume a whole-graph or whole-
sequence representation -- it scores ONE candidate edit to a
partially-built graph, used inside `engine.learned_generation`'s
multi-restart greedy search loop. **This is directly reusable by M6
unchanged** as a candidate-ranking / rejection-sampling signal on top of
whatever M6's generator proposes (Phase 5), exactly as instructed
("reuse M5 placement scoring instead of rewriting it").

## 6. What does the renderer consume?

`engine.render.render_trace_svg`/`render_trace_png` (and the
`GeneratedKolam`-specific wrappers `render_generated_kolam_svg/png`):
`dot_points` (any iterable of `(x, y)`) + an optional `trace` (ordered
point sequence, may be `None` -- renders dots-only + "INVALID" label,
never fabricates a stroke for an invalid candidate). Pure deterministic
geometry (straight-line segments between consecutive trace points, PIL
bitmap font for labels) -- no ML, no randomness. **M6 reuses this
renderer completely unchanged**; a candidate is "renderable" as soon as
it is a `GeneratedKolam` (or exposes `.dot_points`/`.dot_trace`), which
falls out of using `engine.generation.generate_kolam` as the final
assembly step (see Phase 2 below) -- no second renderer needed.

## 7. What constitutes a structurally valid kolam?

`engine.validity.check_validity` (hard gate, never softened): largest
connected component covers every node AND (is Eulerian circuit OR has
Eulerian path). `engine.validity.diagnose_validity` is the graded
companion (odd-degree nodes, Chinese-Postman-style minimum-cost
correction) used for partial credit / repair, not for the pass/fail
decision itself. **M6 reuses both, unmodified** -- this is the same hard
gate M5's `generate_novel_kolam_learned` already enforces after its
bounded multiplicity-only repair (`engine.learned_generation.repair_multiplicity`),
which M6 also reuses rather than reimplementing repair logic.

## 8. What existing utilities are reused by M6 (not reimplemented)?

- `engine.motifs.Motif` / `MotifPlacement` / `induce_motif_set_adaptive`
  -- the vocabulary M6's sequence representation is built FROM (Phase 2).
- `engine.symmetry.D4_TRANSFORMS` / `canonical_motif` / `apply_transform`
  -- both for symmetry-aware augmentation (Phase 3) and for the
  `symmetry=` generation conditioning knob (Phase 4/6).
- `engine.generation.build_candidate_graph` / `generate_kolam` /
  `reconstruct_dot_trace` -- final assembly from a placement list to a
  `GeneratedKolam`, identical to M5's own pipeline.
- `engine.learned_generation.repair_multiplicity` -- bounded, geometry-
  safe closing repair (never invents new edges, only raises multiplicity
  of edges already present) -- reused as-is for M6 candidates too.
- `engine.learned_scoring.PlacementScorer` / `ScorerBundle` -- see #5.
- `engine.novelty.graph_fingerprint` / `coordinate_similarity` /
  `novelty_report` -- D4+translation-canonical structural fingerprinting;
  Phase 8 extends this with additional distance terms (edit distance,
  symmetry-aware distance) but does NOT replace the exact-duplicate
  detection this already provides.
- `engine.render.*` -- see #6.
- `api.detectors.get_detector` (classical + `ml-gated`, wrapping the
  FROZEN `DotHeatmapNetV2` checkpoint) -- Phase 7's verifier, used
  read-only.

## 9. What existing generated training data can be reused?

M5's `experiments/m5_generation/data/{train,val,test}.npz` (528175 /
108690 / 122675 examples) is a **per-CANDIDATE feature/label dataset for
the placement SCORER** (accept/reject a single edit) -- it is NOT a
sequence dataset and cannot be reused directly for an autoregressive
generator, which needs whole ORDERED PLACEMENT SEQUENCES per pattern,
not isolated (feature, label) pairs. The `split_manifest.json`
train/val/test PATTERN-ID split (leakage-safe, by pattern, not by
example) **is reused as-is** for M6's own dataset build, so M6 never
trains/validates/tests across a pattern-id boundary M5 already
established, and the two systems' evaluation sets stay comparable.

The underlying SOURCE data -- `kolam_data/Kolam CSV files/{kolam19,
kolam29}.csv` (kolam109 excluded, same precedent M4.2's own training-data
generation set: too dense, 100+ patterns of ~24k trace points, only
2.1% dot-recoverability at a small render scale) -- is the raw material
M6's Phase 3 augments, exactly as instructed ("use the existing valid
kolam corpus").

## 10. Representation decision for M6 (Phase 2 summary)

Given #3 (path is a derived field, not something to generate) and #5
(the placement scorer already operates on individual placement edits),
the natural, minimum-new-surface representation is a **sequence of
placement tokens**: for a pattern with real, ordered `MotifPlacement`s
(from `induce_motif_set_adaptive`, which already returns them in
selection order), flatten to one token per (point, motif_id, transform)
triple actually used, terminated by an EOS token. This is exactly the
sequence `engine.motifs.induce_motif_set_adaptive` produces when run on
a real pattern -- M6 does not invent a parallel representation; it
trains a model to predict what that function already extracts, so that
at generation time a sequence can be SAMPLED instead of INDUCED from an
existing source. Full field-level design in `representation.py`.
