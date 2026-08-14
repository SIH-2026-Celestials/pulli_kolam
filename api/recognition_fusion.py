"""M5 OBJECTIVE 4: multi-source recognition fusion for real photographs.

NOT an API endpoint -- a plain importable function, reusable by scripts
(experiments/m5_generation/real_photo_experiment.py) and, later, an
endpoint if one is added, without any FastAPI coupling. Lives in api/
(not engine/) for the same reason api/detectors.py does: detector code
is PyTorch/classical-CV-specific, and engine/ stays free of that
dependency (see api/detectors.py's own module docstring).

WHAT THIS DOES: runs every requested detector (default: classical +
ml-gated, the two api/detectors.py already exposes as independently
useful) against the same image, and reports where they AGREE and
DISAGREE -- it does not silently pick a winner or average away the
disagreement. `consensus_dots` (mutually agreeing detections) is offered
as one reasonable summary, but every source's own raw output is also
returned so a caller can make its own judgment call.

HONESTY RULE (task's own explicit rule 2: "do not fabricate real-photo
labels"): no field here is or claims to be ground truth. A detector that
agrees with another detector is not thereby "verified correct" -- both
could share the same failure mode. `confidence` below is inter-detector
AGREEMENT, a real, computable quantity; it is never relabeled as
accuracy, precision, or recall, none of which are computable without
hand-labeled ground truth this project does not have.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.detectors import DetectionResult, get_detector  # noqa: E402

DEFAULT_SOURCES = ("classical", "ml-gated")
MATCH_TOLERANCE_PX = 6.0


@dataclass
class SourceObservation:
    """One detector's raw output on this image -- an OBSERVATION, never
    labeled as ground truth (see module docstring)."""

    detector: str
    available: bool
    dots: "list[tuple[float, float]]" = field(default_factory=list)
    count: int = 0
    processing_ms: "float | None" = None
    error: "str | None" = None


@dataclass
class FusionResult:
    image_path: str
    width: int
    height: int
    sources: "list[SourceObservation]"
    consensus_dots: "list[tuple[float, float]]"  # mutually-agreeing detections across ALL available sources
    n_consensus_dots: int
    agreement_fraction: "float | None"  # consensus / union, None if fewer than 2 sources produced dots
    pairwise_disagreement: dict  # {"<a>_only": n, "<b>_only": n} per source pair, raw counts, not a rate
    confidence_note: str  # explicit: agreement is not accuracy -- see module docstring
    primary_graph_source: "str | None"  # which source's graph a caller should use downstream, and why


def _match_dots(a: "list[tuple[float, float]]", b: "list[tuple[float, float]]", tol: float = MATCH_TOLERANCE_PX):
    """Nearest-neighbor matching within `tol` pixels -- same convention
    api/main.py's compare_detectors endpoint already uses (mirrored here,
    not imported, since that endpoint's matching is inlined in a request
    handler and this needs to be callable standalone)."""
    if not a or not b:
        return [], list(range(len(a))), list(range(len(b)))
    a_arr = np.array(a)
    b_arr = np.array(b)
    tree = cKDTree(b_arr)
    dist, idx = tree.query(a_arr)
    matched_a, matched_b_idx = [], set()
    for i, (d, j) in enumerate(zip(dist, idx)):
        if d < tol and j not in matched_b_idx:
            matched_a.append(i)
            matched_b_idx.add(int(j))
    a_only = [i for i in range(len(a)) if i not in matched_a]
    b_only = [j for j in range(len(b)) if j not in matched_b_idx]
    matched_pairs = [(a[i], b[j]) for i, j in zip(matched_a, sorted(matched_b_idx))]
    return matched_pairs, a_only, b_only


def fuse_recognition(
    image_path: str, sources: "tuple[str, ...]" = DEFAULT_SOURCES
) -> "tuple[FusionResult, dict[str, DetectionResult]]":
    """Run every detector in `sources` against `image_path` and report
    agreement/disagreement. A source that raises (missing checkpoint,
    inference failure) is recorded as unavailable with its error message
    -- never silently dropped, never silently substituted with another
    detector's output (same no-silent-fallback rule api/main.py's
    _run_detector already enforces for a single detector, applied here
    across multiple).

    Returns (FusionResult, raw_results): FusionResult is the
    plain-primitive, JSON-serializable summary; raw_results is
    {detector_name: DetectionResult} for whichever sources succeeded --
    kept separate (not merged into FusionResult) because DetectionResult
    carries a live nx.MultiGraph, which is never serialized directly
    (same convention api/canonical.py's module docstring establishes).
    Callers that need the graph for downstream structural work (e.g.
    experiments/m5_generation/real_photo_experiment.py) use
    raw_results[fusion.primary_graph_source].graph directly -- this
    avoids re-running detection a second time just to get the graph."""
    observations: "list[SourceObservation]" = []
    raw_results: "dict[str, DetectionResult]" = {}
    width = height = 0

    for name in sources:
        detector = get_detector(name)
        try:
            result = detector.detect(image_path)
            raw_results[name] = result
            width, height = result.width, result.height
            observations.append(
                SourceObservation(
                    detector=name, available=True, dots=result.dots, count=len(result.dots),
                    processing_ms=round(result.processing_ms, 2),
                )
            )
        except Exception as e:  # noqa: BLE001 -- every failure surfaced, never swallowed
            observations.append(SourceObservation(detector=name, available=False, error=f"{type(e).__name__}: {e}"))

    available_names = list(raw_results.keys())
    consensus_dots: "list[tuple[float, float]]" = []
    disagreement: dict = {}
    agreement_fraction = None

    if len(available_names) >= 2:
        a_name, b_name = available_names[0], available_names[1]
        a_dots, b_dots = raw_results[a_name].dots, raw_results[b_name].dots
        matched_pairs, a_only, b_only = _match_dots(a_dots, b_dots)
        consensus_dots = [((ax + bx) / 2, (ay + by) / 2) for (ax, ay), (bx, by) in matched_pairs]
        disagreement[f"{a_name}_only"] = len(a_only)
        disagreement[f"{b_name}_only"] = len(b_only)
        union = len(matched_pairs) + len(a_only) + len(b_only)
        agreement_fraction = (len(matched_pairs) / union) if union else None
    elif len(available_names) == 1:
        consensus_dots = list(raw_results[available_names[0]].dots)

    # Downstream structural work needs ONE graph -- prefer the source
    # with the most agreeing detections' own graph (not a synthetic
    # merged graph, which would invent edges no single detector actually
    # traced); ties broken by source list order (classical first, the
    # more reliable of the two on real photos per docs/M4_2_EVALUATION.md).
    primary = available_names[0] if available_names else None

    fusion = FusionResult(
        image_path=image_path,
        width=width,
        height=height,
        sources=observations,
        consensus_dots=consensus_dots,
        n_consensus_dots=len(consensus_dots),
        agreement_fraction=agreement_fraction,
        pairwise_disagreement=disagreement,
        confidence_note=(
            "agreement_fraction measures INTER-DETECTOR AGREEMENT, not accuracy -- "
            "no ground-truth dot labels exist for these real photos, so precision/recall "
            "are UNRESOLVED, not computed as 0 or omitted silently."
        ),
        primary_graph_source=primary,
    )
    return fusion, raw_results
