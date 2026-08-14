"""M4.2-A: a single constraint-based generation entry point.

Wraps the existing, tested M3.7 pipeline
(`engine.novel_generation.select_novel_placements` +
`engine.generation.generate_kolam`, both unmodified) behind one request
object, instead of requiring a caller to already know about motif
libraries / placement selection internals. Every constraint below is
either (a) resolved into an input those existing functions already
accept, or (b) applied as a pure POST-HOC filter/report on the
resulting `GeneratedKolam` -- nothing here reimplements placement or
validity logic, and nothing silently repairs a candidate that doesn't
meet what was asked.

WHAT THIS DOES NOT YET SUPPORT (real gap, not hidden): `symmetry`,
`complexity`, and `approximate stroke count` as HARD constraints that
generation searches for. There is currently no retry/search loop --
`generate_kolam_candidate` builds exactly one candidate per call and
reports whether it happens to satisfy `require_single_stroke`
(the one constraint that can be checked and enforced today, since
`GeneratedKolam.is_valid` already means exactly that). Satisfying a
symmetry/complexity/stroke-count TARGET would need either a search over
many candidates (varying motif subset / multiplicity / seed) or a
generation-time scoring change -- that is exactly M5-E's scope
("Structural search"), not attempted in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.dataset import load_kolam
from engine.generated_kolam import GeneratedKolam
from engine.generation import generate_kolam
from engine.motifs import Motif, induce_motif_set_adaptive
from engine.novel_generation import (
    DEFAULT_MAX_MULTIPLICITY,
    DEFAULT_MAX_PLACEMENTS,
    extract_motif_library,
    select_novel_placements,
)

Point = tuple[int, int]


def rectangular_lattice(width: int, height: int) -> set[Point]:
    """A `width` x `height` dense integer grid, origin at (0, 0) -- the
    simplest "lattice dimensions" constraint. Arbitrary non-rectangular
    layouts are supported too: pass an explicit `set[Point]` as
    `GenerationConstraints.lattice` instead of a `(width, height)` pair."""
    if width < 1 or height < 1:
        raise ValueError(f"lattice dimensions must be >= 1, got ({width}, {height})")
    return {(x, y) for x in range(width) for y in range(height)}


def motif_library_from_sources(
    sources: "list[tuple[str, int]]", max_radius: int = 3
) -> list[Motif]:
    """Build a motif LIBRARY (abstract shapes, no coordinates -- see
    engine.novel_generation's module docstring for why this distinction
    matters) from one or more (collection, pattern_id) source patterns,
    via the existing, unmodified `induce_motif_set_adaptive`. Motifs from
    multiple sources are pooled and de-duplicated by exact D4-canonical
    shape -- a motif repeating across sources is stored once. This is
    the "richer library from multiple patterns" extension
    docs/NOVEL_GENERATION.md's Known Limitations named as not-yet-attempted;
    it now exists here, still using only the unmodified induction/library
    functions underneath."""
    library: dict[Motif, None] = {}
    for collection, pattern_id in sources:
        pattern = load_kolam(collection, pattern_id)
        placements, _residual, _fully_covered = induce_motif_set_adaptive(pattern, max_radius=max_radius)
        for motif in extract_motif_library(placements):
            library.setdefault(motif, None)
    return list(library.keys())


@dataclass
class GenerationConstraints:
    """One generation request. Every field maps directly onto an
    existing, tested mechanism:

      lattice                : explicit target dot set, OR (width, height)
                                for a dense rectangular grid.
      motif_sources           : [(collection, pattern_id), ...] patterns to
                                build the motif library from
                                (motif_library_from_sources). Ignored if
                                `motif_library` is given directly.
      motif_library           : an already-built list[Motif] (e.g.
                                hand-picked motif families) -- takes
                                precedence over motif_sources if both are given.
      max_multiplicity        : flat per-edge strand cap, same meaning and
                                default as engine.novel_generation's own.
      max_placements          : hard safety ceiling, same meaning as
                                engine.novel_generation's own.
      require_single_stroke   : if True (default), GenerationResult.satisfied
                                is False whenever the candidate is not itself
                                fully-connected-and-Eulerian
                                (GeneratedKolam.is_valid) -- a POST-HOC
                                report flag, not a change to placement
                                logic.
      connectivity_aware       : passed straight through to
                                engine.novel_generation.select_novel_placements
                                (default False, matching that function's
                                own default -- existing callers of this
                                dataclass see no behavior change unless
                                they opt in). See
                                docs/M4_2_CONNECTIVITY_EVALUATION.md for
                                what this changes and its measured effect.
      parity_aware             : passed straight through to
                                engine.novel_generation.select_novel_placements
                                (default False). Independent of
                                connectivity_aware -- either or both may
                                be set. See docs/M4_2_PARITY_EVALUATION.md.
    """

    lattice: "set[Point] | tuple[int, int]"
    motif_sources: "list[tuple[str, int]]" = field(default_factory=list)
    motif_library: "list[Motif] | None" = None
    max_multiplicity: int = DEFAULT_MAX_MULTIPLICITY
    max_placements: int = DEFAULT_MAX_PLACEMENTS
    require_single_stroke: bool = True
    connectivity_aware: bool = False
    parity_aware: bool = False


@dataclass
class GenerationResult:
    candidate: GeneratedKolam
    constraints: GenerationConstraints
    satisfied: bool
    reasons_unsatisfied: "list[str]"


def generate_kolam_candidate(constraints: GenerationConstraints) -> GenerationResult:
    """The constraint-based entry point. Resolves `constraints` into
    (motif_library, dot_points), delegates entirely to
    `engine.novel_generation.generate_novel_kolam` (no reimplementation),
    and reports whether the result actually satisfies what was requested.
    `generate_novel_kolam` never fabricates validity, so `satisfied` can
    genuinely come back False -- that is reported, not hidden."""
    dot_points = (
        constraints.lattice
        if isinstance(constraints.lattice, set)
        else rectangular_lattice(*constraints.lattice)
    )

    library = constraints.motif_library
    if library is None:
        if not constraints.motif_sources:
            raise ValueError("GenerationConstraints needs either motif_library or motif_sources")
        library = motif_library_from_sources(constraints.motif_sources)

    # Same two calls engine.novel_generation.generate_novel_kolam makes
    # internally -- inlined here (not reused as-is) only so max_placements
    # can be threaded through, which generate_novel_kolam's own signature
    # does not expose.
    placements = select_novel_placements(
        library,
        dot_points,
        max_multiplicity=constraints.max_multiplicity,
        max_placements=constraints.max_placements,
        connectivity_aware=constraints.connectivity_aware,
        parity_aware=constraints.parity_aware,
    )
    candidate = generate_kolam(placements, dot_points)

    reasons: list[str] = []
    if constraints.require_single_stroke and not candidate.is_valid:
        v = candidate.validity_result
        reasons.append(
            "candidate is not a single connected Eulerian structure "
            f"(largest_component_covers_all_nodes={v['largest_component_covers_all_nodes']}, "
            f"is_eulerian_circuit={v['is_eulerian_circuit']}, "
            f"has_eulerian_path={v['has_eulerian_path']})"
        )

    return GenerationResult(
        candidate=candidate,
        constraints=constraints,
        satisfied=(len(reasons) == 0),
        reasons_unsatisfied=reasons,
    )
