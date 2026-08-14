# Structural Generation

## Objective

What PULLI means by "generation" at this stage: taking a set of motif
rules (the exact `MotifPlacement` objects `engine.motifs.induce_motif_set`
/ `induce_motif_set_adaptive` already discover from real data, or
hand-constructed for a controlled test) and a target dot layout, and
deterministically constructing a candidate graph, checking it against the
same hard structural-validity gate CSV-sourced data is checked with, and
- only if valid - reconstructing an ordered stroke trace.

This is **not** image generation and makes no claim about visual
plausibility. It is not ML - there is no model, no training, no learned
parameters anywhere in this pipeline; everything is deterministic graph
construction and networkx's own (not reimplemented) Eulerian-circuit
algorithms. A generated candidate is never reported as successful because
it "looks" symmetric or plausible - only `engine.validity.check_validity`
(unmodified from the CSV-data gate) decides that.

## Input

`generate_kolam(placements: list[MotifPlacement], dot_points: set[Point])`.

`placements` reuses `engine.motifs.MotifPlacement` as-is - the same type
`induce_motif_set`/`induce_motif_set_adaptive` already return, so motifs
discovered from real data can be fed straight back into generation with
no conversion step, and hand-built test cases use the exact same
constructor. `dot_points` is the target lattice the candidate is built
on - arbitrary shape, not necessarily square.

**Design choice, explained**: the task's illustrative signature was
`generate_kolam(motifs, dot_points, symmetry="D4")`. The implemented
signature drops the separate `symmetry` parameter - it would be
redundant. D4 symmetry is already expressed *per placement* via
`MotifPlacement.transforms` (which D4 transform each individual point
uses, from `engine.symmetry.D4_TRANSFORMS`), which is how the existing
induction code already represents it. A top-level `symmetry="D4"` string
would have no well-defined effect beyond what `transforms` already
encodes, so it was left out rather than added as an unused parameter.

## Construction

`build_candidate_graph(placements, dot_points)`: each placement is
stamped independently via the pre-existing `apply_motif` (unmodified),
and its resulting edges are added **one at a time** into a single
accumulator `nx.MultiGraph` via `add_edge` - never via `nx.compose` or a
fresh-graph merge. This matters: composing two independently-built
MultiGraphs can silently collide on auto-assigned parallel-edge keys and
drop one strand; adding edges one at a time into one accumulator never
can, because `MultiGraph.add_edge` always allocates a fresh key. This is
also how "avoid silently overwriting existing edges" and "preserve edge
multiplicity" are satisfied simultaneously by construction, not by a
separate check.

`dot_points` is defensively copied at the start of `build_candidate_graph`
and `placements`' contents are only ever read, never mutated - see
`docs/GENERATION.md`'s companion tests
(`test_generation_does_not_mutate_source_motifs`,
`test_generation_does_not_mutate_source_kolam_pattern`).

## Multiplicity

Every `apply_motif` call already preserves multiplicity within one
placement (a motif with a repeated relative edge produces that many
parallel MultiGraph edges). Generation extends this across *multiple,
independent* placements: two different placements that happen to stamp
the same dot pair produce 2 separate parallel edges in the accumulator
graph, not 1 - verified directly
(`test_overlapping_motif_placements_accumulate_not_overwrite`). The
returned `GeneratedKolam.edge_multiplicity` uses the exact same
`{frozenset({a, b}): count}` convention as `KolamPattern.edge_multiplicity`
(`engine/dataset.py`), computed the same way (`Counter` over the graph's
edges), for consistency between source and generated data.

## Validation

`generate_kolam` unconditionally calls `engine.validity.check_validity`
(unmodified - the same hard gate CSV-sourced data goes through) and
populates `GeneratedKolam.validity_result` on every candidate, valid or
not. It also unconditionally calls `engine.validity.diagnose_validity`
(the graded, explainable companion added for image-derived data) and
stores it as `GeneratedKolam.diagnosis` - so an invalid candidate always
exposes *which* vertices have the wrong degree and *how many* corrections
a Route-Inspection-Problem fix would need, without ever applying that fix.
No candidate is silently repaired.

