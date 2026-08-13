"""M4.0: the FROZEN interface an ML dot-lattice detector must satisfy to be
a drop-in replacement for engine.image_io.detect_lattice(). This module
defines the contract ONLY -- it contains no model code, no ML framework
dependency, and no behavior change to any existing consumer.

See docs/ML_CONTRACT.md for the full, human-readable specification this
Protocol formalizes (coordinate system, ordering guarantees, edge cases,
error behavior, and the one known pre-existing contract violation in the
CURRENT deterministic detector -- documented there, not fixed here).

WHY THIS EXISTS: M4's own readiness report (PROJECT_STATE.md, session 11)
named "freeze the ML-output -> deterministic-engine-input contract" as one
of exactly two conditions before model implementation may begin. This is
that freeze. Downstream code (engine.image_io.trace_path and everything
after it) is NOT modified to accommodate a future model -- the model must
conform to this Protocol, not the other way around.
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from engine.image_io import Lattice, Preprocessed

# The contract, as a plain type alias: any zero-state function/callable
# matching detect_lattice's own exact signature. This is the primary,
# preferred way to express "drop-in for detect_lattice" -- a plain module-
# level function (like detect_lattice itself) satisfies this directly,
# with no class/method wrapping required.
MLLatticeDetectorFn = Callable[[Preprocessed], Lattice]


@runtime_checkable
class MLLatticeDetector(Protocol):
    """Callable-object form of the same contract, for implementations that
    need to carry state (e.g. a loaded model checkpoint) and therefore
    can't be a bare function. Anything satisfying this Protocol -- a bare
    function matching MLLatticeDetectorFn, OR a callable object
    implementing __call__ with this exact signature -- can replace
    engine.image_io.detect_lattice as the dot-detection stage of
    engine.image_io.build_graph, with ZERO changes to preprocess(),
    trace_path(), or anything downstream of Lattice.

    Checked structurally via @runtime_checkable isinstance() at call
    sites that want to assert conformance (e.g. in contract tests) --
    see tests/test_ml_contract.py.

    See docs/ML_CONTRACT.md for the full output-shape and edge-case
    specification every implementation (deterministic or ML) must honor.
    """

    def __call__(self, preprocessed: Preprocessed) -> Lattice: ...


def assert_conforms(lattice: Lattice) -> None:
    """Structural conformance check for ANY MLLatticeDetector's output --
    deterministic or ML. Does not evaluate accuracy (that's the
    evaluation-metrics side of the contract, see docs/ML_CONTRACT.md
    Section 6); only checks the SHAPE invariants trace_path and
    downstream code rely on to not crash or silently corrupt data.

    Raises ValueError, naming the specific invariant violated, rather
    than letting a malformed Lattice propagate into an IndexError deep
    inside trace_path (see docs/ML_CONTRACT.md's documented pre-existing
    blocker: detect_lattice itself can currently violate invariant (b)
    below when 1-2 dots are detected -- this function exists specifically
    so that violation is caught at the contract boundary, with a clear
    message, rather than surfacing as a confusing crash three functions
    later).
    """
    n_pixels = len(lattice.pixel_positions)
    n_coords = len(lattice.lattice_coords)

    if n_coords not in (0, n_pixels):
        raise ValueError(
            "MLLatticeDetector contract violation: lattice_coords must be "
            "either empty or the same length as pixel_positions (index-"
            f"aligned), got {n_coords} coords for {n_pixels} pixel "
            "positions. A detector with fewer confident lattice-fit points "
            "than detected pixels must report ALL of them as empty "
            "(matching the '< 3 points -> degenerate' convention), not a "
            "partial/truncated list -- see docs/ML_CONTRACT.md Section 4."
        )
    if n_coords > 0 and len(set(lattice.lattice_coords)) != n_coords:
        raise ValueError(
            "MLLatticeDetector contract violation: lattice_coords contains "
            "duplicate integer coordinates -- every detected dot must map "
            "to a distinct lattice position (see docs/ML_CONTRACT.md "
            "Section 4, 'duplicate detections')."
        )
    if lattice.dot_radius < 0:
        raise ValueError(
            "MLLatticeDetector contract violation: dot_radius must be "
            f">= 0, got {lattice.dot_radius}."
        )
