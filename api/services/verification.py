"""M7 platform integration: verification service.

Two distinct verification methods, never conflated:

1. STRUCTURAL hard-gate (`verify_structural`): deterministic,
   engine.validity.check_validity, unmodified. Always runs, always
   free (no model inference) -- this is the SAME check that already
   determines `candidate.is_valid` everywhere else in this repository;
   this service exists so it's exposed as a first-class, persistable
   VerificationResult, not just an internal boolean.

2. RECOGNIZER self-consistency (`verify_with_recognizer`): renders the
   candidate, runs the FROZEN M4.2 detector against the rendered image,
   compares detected dots to the generator's OWN exact ground truth
   (same technique experiments/m5_generation/run_generation_benchmark.py
   and experiments/m6_generation/verify.py already established and
   validated). This is legitimate because ground truth here is exact
   (the generator's own output), NOT a claim about real-photo accuracy.

`PhotoVerifier` is an explicit ABSTRACTION (Protocol), not a concrete
photo-verification pipeline -- per this task's explicit instruction
("do NOT pretend M4.2 is a production photo verifier... keep photo
verification behind an abstraction so a stronger vision model can be
plugged in later"). The only concrete implementation today
(`M42PhotoVerifier`) is explicitly labeled UNRESOLVED for real-photo
precision/recall, reusing api.recognition_fusion's already-established
honesty discipline rather than inventing a new one.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

import networkx as nx

from engine.validity import check_validity, diagnose_validity


def _as_graph(obj) -> nx.MultiGraph:
    """`isinstance`, NOT `hasattr(obj, "graph")` -- nx.MultiGraph/Graph
    objects have their OWN built-in `.graph` attribute (a plain dict for
    graph-level metadata, defaults to `{}`), so `hasattr` is always True
    for a raw graph too and would wrongly try to use that metadata dict
    as if it were the graph itself. Same landmine already documented and
    fixed in engine/generation_contract.py's build_representation."""
    return obj if isinstance(obj, nx.MultiGraph) else obj.graph


@dataclass
class StructuralVerification:
    method: str
    is_valid: bool
    n_expected: "int | None" = None
    n_detected: "int | None" = None
    recall: "float | None" = None
    precision: "float | None" = None
    notes: "str | None" = None


def verify_structural(candidate) -> StructuralVerification:
    """Method: "structural_hard_gate". Free, deterministic, always run.
    Reuses engine.validity unmodified -- the SAME function that already
    sets candidate.is_valid, called again here explicitly so it produces
    a persistable, independently-auditable VerificationResult row rather
    than only living as a transient attribute on the in-memory object."""
    G = _as_graph(candidate)
    validity = check_validity(G)
    is_valid = validity["largest_component_covers_all_nodes"] and (
        validity["is_eulerian_circuit"] or validity["has_eulerian_path"]
    )
    diagnosis = diagnose_validity(G)
    notes = (
        f"connected_components={validity['connected_components']}, "
        f"odd_degree_nodes={diagnosis['n_odd_degree_nodes']}"
    )
    return StructuralVerification(method="structural_hard_gate", is_valid=is_valid, notes=notes)


