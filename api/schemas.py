"""Pydantic request/response models for the M4.2 REST API. Plain
primitives only -- see api/canonical.py's module docstring for why."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

DetectorName = Literal["classical", "ml", "ml-gated"]


class HealthResponse(BaseModel):
    status: str
    classical_detector_available: bool
    ml_detector_available: bool
    # ml-gated wraps the SAME checkpoint as ml (see api/detectors.py's
    # GatedMLDetector) -- availability tracks the same checkpoint file.
    gated_detector_available: bool = False


class ModelInfoResponse(BaseModel):
    # Original fields -- unchanged, existing consumers keep working.
    ml_model_version: Optional[str]
    ml_checkpoint_exists: bool
    ml_model_input_size: Optional[int]
    ml_heatmap_size: Optional[int]
    classical_detector: str
    # experimental lattice-consistency-gated variant (see
    # docs/M4_1_ML_COMPLETION_REPORT.md Section 10) -- same checkpoint,
    # different post-detection filtering; distinct MODEL_VERSION string.
    gated_model_version: Optional[str] = None
    # Additive fields (Phase 9): richer, honest model metadata. No
    # accuracy/quality claim is included here -- see docs/M4_1_ML_INVESTIGATION.md
    # and docs/M4_2_EVALUATION.md for the actual (documented, not
    # fabricated) evaluation results, which do not belong in a live
    # status endpoint's response.
    ml_model_name: Optional[str] = None
    ml_parameter_count: Optional[int] = None
    ml_device: Optional[str] = None
    ml_loaded: bool = False
    ml_inference_mode: Optional[str] = None
    classical_detector_status: str = "available"
    ml_detector_status: str = "unavailable"


class ImageInfo(BaseModel):
    width: int
    height: int


class Detection(BaseModel):
    x: float
    y: float


class ModelAttribution(BaseModel):
    """Which detector/model actually produced a given result -- attached
    to every detection/analysis/reconstruction response so a caller never
    has to infer provenance from the top-level `detector` string alone."""
    name: str
    version: Optional[str]
    device: str


class DetectResponse(BaseModel):
    success: bool
    detector: DetectorName
    model_version: Optional[str]
    image: ImageInfo
    detections: list[Detection]
    count: int
    processing_ms: float
    model: Optional[ModelAttribution] = None


class GraphSummary(BaseModel):
    nodes: int
    edges: int
    distinct_edges: int


class AnalyzeResponse(BaseModel):
    success: bool
    detector: DetectorName
    model_version: Optional[str]
    dots: list[Detection]
    dot_count: int
    processing_ms: float
    graph: GraphSummary
    motifs: dict
    validity: dict
    model: Optional[ModelAttribution] = None
    timing_ms: Optional[dict] = None


class ReconstructResponse(BaseModel):
    success: bool
    detector: DetectorName
    model_version: Optional[str]
    processing_ms: float
    graph: GraphSummary
    reconstruction: dict
    model: Optional[ModelAttribution] = None
    timing_ms: Optional[dict] = None


class DetectorComparisonSide(BaseModel):
    detector: DetectorName
    model_version: Optional[str]
    detections: list[Detection]
    count: int
    processing_ms: float
    error: Optional[str] = None


class CompareDetectorsResponse(BaseModel):
    success: bool
    image: ImageInfo
    classical: DetectorComparisonSide
    ml: DetectorComparisonSide
    agreement: dict


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    code: Optional[str] = None
    detail: Optional[str] = None


class GenerateRequest(BaseModel):
    seed: Optional[int] = None
    temperature: Optional[float] = None  # reserved: current search is deterministic-per-seed, see api/main.py
    count: Optional[int] = 1


class GenerationConstraintsInfo(BaseModel):
    """What request this candidate was generated against -- lattice size,
    motif source patterns -- so a caller can tell WHAT it asked for, not
    just what came back."""
    lattice_width: int
    lattice_height: int
    n_dots: int
    motif_source_collection: str
    motif_library_size: int


class GeneratedCandidate(BaseModel):
    seed: int
    is_valid: bool
    n_dots: int
    n_distinct_edges: int
    n_edge_instances: int
    connected_components: int
    n_odd_degree_nodes: int
    n_nodes_outside_largest_component: int
    multiplicity_violations: int
    symmetry_coverage: Optional[float]
    novelty_note: str
    n_restarts_used: int
    repair_edges_applied: int
    generation_latency_ms: float
    render_svg: str
    dot_trace_length: Optional[int]


class GenerateResponse(BaseModel):
    success: bool
    model: dict
    constraints: GenerationConstraintsInfo
    candidates: list[GeneratedCandidate]
    total_latency_ms: float
