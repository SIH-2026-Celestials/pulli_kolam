"""M7 platform integration: the new, persisted generation/analysis/
model-registry endpoints.

Kept in a SEPARATE module (not added directly into api/main.py's
560-line body) and wired in via `app.include_router(router)` -- the
existing `/api/v1/generate` endpoint in api/main.py is UNTOUCHED, kept
for backward compatibility with its existing tests and the frontend's
prior integration; these new endpoints are additive, sharing the SAME
underlying M5 call path (api.services.generation.generate) so both
routes stay behaviorally consistent without duplicating the generation
logic itself.

Preserves the existing error envelope
({"success": false, "error": ..., "code": ...}) via the SAME
`_api_error`/exception-handler pattern api/main.py already established
-- this module raises the same HTTPException shape, no second error
convention introduced.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from api.rate_limit import GENERATION_LIMIT_PER_MINUTE, enforce_rate_limit
from api.db.database import get_session
from api.db.models import (
    GenerationRequest,
    GenerationResult,
    GenerationRun,
    Model,
    ModelVersion,
    PatternAnalysis,
    PatternVersion,
    VerificationResult,
)

router = APIRouter(prefix="/api/v1")


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


# ============================================================
# Request/response schemas
# ============================================================

class CreateGenerationRequest(BaseModel):
    seed: Optional[int] = None
    count: Optional[int] = 1
    verify_recognizer: Optional[bool] = False


class AnalyzePatternRequest(BaseModel):
    """A caller-submitted structural representation -- dot_points +
    edges, the same shape engine.generation_contract.StructuralRepresentation
    already produces (a subset is sufficient: this endpoint only needs
    dot_points and edges to rebuild an nx.MultiGraph; other fields, if
    present, are ignored)."""

    dot_points: list[list[int]]
    edges: list[list[list[int]]]


MAX_GENERATE_COUNT = 5  # same cap api/main.py's existing /generate endpoint already enforces


def _build_graph(dot_points: list, edges: list):
    import networkx as nx

    G = nx.MultiGraph()
    G.add_nodes_from(tuple(p) for p in dot_points)
    for a, b in edges:
        G.add_edge(tuple(a), tuple(b))
    return G


def _pattern_version_to_json(pv: PatternVersion) -> dict:
    return {
        "id": pv.id,
        "pattern_id": pv.pattern_id,
        "representation": pv.representation_json,
        "fingerprint": pv.fingerprint,
        "n_dots": pv.n_dots,
        "n_distinct_edges": pv.n_distinct_edges,
        "is_valid": pv.is_valid,
        "created_at": pv.created_at.isoformat(),
    }


def _analysis_to_json(a: "PatternAnalysis | None") -> "dict | None":
    if a is None:
        return None
    return {
        "graph": {
            "vertices": a.vertices, "edges": a.edges, "distinct_edges": a.distinct_edges,
            "connected_components": a.connected_components, "density": a.graph_density,
        },
        "eulerian": {
            "odd_degree_vertex_count": a.odd_degree_vertex_count,
            "largest_component_covers_all_nodes": a.largest_component_covers_all_nodes,
            "is_eulerian_circuit": a.is_eulerian_circuit, "has_eulerian_path": a.has_eulerian_path,
        },
        "multiplicity": {
            "max_multiplicity": a.max_multiplicity, "distribution": a.multiplicity_distribution,
            "violations": a.multiplicity_violations,
        },
        "symmetry": {"coverage": a.symmetry_coverage, "dominant_transform_sample": a.symmetry_transform},
        "complexity": {"complexity_score": a.complexity_score, "density_score": a.density_score},
        "novelty": {"novelty_score": a.novelty_score, "nearest_source_id": a.nearest_source_id},
        "computed_at": a.computed_at.isoformat(),
    }


def _verification_to_json(rows: list) -> list:
    return [
        {
            "method": v.method, "is_valid": v.is_valid, "n_expected": v.n_expected, "n_detected": v.n_detected,
            "recall": v.recall, "precision": v.precision, "notes": v.notes,
            "model_version_id": v.model_version_id, "verified_at": v.verified_at.isoformat(),
        }
        for v in rows
    ]


def _model_version_to_json(mv: ModelVersion) -> dict:
    return {
        "id": mv.id, "model_name": mv.model.name, "version": mv.version, "status": mv.status,
        "metrics": mv.metrics, "created_at": mv.created_at.isoformat(),
    }


# ============================================================
# Generations
# ============================================================

@router.get("/generations")
def list_generations(page: int = 1, page_size: int = 20):
    """Paginated generation HISTORY -- Phase 13's explicit requirement.
    Deliberately a LIGHT payload per row (no SVG, no full representation,
    no full analysis blob) -- "avoid returning huge unnecessary payloads
    in list endpoints" -- a caller drills into one result via
    GET /generations/{id} for the full detail this list intentionally
    omits."""
    if page < 1:
        raise _api_error(422, "INVALID_REQUEST", f"page must be >= 1, got {page}")
    if not (1 <= page_size <= 100):
        raise _api_error(422, "INVALID_REQUEST", f"page_size must be in [1, 100], got {page_size}")

    session = get_session()
    try:
        total = session.query(GenerationResult).count()
        rows = (
            session.query(GenerationResult)
            .order_by(GenerationResult.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        items = []
        for r in rows:
            run = session.get(GenerationRun, r.run_id)
            model_version = session.get(ModelVersion, run.model_version_id) if run else None
            pv = session.get(PatternVersion, r.pattern_version_id)
            analysis = session.query(PatternAnalysis).filter_by(pattern_version_id=r.pattern_version_id).one_or_none()
            items.append(
                {
                    "id": r.id,
                    "run_id": r.run_id,
                    "seed": r.seed,
                    "is_valid": r.is_valid,
                    "created_at": r.created_at.isoformat(),
                    "generator": model_version.model.name if model_version else None,
                    "generator_version": model_version.version if model_version else None,
                    "n_dots": pv.n_dots if pv else None,
                    "novelty_score": analysis.novelty_score if analysis else None,
                    "symmetry_coverage": analysis.symmetry_coverage if analysis else None,
                    "complexity_score": analysis.complexity_score if analysis else None,
                }
            )

        return {
            "success": True, "page": page, "page_size": page_size, "total": total,
            "total_pages": (total + page_size - 1) // page_size if page_size else 0,
            "items": items,
        }
    finally:
        session.close()


@router.post("/generations")
def create_generation(request: Request, body: CreateGenerationRequest):
    """Generate + PERSIST N candidates. Same underlying M5 call path as
    the legacy /api/v1/generate, plus full analysis/verification/artifact
    persistence and a stable `run_id`/per-candidate `id` for later
    retrieval (Phase 10's generation-history requirement).

    THE canonical, frontend-facing generation endpoint (see
    PRODUCTION_READINESS.md section 1) -- this is the one that most
    needs rate limiting, since it is the only generation path the real
    UI calls. See api/rate_limit.py for the limit's justification."""
    enforce_rate_limit(request, "generations", GENERATION_LIMIT_PER_MINUTE)
    count = body.count if body.count is not None else 1
    if not isinstance(count, int) or count < 1:
        raise _api_error(422, "INVALID_REQUEST", f"count must be a positive integer, got {body.count!r}")
    if count > MAX_GENERATE_COUNT:
        raise _api_error(422, "INVALID_REQUEST", f"count must be <= {MAX_GENERATE_COUNT}, got {count}")

    from api.services.generation import GenerationUnavailableError, generate

    session = get_session()
    try:
        try:
            result = generate(session, seed=body.seed, count=count, verify_recognizer=bool(body.verify_recognizer))
        except GenerationUnavailableError as e:
            raise _api_error(503, "GENERATION_MODEL_UNAVAILABLE", str(e)) from e

        return {
            "success": True,
            "run_id": result.run_id,
            "request_id": result.request_id,
            "model_version": result.model_version,
            "total_latency_ms": round(result.total_latency_ms, 2),
            "candidates": [
                {
                    "id": c.generation_result_id,
                    "pattern_version_id": c.pattern_version_id,
                    "seed": c.seed,
                    # `status`/`is_valid` say the SAME thing two ways
                    # deliberately: `is_valid` is the original field the
                    # frontend already consumes (kept, unchanged, for
                    # backward compatibility); `status` is the exact
                    # field name this task's canonical pipeline spec
                    # asks for. Never diverge -- both are always derived
                    # from the one real is_valid boolean, never set
                    # independently.
                    "status": "valid" if c.is_valid else "invalid",
                    "is_valid": c.is_valid,
                    "svg": c.svg,
                    "render_svg": c.svg,  # kept for existing frontend callers -- see `svg` for the canonical name
                    "graph": {
                        "dot_points": c.representation.get("dot_points"),
                        "edges": c.representation.get("edges"),
                        "degree_distribution": c.representation.get("degree_distribution"),
                    },
                    "mathematics": c.analysis,
                    "analysis": c.analysis,  # kept for existing frontend callers -- see `mathematics` for the canonical name
                    "verification": c.verification,
                    "novelty": c.analysis.get("novelty"),
                    "generation_time_ms": round(c.latency_ms, 2),
                    "latency_ms": round(c.latency_ms, 2),  # kept for existing frontend callers
                    "metadata": {"generator": "M5", "model_version": result.model_version, "seed": c.seed},
                }
                for c in result.candidates
            ],
        }
    finally:
        session.close()


@router.get("/generations/{result_id}")
def get_generation(result_id: str):
    """Retrieve one previously-persisted generation candidate by its
    GenerationResult id -- Phase 10's "retrieve previous generations"
    requirement. Returns request/seed/model/timestamp/SVG/structural
    representation/analysis/verification together in one response."""
    session = get_session()
    try:
        result_row = session.get(GenerationResult, result_id)
        if result_row is None:
            raise _api_error(404, "NOT_FOUND", f"generation result {result_id!r} not found")

        run = session.get(GenerationRun, result_row.run_id)
        request_row = session.get(GenerationRequest, run.request_id)
        pv = session.get(PatternVersion, result_row.pattern_version_id)
        analysis = session.query(PatternAnalysis).filter_by(pattern_version_id=pv.id).one_or_none()
        verifications = session.query(VerificationResult).filter_by(pattern_version_id=pv.id).all()
        model_version = session.get(ModelVersion, run.model_version_id)

        svg = None
        artifact = pv.artifacts[0] if pv.artifacts else None
        if artifact is not None:
            from api.services.artifact_store import get_artifact_store
            store = get_artifact_store()
            svg = store.read(artifact.storage_path)

        return {
            "success": True,
            "id": result_row.id,
            "run_id": run.id,
            "request": request_row.params,
            "seed": result_row.seed,
            "model": {"name": model_version.model.name, "version": model_version.version},
            "created_at": result_row.created_at.isoformat(),
            "is_valid": result_row.is_valid,
            "render_svg": svg,
            "representation": pv.representation_json,
            "analysis": _analysis_to_json(analysis),
            "verification": _verification_to_json(verifications),
        }
    finally:
        session.close()


@router.get("/generations/{result_id}/mathematics")
def get_generation_mathematics(result_id: str):
    """Mathematics-only view -- no SVG, no raw representation, just the
    PatternAnalysis row (Phase 9's "Mathematics panel" data source)."""
    session = get_session()
    try:
        result_row = session.get(GenerationResult, result_id)
        if result_row is None:
            raise _api_error(404, "NOT_FOUND", f"generation result {result_id!r} not found")
        analysis = session.query(PatternAnalysis).filter_by(pattern_version_id=result_row.pattern_version_id).one_or_none()
        if analysis is None:
            raise _api_error(404, "NOT_FOUND", "analysis not available for this generation result")
        return {"success": True, "id": result_id, "mathematics": _analysis_to_json(analysis)}
    finally:
        session.close()


@router.get("/generations/{result_id}/graph")
def get_generation_graph(result_id: str):
    """Graph-only view -- dot_points + edges only (Phase 9's "Graph
    view" data source), trimmed from the full representation."""
    session = get_session()
    try:
        result_row = session.get(GenerationResult, result_id)
        if result_row is None:
            raise _api_error(404, "NOT_FOUND", f"generation result {result_id!r} not found")
        pv = session.get(PatternVersion, result_row.pattern_version_id)
        rep = pv.representation_json
        return {
            "success": True, "id": result_id,
            "graph": {
                "dot_points": rep.get("dot_points"), "edges": rep.get("edges"),
                "degree_distribution": rep.get("degree_distribution"),
            },
        }
    finally:
        session.close()


_EXPORT_CONTENT_TYPES = {"svg": "image/svg+xml", "png": "image/png", "json": "application/json"}


@router.get("/generations/{result_id}/export")
def export_generation(result_id: str, format: str = "svg"):  # noqa: A002 -- "format" is the natural query param name here
    """Phase 14: download the persisted artifact (SVG/PNG/JSON) for one
    generation result. Reads from the SAME Artifact rows/ArtifactStore
    api/services/generation.py already wrote at generation time -- no
    re-rendering, no filesystem path ever exposed to the caller (the
    response IS the file bytes, with a Content-Disposition header, not
    a path string)."""
    if format not in _EXPORT_CONTENT_TYPES:
        raise _api_error(422, "INVALID_REQUEST", f"format must be one of {sorted(_EXPORT_CONTENT_TYPES)}, got {format!r}")

    session = get_session()
    try:
        result_row = session.get(GenerationResult, result_id)
        if result_row is None:
            raise _api_error(404, "NOT_FOUND", f"generation result {result_id!r} not found")
        pv = session.get(PatternVersion, result_row.pattern_version_id)
        artifact = next((a for a in pv.artifacts if a.artifact_type == format), None)
        if artifact is None:
            raise _api_error(404, "NOT_FOUND", f"no {format!r} artifact available for this generation result")

        from api.services.artifact_store import get_artifact_store

        store = get_artifact_store()
        content_type = _EXPORT_CONTENT_TYPES[format]
        if format == "png":
            content = store.read_bytes(artifact.storage_path)
        else:
            content = store.read(artifact.storage_path)
        if content is None:
            raise _api_error(404, "NOT_FOUND", "artifact record exists but the underlying file is missing")

        headers = {"Content-Disposition": f'attachment; filename="pulli-kolam-{result_id}.{format}"'}
        return Response(content=content, media_type=content_type, headers=headers)
    finally:
        session.close()


# ============================================================
# Patterns (submit an arbitrary structural representation)
# ============================================================

@router.post("/patterns/analyze")
def analyze_pattern(body: AnalyzePatternRequest):
    """Run every analyzer on a CALLER-SUBMITTED structural representation
    -- does not require it to have come from M5 generation (useful for a
    future upload/detection flow feeding a real detected structure
    through the same analysis pipeline)."""
    from api.services.analysis import analyze_all

    if not body.dot_points:
        raise _api_error(422, "INVALID_REQUEST", "dot_points must be non-empty")
    G = _build_graph(body.dot_points, body.edges)
    result = analyze_all(G)
    return {"success": True, "analysis": result}


@router.post("/patterns/verify")
def verify_pattern(body: AnalyzePatternRequest):
    """Run the deterministic structural hard-gate on a caller-submitted
    representation. Does NOT run recognizer self-consistency (that
    requires a rendered image derived from a full GeneratedKolam, not
    just a bare graph) -- structural verification alone is still a
    real, meaningful check (the same one that gates every M5 candidate)."""
    from api.services.verification import verify_structural

    if not body.dot_points:
        raise _api_error(422, "INVALID_REQUEST", "dot_points must be non-empty")
    G = _build_graph(body.dot_points, body.edges)
    v = verify_structural(G)
    return {"success": True, "verification": v.__dict__}


# ============================================================
# Model registry
# ============================================================

@router.get("/models")
def list_models():
    session = get_session()
    try:
        versions = session.query(ModelVersion).all()
        return {"success": True, "models": [_model_version_to_json(v) for v in versions]}
    finally:
        session.close()


@router.get("/models/{model_version_id}")
def get_model(model_version_id: str):
    session = get_session()
    try:
        mv = session.get(ModelVersion, model_version_id)
        if mv is None:
            raise _api_error(404, "NOT_FOUND", f"model version {model_version_id!r} not found")
        return {"success": True, "model": _model_version_to_json(mv)}
    finally:
        session.close()