def verify_with_recognizer(candidate, detector_name: str = "ml-gated") -> StructuralVerification:
    """Method: "recognizer_self_consistency". Renders the candidate to a
    temp PNG, runs the FROZEN M4.2 detector (api.detectors.get_detector,
    unmodified, never retrained here), compares against the candidate's
    OWN exact dot positions (same technique
    experiments/m6_generation/verify.py already validated). Costs real
    ML inference time -- callers (api/services/generation.py) make this
    OPT-IN per request, not run unconditionally on every candidate."""
    import tempfile
    import os

    from engine.render import DEFAULT_MARGIN, DEFAULT_SCALE, render_generated_kolam_png
    from api.detectors import get_detector

    dot_points = sorted(candidate.dot_points)
    n_expected = len(dot_points)
    if n_expected == 0:
        return StructuralVerification(method="recognizer_self_consistency", is_valid=False, n_expected=0, notes="empty candidate")

    fd, png_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        render_generated_kolam_png(candidate, png_path)
        detector = get_detector(detector_name)
        result = detector.detect(png_path)
    except Exception as e:  # noqa: BLE001 -- surfaced as a failed verification, not a crash
        return StructuralVerification(
            method="recognizer_self_consistency", is_valid=False, n_expected=n_expected,
            notes=f"{type(e).__name__}: {e}",
        )
    finally:
        if os.path.exists(png_path):
            os.unlink(png_path)

    import numpy as np
    from scipy.spatial import cKDTree

    xs = [p[0] for p in dot_points]
    ys = [p[1] for p in dot_points]
    min_x, min_y = min(xs), min(ys)
    gt_px = [(DEFAULT_MARGIN + (x - min_x) * DEFAULT_SCALE, DEFAULT_MARGIN + (y - min_y) * DEFAULT_SCALE) for x, y in dot_points]

    detected = result.dots
    n_detected = len(detected)
    if n_detected == 0:
        return StructuralVerification(
            method="recognizer_self_consistency", is_valid=False,
            n_expected=n_expected, n_detected=0, recall=0.0,
        )

    gt_arr = np.array(gt_px)
    det_arr = np.array(detected)
    tree = cKDTree(det_arr)
    dist, _idx = tree.query(gt_arr)
    matched = dist < 8.0
    n_matched = int(matched.sum())

    return StructuralVerification(
        method="recognizer_self_consistency",
        is_valid=(n_matched == n_expected),
        n_expected=n_expected, n_detected=n_detected,
        recall=n_matched / n_expected, precision=n_matched / n_detected,
        notes=f"self-consistency check against generator's own ground truth (detector={detector_name})",
    )


class PhotoVerifier(Protocol):
    """Abstraction for a FUTURE real-photograph verifier. No current
    implementation of this protocol claims production-grade real-photo
    accuracy -- see M42PhotoVerifier's own docstring. A stronger vision
    model can implement this Protocol and be swapped in without
    changing any caller."""

    def verify_photo(self, image_path: str) -> "StructuralVerification": ...


class M42PhotoVerifier:
    """The ONLY currently-available PhotoVerifier implementation --
    wraps api.recognition_fusion (classical + M4.2-gated consensus,
    unmodified). Explicitly NOT claimed as production-grade: real-photo
    precision/recall is UNRESOLVED (no ground-truth labels exist for
    real photographs, same finding
    experiments/m5_generation/results/real_photo_experiment.json
    already established) -- `notes` always says so, never silently
    omitted."""

    def verify_photo(self, image_path: str) -> StructuralVerification:
        from api.recognition_fusion import fuse_recognition

        fusion, _raw = fuse_recognition(image_path)
        return StructuralVerification(
            method="photo_recognition_fusion",
            is_valid=fusion.n_consensus_dots > 0,
            n_detected=fusion.n_consensus_dots,
            notes=(
                "real-photo precision/recall UNRESOLVED -- no ground-truth dot labels exist; "
                f"agreement_fraction={fusion.agreement_fraction}"
            ),
        )


class PatternVerifier(Protocol):
    """The GENERATED-PATTERN verifier interface, structurally distinct
    from `PhotoVerifier` above (real-photo input) -- never conflated:
    a `PatternVerifier` always verifies a structural candidate object
    (a `GeneratedKolam`/`nx.MultiGraph`, never image bytes)."""

    def verify(self, candidate) -> StructuralVerification: ...


class StructuralVerifier:
    """Class-shaped wrapper around `verify_structural` (unmodified --
    no new verification logic here, purely an interface adapter so
    `PatternVerifier` implementations can be selected/composed
    polymorphically, e.g. by `api/services/generation.py`)."""

    def verify(self, candidate) -> StructuralVerification:
        return verify_structural(candidate)


class M42RecognizerVerifier:
    """Class-shaped wrapper around `verify_with_recognizer` (unmodified
    -- the FROZEN M4.2 detector, never retrained, never modified). Optional
    because of latency: `api/services/generation.py` only invokes this
    when the caller explicitly opts in (`verify_recognizer=True`),
    exactly like the un-wrapped function it delegates to."""

    def __init__(self, detector_name: str = "ml-gated"):
        self.detector_name = detector_name

    def verify(self, candidate) -> StructuralVerification:
        return verify_with_recognizer(candidate, detector_name=self.detector_name)
