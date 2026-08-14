# M5 - Structural Grammar: NOT STARTED

**This milestone was explicitly scoped OUT of this session.** Given the
size of M5 as specified (a formal grammar representation layer, parsing
existing patterns into grammar descriptions, grammar-based generation,
and a structural search mechanism - each independently a multi-session
effort), the session's real implementation effort went entirely into
M4.2 (`docs/M4_2_GENERATION.md`), done honestly rather than spreading
effort thin across three milestones and risking implementation theater
in all of them. This document exists only so M5's status is stated
plainly (not silently omitted) and so a future session has a concrete
starting point.

## What already exists that M5 would build on

M5-A/B's "grammar representation" and "structural parsing" are not
starting from nothing - the raw material already exists and is tested:

- **Motif primitives**: `engine.motifs.Motif` (relative-edge shapes) and
  `MotifPlacement` (shape + coordinates + D4 transform) already ARE a
  primitive/instance split, just not packaged as a formal grammar object.
- **Symmetry**: `engine.symmetry.analyze_symmetry` / `D4_TRANSFORMS`.
- **Composition rules**: `engine.motifs.induce_motif_set_adaptive`'s MDL
  gate (`mdl_gain`) already encodes "when is adding this motif worth
  it" - the seed of a compositional cost model, not a grammar per se.
- **Constraints**: `engine.validity.check_validity` /
  `diagnose_validity` (Eulerian, connectivity), `engine.novel_generation`'s
  flat multiplicity cap.
- **A structural fingerprint** for comparing shapes: `engine.novelty.graph_fingerprint`
  (built this session for M4.2-D, directly reusable for M5's "structural
  similarity" foundation named in M5-C).

## What M5 would actually require (not attempted)

- **M5-A Grammar representation**: a formal object tying together
  symmetry + lattice + topology + motif grammar into one described
  hierarchy (the task's own conceptual `Kolam -> symmetry/lattice/
  topology/motif grammar` tree) - currently these are four separate,
  uncomposed analyses (`analyze_symmetry`, `KolamPattern`,
  `check_validity`, `induce_motif_set_adaptive`), not one grammar object.
- **M5-B Structural parsing**: a function `KolamPattern -> {symmetry,
  lattice, topology, motifs, composition_rules, constraints}` producing
  exactly the machine-readable shape the task illustrates. Not built -
  would mostly be an assembly/serialization layer over the analyses
  above, but a real one, not attempted here.
- **M5-C MDL / description length as a STRUCTURAL objective**: the
  existing MDL machinery (`mdl_gain`, `description_size`,
  `compression_ratio`) operates at the MOTIF level only. Extending it to
  compare whole candidate GRAMMARS (not just whether to add one more
  motif) is new work.
- **M5-D Grammar-based generation**: would consume M5-A's grammar object;
  cannot be built before that object exists.
- **M5-E Structural search**: "find a valid Kolam satisfying X" - this
  is where `engine.generation_api.GenerationConstraints`'s currently
  unsupported constraints (`symmetry`, `complexity`, `stroke count` as
  hard, searched-for targets - see `docs/M4_2_GENERATION.md`) would
  actually get implemented, most likely as a search/retry loop over
  `generate_kolam_candidate` varying motif subset/layout/multiplicity,
  not reinforcement learning (per this task's own explicit guidance).

## Recommended order if M5 is picked up

1. M5-B first, oddly, not M5-A: writing the PARSER (`KolamPattern ->
   structural description dict`) using only functions that already
   exist forces the grammar's actual field shape to be grounded in real,
   derivable data rather than designed from the task's illustrative
   example - matches this project's repeated "do not invent fields that
   cannot be derived" discipline.
2. Only then formalize M5-A as a real dataclass/type around what M5-B's
   parser actually needed to produce.
3. M5-D (grammar-based generation) and M5-E (search) both depend on
   M4.2's validity gap (`docs/M4_2_GENERATION.md`'s "next bottleneck")
   being addressed first, or they will inherit the same 0%-valid result
   this session already measured for the non-grammar-based generator -
   a connectivity-aware placement strategy is a prerequisite for BOTH
   M4.2 and M5 to produce usable output, not just M4.2's own problem.
