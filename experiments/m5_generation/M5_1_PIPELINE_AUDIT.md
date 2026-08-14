# M5.1 Phase 1 — pipeline audit

Traced from actual code (not assumed), current as of the M5 final
benchmark. Every claim below cites the exact file/function.

## 1. Input representation

A target dot lattice: `set[tuple[int, int]]` (integer lattice
coordinates), plus a **motif library**: `list[Motif]` where
`Motif = tuple[RelEdge, ...]` (`engine/motifs.py`) — abstract, relative-
coordinate edge shapes with no absolute position, induced from real
patterns via `engine.motifs.induce_motif_set_adaptive`
(`engine/generation_api.py::motif_library_from_sources`). No source
graph is passed into placement selection itself
(`engine/novel_generation.py`'s module docstring: "there is no source
graph anywhere in this module's placement logic").

## 2. Candidate representation

`engine.generated_kolam.GeneratedKolam`: `dot_points`, `graph:
nx.MultiGraph`, `placements: list[MotifPlacement]`,
`edge_multiplicity: dict[frozenset, int]`, `validity_result`,
`diagnosis`, `dot_trace: list[Point] | None`. No provenance fields
(distinct from `KolamPattern`, which carries `pattern_id`/`collection` —
see `engine/generated_kolam.py`'s own docstring on why this
distinction is deliberate).

## 3. Placement representation

`engine.motifs.MotifPlacement`: one `motif` (shape) + `points: list[Point]`
(every lattice location it was stamped at) + `transforms: dict[Point, str]`
(D4 transform per point, default "identity") + `new_edges: set`. One
`MotifPlacement` can cover many points sharing the same motif+transform.

## 4. Graph representation

`nx.MultiGraph` throughout — never `nx.Graph`. Parallel edges (real
strand multiplicity) are load-bearing: `engine/motifs.py`'s module
docstring: "two dots with a genuine double strand between them are
distinguished from two dots with a single strand." Edge identity for
multiplicity accounting is `frozenset({a, b})`.

## 5. Connectivity algorithm

`nx.number_connected_components` / `nx.connected_components` (standard
NetworkX, unmodified) inside `engine.validity.check_validity`. The
"largest connected component" convention (not "any" component) is used
consistently across `check_validity`, `diagnose_validity`, and
`engine.generation.reconstruct_dot_trace`.

## 6. Search algorithm

`engine.learned_generation.search_best_candidate`: `n_restarts`
independent passes of `_single_restart_placements`, each a single
deterministic greedy sweep over a SHUFFLED (per-restart, seeded)
ordering of `(point, motif, transform)` candidates. Each candidate
placement is accepted iff `engine.learned_scoring.ScorerBundle.score`
(the trained MLP) returns > `ACCEPT_THRESHOLD = 0.5`. The best restart
(by `_candidate_quality`: valid first, then fewest stranded nodes, then
fewest odd-degree nodes, then lowest correction cost) is kept; search
stops early the moment any restart is fully valid.

## 7. Placement scorer

`engine.learned_scoring.PlacementScorer`: MLP, 16→32→16→1, 1,089
params. Input: a 16-dim hand-engineered feature vector per CANDIDATE
EDIT (`extract_features` — motif length, touched-node growth/existing
split, local parity delta, connectivity effect via incremental
union-find, global parity effect, contribution strand count, progress
fraction, global odd-degree fraction). Output: sigmoid probability,
trained via imitation learning (oracle label = "does this edit appear
in a real pattern's own reconstruction," from teacher-forced replay
against 528,175 labeled examples). Test accuracy 90.3% vs. 80.0%
trivial baseline, AUC 0.962
(`experiments/m5_generation/results/train_report.json`).

## 8. Repair algorithm

`engine.learned_generation.repair_multiplicity`: Chinese-Postman-style
route doubling. Only runs if the search-phase candidate is invalid AND
already fully connected (0 nodes outside the largest component) — never
attempts to merge separate components (would require inventing an edge
with no motif justification, explicitly refused). Walks
`diagnose_validity`'s minimum-weight odd-node pairing
(`nx.min_weight_matching` over shortest-path distances) and increments
each correction path edge's strand count, bounded by
`max_repair_multiplicity` (default 3 — **see Phase 3/M5_1_CONSTRAINT_SPEC.md
for why this specific bound is the root cause of the multiplicity
finding**).

## 9. Multiplicity handling

Two INDEPENDENT caps exist in the current pipeline:
`engine.novel_generation.DEFAULT_MAX_MULTIPLICITY = 2` (search phase,
matches real data) and `engine.learned_generation.DEFAULT_REPAIR_MAX_MULTIPLICITY = 3`
(repair phase, does NOT match real data — see Phase 3). No single
source of truth for "what multiplicity is allowed" currently exists;
this split-cap design is itself part of the M5.1 finding.

## 10. Rendering pipeline

`engine.render`: pure deterministic geometry (no ML, no randomness).
`render_trace_svg`/`render_trace_png` take `dot_points` + an optional
ordered `trace`; `render_generated_kolam_svg/png` wrap these for a
`GeneratedKolam`, labeling an invalid candidate "INVALID" rather than
silently omitting its stroke. Straight-line segments only — no
loop-around curve reconstruction (documented limitation, not attempted).

## 11. Validation pipeline

`engine.validity.check_validity` (hard gate, never softened): largest
component covers every node AND (is Eulerian circuit OR has Eulerian
path). `diagnose_validity` is the graded companion (odd-degree nodes,
minimum-cost correction) used by repair and by diagnostics, never by
the pass/fail decision itself.

## 12. Novelty fingerprinting

`engine.novelty.graph_fingerprint`: D4- and translation-canonical edge-
multiset signature (lexicographically smallest of the 8 D4 transforms,
each shifted so its bounding box starts at the origin). Two graphs with
identical fingerprints are the same shape up to translation/rotation/
reflection. `novelty_report` aggregates unique-fingerprint rate, exact
topological duplicate rate (vs. a source pool), exact/near coordinate
duplicate rate (only meaningful when layouts match).

## 13. Existing symmetry handling

`engine.symmetry.D4_TRANSFORMS` (8 lambdas: identity + 3 rotations + 4
reflections). `analyze_symmetry`/`induce_motif_symmetric`: clusters
local windows by their D4-canonical signature and reports the DOMINANT
motif's coverage fraction — a descriptive measurement, not a generation
constraint. Nothing in the current search/repair pipeline actively
steers toward higher symmetry; M5's own measured average symmetry
coverage (21.6%, `benchmark_report.json`) is emergent, not targeted.
