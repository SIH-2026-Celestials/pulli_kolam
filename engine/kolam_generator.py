"""M5: the self-contained, no-reference-image, no-caller-supplied-pattern
top-level generation entry point.

engine.generation_contract.generate_kolam already does seed -> structure
-> validate -> render, but it REQUIRES the caller to supply a specific
target dot lattice and motif library -- appropriate for a caller that
already has a specific layout in mind (e.g. "regenerate variations of
THIS pattern"), wrong for "just give me a kolam from a seed," which is
what this module provides.

    SEED (+ complexity, symmetry, size)
        |
        v
    lattice construction (engine.generation_api.rectangular_lattice,
                           deterministic given `size`)
        |
        v
    motif library (induced once from a small, fixed pool of held-out
                    REAL patterns -- engine.motifs.induce_motif_set_adaptive,
                    cached module-level; this is a data-driven GRAMMAR,
                    not a literal source layout -- no specific pattern's
                    dot positions ever appear in the output unless the
                    search coincidentally reproduces them, which
                    engine.novelty's fingerprinting below would catch)
        |
        v
    engine.generation_contract.generate_kolam (seed-guided search +
                                                bounded repair + hard
                                                validity gate + render)
        |
        v
    {seed, structure, dot_positions, edges, paths, valid, score, svg}

`complexity` and `symmetry` are REAL, EXECUTABLE knobs, not decorative:
  complexity in [0, 1] scales search effort (n_restarts) and the
    permitted edge-strand multiplicity cap -- higher complexity allows a
    denser, more elaborate structure (max_multiplicity=2, more restarts
    to find a valid one) versus a sparser one (max_multiplicity=1).
  symmetry "auto" (default) never constrains the motif library --
    whatever D4 coverage the search naturally finds is reported via
    `structure.symmetry_coverage`, not forced. symmetry "strict"
    filters the motif library down to only individually D4-self-
    symmetric motifs (a motif unchanged by at least one non-identity D4
    transform) BEFORE search -- a real structural restriction on what
    can be stamped, not a post-hoc label.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

Point = tuple[int, int]

SIZE_TO_DIMS: dict[str, tuple[int, int]] = {
    "small": (10, 10),
    "medium": (16, 16),
    "large": (22, 22),
}

_MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent
    / "experiments" / "m5_generation" / "data" / "split_manifest.json"
)
_N_LIBRARY_SOURCES = 5


@lru_cache(maxsize=1)
def _default_motif_pool():
    """Motif library + reference source patterns, built ONCE per process
    from a fixed, small pool of held-out (test-split) real patterns --
    never train/val patterns (experiments/m5_generation/data/split_manifest.json,
    same leakage-safe split engine.learned_scoring's training data uses).
    Cached (lru_cache) because inducing motifs from real CSV data is not
    free and this pool does not change between calls."""
    from engine.dataset import load_kolam
    from engine.generation_api import motif_library_from_sources

    manifest = json.loads(_MANIFEST_PATH.read_text())
    test_sources = [tuple(s.split("#")) for s in manifest["test"]]
    test_sources = [(c, int(p)) for c, p in test_sources]

    library_sources = test_sources[:_N_LIBRARY_SOURCES]
    library = motif_library_from_sources(list(library_sources))
    reference_sources = [load_kolam(c, p) for c, p in test_sources]
    return library, reference_sources, library_sources


def _is_self_symmetric(motif) -> bool:
    """True if `motif` is mapped to itself by at least one NON-IDENTITY
    D4 transform -- a real structural property (the motif looks the same
    after that rotation/reflection), not a label."""
    from engine.symmetry import D4_TRANSFORMS, apply_transform

    for name in D4_TRANSFORMS:
        if name == "identity":
            continue
        if apply_transform(name, motif) == motif:
            return True
    return False


def generate_kolam(
    seed: int,
    complexity: float = 0.7,
    symmetry: str = "auto",
    size: str = "medium",
) -> dict:
    """Generate one novel kolam from a seed alone -- no input image, no
    caller-supplied pattern or lattice required.

    Returns:
      seed             : int, the seed used (echoed back for reproducibility)
      structure        : StructuralRepresentation.to_dict() (dot_points,
                          lattice dims, edges, degree distribution,
                          Eulerian validity, symmetry coverage, ...) --
                          see engine.generation_contract.StructuralRepresentation
      dot_positions    : same as structure["dot_points"], surfaced at the
                          top level per the requested conceptual interface
      edges            : same as structure["edges"]
      paths            : structure["dot_trace"] -- ordered stroke path,
                          None if the candidate is not a valid single stroke
      valid            : bool, candidate.is_valid after bounded repair
      score            : validity_score in [0,1] (1.0 = fully valid; see
                          engine.novelty._candidate_validity_score for the
                          partial-credit heuristic used when invalid)
      svg              : rendered SVG string (engine.render, always present)
      config           : {complexity, symmetry, size, n_restarts,
                          max_multiplicity, lattice_width, lattice_height,
                          motif_library_size, motif_sources} -- exactly
                          what was actually used, so a caller/log can
                          audit a specific generation call after the fact

    Deterministic given the same seed and config; changing `seed` with
    everything else fixed changes the multi-restart search's shuffle
    order (see engine.learned_generation._single_restart_placements),
    which routinely produces a structurally different candidate (see
    experiments/m5_generation/results/benchmark_report_lite.json's
    n_unique_fingerprints for the measured rate).
    """
    if size not in SIZE_TO_DIMS:
        raise ValueError(f"size must be one of {sorted(SIZE_TO_DIMS)}, got {size!r}")
    if not (0.0 <= complexity <= 1.0):
        raise ValueError(f"complexity must be in [0, 1], got {complexity!r}")
    if symmetry not in ("auto", "strict"):
        raise ValueError(f"symmetry must be 'auto' or 'strict', got {symmetry!r}")

    from engine.generation_api import rectangular_lattice
    from engine.learned_generation import generate_novel_kolam_learned
    from engine.learned_scoring import load_scorer
    from engine.novelty import _candidate_validity_score, novelty_report
    from engine.render import render_generated_kolam_svg
    from engine.generation_contract import build_representation

    width, height = SIZE_TO_DIMS[size]
    dots = rectangular_lattice(width, height)

    library, reference_sources, library_sources = _default_motif_pool()
    if symmetry == "strict":
        filtered = [m for m in library if _is_self_symmetric(m)]
        if filtered:  # fall back to the unfiltered library rather than search with an empty one
            library = filtered

    n_restarts = max(2, round(2 + complexity * 10))  # complexity 0.0 -> 2, 1.0 -> 12
    max_multiplicity = 2 if complexity >= 0.5 else 1

    scorer = load_scorer()
    # Single search run (not engine.generation_contract.generate_kolam,
    # which would require a second identical run to also get the graph
    # for dot_positions/edges/paths below) -- everything this function
    # returns is derived from this ONE run's candidate.
    run = generate_novel_kolam_learned(
        library, dots, scorer=scorer, max_multiplicity=max_multiplicity,
        n_restarts=n_restarts, seed=seed,
    )
    candidate = run.candidate
    structure = build_representation(candidate)
    novelty = novelty_report([candidate], reference_sources)

    return {
        "seed": seed,
        "structure": structure.to_dict(),
        "dot_positions": structure.dot_points,
        "edges": structure.edges,
        "paths": structure.dot_trace,
        "valid": candidate.is_valid,
        "score": _candidate_validity_score(candidate),
        "svg": render_generated_kolam_svg(candidate),
        "novelty": novelty,
        "config": {
            "complexity": complexity,
            "symmetry": symmetry,
            "size": size,
            "n_restarts": n_restarts,
            "max_multiplicity": max_multiplicity,
            "lattice_width": width,
            "lattice_height": height,
            "motif_library_size": len(library),
            "motif_sources": [f"{c}#{p}" for c, p in library_sources],
        },
    }