## Trace reconstruction

`reconstruct_dot_trace(graph)` operates on the graph's **largest
connected component** (matching `check_validity`'s own convention) and
uses networkx's own `eulerian_circuit`/`eulerian_path` (not a
reimplementation of Hierholzer's algorithm) with an explicit, sorted
`source` node so the traversal is reproducible across calls on the same
graph. It returns `None` - not an approximation, not a partial trace -
if the largest component is not itself Eulerian (circuit or path); that
determination belongs to `check_validity`, not to this function.

**This returns a DOT-LEVEL trace only.** It does not reconstruct the
half-integer loop-around points the source CSV format uses (see
`docs/DATA_FORMAT.md`). This is a deliberate scope decision, not an
oversight: which side of a skipped dot the curve arcs around is a
drawing decision the graph topology alone does not determine - the
verified concrete double-strand example in `DATA_FORMAT.md` shows the
*same* dot pair connected once passing above and once passing below the
skipped dot, i.e. the same topology, two different loop geometries.
Inventing a specific side would not be justified by the established
rules, so it isn't attempted here. **Loop-around/half-step reconstruction
is explicit future work, tracked separately, not started.**

## Current limitations

Explicitly distinguishing the three things this task named:

- **Structural validity** - the only thing `GeneratedKolam.is_valid`
  claims, backed entirely by the unmodified `check_validity` gate.
- **Visual plausibility** - not represented anywhere in this pipeline.
  A candidate that passes validity has never been rendered or looked at;
  this codebase makes no claim about how it would look drawn.
- **Exact CSV trace reconstruction** - not attempted. `dot_trace` is an
  ordered dot-visit sequence; it is not, and does not claim to be, a
  reconstruction of a half-integer-resolution CSV-style trace.

Other known limitations of this first version:
- Motifs discovered by `induce_motif_set_adaptive` are MDL-gated - they
  stop as soon as no further motif shortens the description, by design
  (see prior session's MDL-gating work). This means feeding real
  discovered motifs straight into `generate_kolam` typically produces a
  **partial, disconnected** candidate (see "Example" below) - the
  generator does not currently fill gaps with the induction's own
  `residual` edge list, or escalate coverage to force connectivity. This
  is an exposed, real gap, not a hidden one.
- No motif selection, search, diversity, or optimization of any kind -
  `generate_kolam` builds exactly what `placements` says to build, in the
  order given. Choosing *which* motifs/placements to use for a "good"
  candidate is out of scope for this milestone.
- `dot_points` for a hand-built synthetic case must be chosen so motif
  edges land inside it (`apply_motif` silently drops edges landing
  outside the given node set, unchanged pre-existing behavior) - this is
  the same contract `apply_motif` already had, not new behavior.

## Example

Controlled synthetic case (`tests/test_generation.py:doubled_square_placement`):
a single motif - a 4-cycle with every relative edge doubled - stamped at
one center, on a 4-dot lattice `{(0,0), (1,0), (1,1), (0,1)}`.

```
candidate nodes: 4
candidate unique edges: 4          (every edge multiplicity exactly 2)
candidate total edge strands: 8
validity_result: is_eulerian_circuit=True, has_eulerian_path=True,
                 connected_components=1, largest_component_covers_all_nodes=True
dot_trace: [(0,0), (0,1), (1,1), (1,0), (1,1), (0,1), (0,0), (1,0), (0,0)]
           (9 points: a closed loop starting and ending at (0,0),
            traversing all 8 parallel edges exactly once)
```

Real-data experiment (`kolam19` pattern 26 - see full numbers in the
session report): 8 motifs discovered by `induce_motif_set_adaptive`,
fed into `generate_kolam` on the source pattern's own 200-dot layout.
Result: **invalid** - 32 connected components, 12 odd-degree nodes, 6
corrections needed. This is the expected, honest outcome of the
current limitation above (MDL-gated induction does not guarantee
coverage/connectivity, and generation does not currently compensate for
that) - reported as a real finding about what the generator still needs,
not adjusted to look better.
