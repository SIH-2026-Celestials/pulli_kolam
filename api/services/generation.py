"""M7 platform integration: the framework-independent GenerationService.

    generate(request) -> GenerationServiceResult (request persisted, N candidates)

Internally reuses `api.generation_service.get_generation_service()` (the
EXISTING lazy M5 loader, UNMODIFIED) and `engine.learned_generation`
(M5's OWN algorithm, UNMODIFIED, no rewrite, no checkpoint change) --
this module adds PERSISTENCE and ANALYSIS/VERIFICATION around M5, it
does not touch M5 itself. No FastAPI import anywhere in this file --
callable from a script, a test, or (as api/routes_generations.py does)
a request handler, identically.

MODEL REGISTRY ENFORCEMENT: this service resolves the "production"
M5 ModelVersion from the database (api.db.seed's seeded row) and
refuses to run if none exists with status="production" -- it will
NEVER invoke a "research" status model (M6) for live generation, this
is checked explicitly (see `_resolve_production_generator`), not just
documented.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from api.db.models import (
    Artifact,
    GenerationRequest,
    GenerationResult,
    GenerationRun,
    ModelVersion,
    Pattern,
    PatternAnalysis,
    PatternVersion,
    VerificationResult,
)
from api.services.analysis import analyze_all
from api.services.verification import verify_structural, verify_with_recognizer

_STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage" / "artifacts"


@dataclass
class GenerationCandidateResult:
    generation_result_id: str
    pattern_version_id: str
    seed: int
    is_valid: bool
    representation: dict
    analysis: dict
    verification: dict
    svg: str
    latency_ms: float


@dataclass
class GenerationServiceResult:
    run_id: str
    request_id: str
    model_version: str
    candidates: "list[GenerationCandidateResult]"
    total_latency_ms: float


class GenerationUnavailableError(RuntimeError):
    pass


def _resolve_production_generator(session: Session) -> ModelVersion:
    """The ONLY model-selection logic in this service: query for the
    model_version row with status == "production". A "research" row
    (M6) is structurally ineligible -- there is no code path here that
    can select it, seeded or not."""
    mv = (
        session.query(ModelVersion)
        .filter(ModelVersion.status == "production")
        .order_by(ModelVersion.created_at.desc())
        .first()
    )
    if mv is None:
        raise GenerationUnavailableError("no ModelVersion with status='production' found in the registry")
    return mv


def generate(
    session: Session,
    seed: "int | None",
    count: int,
    verify_recognizer: bool = False,
    reference_sources: "list | None" = None,
) -> GenerationServiceResult:
    """The framework-independent entry point. Persists a
    GenerationRequest + GenerationRun + one GenerationResult (and its
    Pattern/PatternVersion/PatternAnalysis/VerificationResult/Artifact)
    per candidate, then returns everything in one assembled result so a
    caller (e.g. the API route) doesn't need a second round-trip to
    read back what was just written.
    """
    import os

    from api.generation_service import get_generation_service
    from engine.learned_generation import generate_novel_kolam_learned
    from engine.render import render_generated_kolam_svg

    production_mv = _resolve_production_generator(session)

    m5_service = get_generation_service()
    if not m5_service.available:
        raise GenerationUnavailableError(m5_service.load_error or "M5 generation service unavailable")

    request_row = GenerationRequest(params={"seed": seed, "count": count, "verify_recognizer": verify_recognizer})
    session.add(request_row)
    session.flush()

    run_row = GenerationRun(request_id=request_row.id, model_version_id=production_mv.id, candidate_count=count)
    session.add(run_row)
    session.flush()

    base_seed = seed if seed is not None else int.from_bytes(os.urandom(4), "big")
    _STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    candidates: list[GenerationCandidateResult] = []
    t_start = time.monotonic()

    for i in range(count):
        this_seed = base_seed + i
        _layout_name, dots = m5_service.layout_for_seed(this_seed)
        t0 = time.monotonic()
        run_result = generate_novel_kolam_learned(
            m5_service.motif_library, dots, scorer=m5_service.scorer, seed=this_seed,
        )
        latency_ms = (time.monotonic() - t0) * 1000
        candidate = run_result.candidate

        from engine.generation_contract import build_representation
        from engine.novelty import graph_fingerprint

        representation = build_representation(candidate)
        fingerprint = repr(graph_fingerprint(candidate.graph))

        pattern_row = Pattern(kind="generated")
        session.add(pattern_row)
        session.flush()

        pv_row = PatternVersion(
            pattern_id=pattern_row.id,
            representation_json=representation.to_dict(),
            fingerprint=fingerprint,
            n_dots=representation.n_nodes,
            n_distinct_edges=representation.n_distinct_edges,
            is_valid=candidate.is_valid,
        )
        session.add(pv_row)
        session.flush()

        analysis = analyze_all(candidate, reference_sources or [])
        session.add(
            PatternAnalysis(
                pattern_version_id=pv_row.id,
                vertices=analysis["graph"]["vertices"], edges=analysis["graph"]["edges"],
                distinct_edges=analysis["graph"]["distinct_edges"],
                connected_components=analysis["graph"]["connected_components"],
                graph_density=analysis["graph"]["density"],
                odd_degree_vertex_count=analysis["eulerian"]["odd_degree_vertex_count"],
                largest_component_covers_all_nodes=analysis["eulerian"]["largest_component_covers_all_nodes"],
                is_eulerian_circuit=analysis["eulerian"]["is_eulerian_circuit"],
                has_eulerian_path=analysis["eulerian"]["has_eulerian_path"],
                max_multiplicity=analysis["multiplicity"]["max_multiplicity"],
                multiplicity_distribution=analysis["multiplicity"]["distribution"],
                multiplicity_violations=analysis["multiplicity"]["violations"],
                symmetry_coverage=analysis["symmetry"]["coverage"],
                symmetry_transform=analysis["symmetry"]["dominant_transform_sample"],
                complexity_score=analysis["complexity"]["complexity_score"],
                density_score=analysis["complexity"]["density_score"],
                novelty_score=analysis["novelty"]["novelty_score"],
                nearest_source_id=analysis["novelty"]["nearest_source_id"],
            )
        )

        struct_v = verify_structural(candidate)
        session.add(
            VerificationResult(
                pattern_version_id=pv_row.id, method=struct_v.method, is_valid=struct_v.is_valid,
                n_expected=struct_v.n_expected, n_detected=struct_v.n_detected,
                recall=struct_v.recall, precision=struct_v.precision, notes=struct_v.notes,
            )
        )
        verification_dict = {"structural_hard_gate": struct_v.__dict__}

        if verify_recognizer:
            verifier_mv = (
                session.query(ModelVersion)
                .filter(ModelVersion.status == "production-verifier")
                .order_by(ModelVersion.created_at.desc())
                .first()
            )
            rec_v = verify_with_recognizer(candidate)
            session.add(
                VerificationResult(
                    pattern_version_id=pv_row.id,
                    model_version_id=verifier_mv.id if verifier_mv else None,
                    method=rec_v.method, is_valid=rec_v.is_valid,
                    n_expected=rec_v.n_expected, n_detected=rec_v.n_detected,
                    recall=rec_v.recall, precision=rec_v.precision, notes=rec_v.notes,
                )
            )
            verification_dict["recognizer_self_consistency"] = rec_v.__dict__

        svg = render_generated_kolam_svg(candidate)
        artifact_path = _STORAGE_DIR / f"{pv_row.id}.svg"
        artifact_path.write_text(svg, encoding="utf-8")
        session.add(
            Artifact(
                pattern_version_id=pv_row.id, artifact_type="svg",
                storage_path=f"artifacts/{pv_row.id}.svg", content_type="image/svg+xml",
            )
        )

        result_row = GenerationResult(
            run_id=run_row.id, pattern_version_id=pv_row.id, seed=this_seed,
            is_valid=candidate.is_valid, latency_ms=latency_ms, rank=i,
        )
        session.add(result_row)
        session.flush()

        candidates.append(
            GenerationCandidateResult(
                generation_result_id=result_row.id, pattern_version_id=pv_row.id, seed=this_seed,
                is_valid=candidate.is_valid, representation=representation.to_dict(),
                analysis=analysis, verification=verification_dict, svg=svg, latency_ms=latency_ms,
            )
        )

    total_latency_ms = (time.monotonic() - t_start) * 1000
    run_row.total_latency_ms = total_latency_ms
    session.commit()

    return GenerationServiceResult(
        run_id=run_row.id, request_id=request_row.id, model_version=production_mv.version,
        candidates=candidates, total_latency_ms=total_latency_ms,
    )
