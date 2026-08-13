# Novel Structural Generation (M3.7)

## The distinction from reconstruction

`engine.reconstruction.reconstruct_kolam(source, placements)` answers
"can THIS source be rebuilt" - and it always CAN, exactly, because it
copies the real deficit edges back from `source.graph` when motif
coverage falls short. `engine.novel_generation.generate_novel_kolam(motif_library,
dot_points)` answers a structurally different question: given only a
set of abstract, reusable motif SHAPES (`engine.motifs.Motif` - relative
edges, no coordinates, no source) and a dot layout, can the shapes alone
produce something valid?

The distinction is enforced at the type level, not by convention:
`select_novel_placements` (the function that decides what to place)
never receives a source graph as an argument at all. There is nothing
in scope for it to copy a residual edge from, even by accident. This is
verified directly in `tests/test_novel_generation.py`:
`test_novel_generation_never_copies_source_residual` shows that
`reconstruct_kolam(source, [])` (empty placement list) still reproduces
`source` exactly via residual, while `generate_novel_kolam` on the exact
same layout, with a real motif library extracted from that same source,
does NOT.

## Pipeline

```
motif library (Motif shapes, no coordinates)
      +
new dot layout
      |
      v
select_novel_placements   -- greedy placement + flat multiplicity cap
      |
      v
engine.generation.generate_kolam   -- UNCHANGED, reused as-is: MultiGraph
      |                                construction, Eulerian validity,
      v                                deterministic trace
GeneratedKolam candidate
```

`extract_motif_library(placements)` is the abstraction step: it strips
`MotifPlacement` objects (motif shape + specific source coordinates +
transforms) down to just the distinct shapes - the reusable part. A
library built this way carries no memory of which pattern or which
points produced it.

## Multiplicity constraint, redefined for an unseen layout

M3.6's constraint compared a candidate's contribution against a SPECIFIC
source pattern's exact per-edge strand count. There is no such count for
a layout nothing was ever drawn on. Instead, `select_novel_placements`
uses a flat cap, `max_multiplicity` (default 2) - the real, verified
dataset-wide ceiling from `docs/DATA_FORMAT.md` (no source pattern in
the Kaggle dataset was ever found with a triple-or-more strand on any
edge). A candidate placement that would push any touched edge above this
cap is rejected outright, exactly like M3.6's discipline: never clipped,
never silently repaired.

## The bootstrap problem (found by testing, not anticipated)

The first scoring design directly reused
`engine.motif_selection._parity_delta` - which treats a node's degree
BEFORE a placement as a baseline to protect. On a brand-new layout,
every node starts at degree 0 (even, by the modulo-2 definition), so the
very first edge ever placed always looks like it "breaks" two nodes from
even to odd. Every candidate scored negative; nothing was ever placed.
Verified directly: the naive version produced `n_edges=0` on every test
input, not a subtle degradation.

Fix (`_novel_score`): a node touched for the first time has no parity
state worth protecting - giving it any structure at all is pure growth,
not a tradeoff to weigh. Only nodes that already have degree > 0 (from a
PREVIOUS accepted placement in the same run) get the parity
reward/penalty treatment `_parity_delta` uses. This is a genuinely
different function, not a parameterization of the M3.6 one, because the
two contexts have a different meaning of "baseline": M3.6 starts from an
already-partial reconstruction of a real pattern; M3.7 starts from
nothing.

## Evaluation

5 reproducible candidates (`validate_novel_generation.py`): motif
libraries extracted from `kolam19#1` and `kolam29#1` (via
`induce_motif_set_eulerian_aware`, M3.6's best-performing mode), placed
onto three kinds of unseen layout - a different real pattern's dot
layout (`kolam19#2`, `kolam19#3`, `kolam29#2`) and a genuinely synthetic
15×15 grid that appears nowhere in the dataset.

| candidate | valid | connected | dots | edges | library size | symmetry coverage | duplicates source | time |
|---|---|---|---|---|---|---|---|---|
| kolam19#1 lib → kolam19#2 layout | False | False | 188 | 116 | 8 | 0.473 | False | 0.21s |
| kolam19#1 lib → kolam19#3 layout | False | False | 212 | 140 | 8 | 0.495 | False | 0.22s |
| kolam29#1 lib → kolam29#2 layout | False | False | 472 | 357 | 12 | 0.477 | False | 0.66s |
| kolam19#1 lib → synthetic 15×15 grid | False | False | 225 | 190 | 8 | 0.325 | False | 0.20s |
| kolam29#1 lib → synthetic 15×15 grid | False | False | 225 | 212 | 12 | 0.544 | False | 0.40s |

**0/5 valid, 0/5 fully connected, 0/5 duplicate their source pattern.**
This is reported plainly, not adjusted to look better: a small (8-12
motif), greedily-placed library does not yet produce a fully valid
single-stroke structure on an unseen layout. What it DOES demonstrate:
the pipeline runs end-to-end and deterministically at every scale
tested; the multiplicity cap is never violated; every candidate has
real, measurable D4 structural symmetry (33-54% coverage, via the
existing `engine.symmetry.analyze_symmetry`, reused unchanged); and no
candidate is a trivial copy of the pattern its library came from.

**On "novelty"**: this project does not claim artistic or visual
novelty, and has no way to measure it. "Duplicates source" is a strict,
mechanical check - exact edge-multiset equality with one specific named
source pattern (`engine.novel_generation.duplicates_source`). A False
result means exactly that and nothing more: it is not evidence of
aesthetic originality, only of not being a literal copy.

## Known limitations

- **Recall/validity gap is worse than reconstruction's, as expected.**
  Reconstruction always reaches validity (see `docs/RECONSTRUCTION.md`);
  novel generation has no residual fallback, so it inherits the full
  gap between what a small motif library can cover and what a complete
  valid structure needs. This is not a bug to fix here - it is the
  honest cost of the distinction M3.7 exists to preserve.
- **No connectivity-seeking strategy.** `select_novel_placements` scores
  growth and parity locally; it has no global view of whether the
  layout ends up as one component or many. Every evaluated candidate
  fragmented into multiple components.
- **Library size is small** (8-12 motifs, inherited directly from
  M3.6's own measured motif counts) - a richer library discovered from
  MULTIPLE source patterns, not attempted here, might cover more of a
  new layout. Not attempted, per the task's explicit scope limit on this
  phase.
- **Greedy, single-pass, no backtracking** - same discipline and same
  limitation as every other selector in this project (see
  `docs/MOTIF_SELECTION.md`'s "Limitations of greedy selection").
