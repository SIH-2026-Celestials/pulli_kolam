"""M7 platform integration: domain model (SQLAlchemy ORM).

Maps the task's 11 requested domain concepts (Pattern, PatternVersion,
GenerationRequest, GenerationResult, PatternGraph, PatternAnalysis,
VerificationResult, Model, ModelVersion, GenerationRun, Artifact) onto
9 tables -- two deliberate, documented simplifications, not omissions:

  - PatternGraph is NOT a separate normalized table (one row per edge).
    A generated candidate has hundreds of edges (M5's own final
    benchmark measured a mean of ~320 distinct edges/candidate, see
    experiments/m5_generation/results/benchmark_report.json) and
    nothing in this platform currently needs per-edge relational
    queries (e.g. "find all patterns containing edge (3,4)-(3,5)") --
    the graph (dot_points + edges) is stored as a JSON field on
    PatternVersion instead, exactly the same information, no relational
    benefit given current query patterns. Revisit if a future feature
    needs per-edge querying.
  - GenerationRun's per-candidate output IS GenerationResult (one row
    per generated candidate, FK back to the run) -- there is no
    separate "job" concept distinct from "the batch of results a
    request produced," so introducing a 10th table with no distinct
    data would be pure ceremony.

MATHEMATICAL REPRESENTATION IS THE SOURCE OF TRUTH, SVG IS AN ARTIFACT:
`PatternVersion.representation_json` (dot positions, edges, degree
distribution, Eulerian status -- the exact fields
engine.generation_contract.StructuralRepresentation.to_dict() already
produces) is the durable, queryable record. `Artifact` rows point to
rendered SVG files on disk (api/storage/artifacts/) -- deleting every
Artifact row and re-rendering from `representation_json` via
engine.render must always be possible; the reverse (reconstructing the
graph FROM only an SVG) is not, which is exactly why SVG must never be
the only thing persisted.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Model(Base):
    """A generator/verifier FAMILY -- e.g. "M5", "M4.2", "M6". Never
    referenced directly by application code for behavior (see
    ModelVersion.status for that) -- exists so multiple versions of the
    same family can be listed together."""

    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    versions: Mapped[list["ModelVersion"]] = relationship(back_populates="model")


class ModelVersion(Base):
    """One specific, checkpointed version of a Model. `status` is the
    ONLY thing application code branches on ("production" = usable for
    live generation, "production-verifier" = usable for verification,
    "research" = listed for provenance/transparency but NEVER invoked
    by GenerationService or VerificationService -- enforced in
    api/services/generation.py and api/services/verification.py, not
    just documented here). `checkpoint_path` is repo-relative, resolved
    by services at load time -- no application code hardcodes a
    checkpoint path string outside this table's seeded rows (see
    api/db/seed.py)."""

    __tablename__ = "model_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    model_id: Mapped[str] = mapped_column(String(36), ForeignKey("models.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # "production" | "production-verifier" | "research"
    checkpoint_path: Mapped[str] = mapped_column(String(512), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    model: Mapped["Model"] = relationship(back_populates="versions")


class GenerationRequest(Base):
    """The request AS SUBMITTED -- params are stored verbatim (JSON) so
    a past request can always be re-examined even if the request schema
    changes later."""

    __tablename__ = "generation_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Soft reference to api.auth.models.User.id -- NOT a DB-enforced foreign
    # key, because auth lives in a separate SQLAlchemy Base/metadata (see
    # api/auth/db.py's module docstring) that may even be a physically
    # different database from this one. Nullable for pre-ownership rows
    # created before this column existed; those rows are intentionally
    # unowned (never returned to any user, see api/routes_generations.py's
    # ownership check) rather than retroactively guessed.
    user_id: Mapped["str | None"] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    runs: Mapped[list["GenerationRun"]] = relationship(back_populates="request")


class GenerationRun(Base):
    """One executed batch: the request, which ModelVersion generated
    it, and aggregate timing. `candidate_count` is denormalized (also
    derivable from `len(results)`) purely for a cheap list-view query
    that doesn't need to join/count every time."""

    __tablename__ = "generation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("generation_requests.id"), nullable=False)
    model_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("model_versions.id"), nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    request: Mapped["GenerationRequest"] = relationship(back_populates="runs")
    model_version: Mapped["ModelVersion"] = relationship()
    results: Mapped[list["GenerationResult"]] = relationship(back_populates="run")


class Pattern(Base):
    """A logical lineage id -- one Pattern can accumulate multiple
    PatternVersions over time (e.g. if a future feature re-derives or
    edits a structure). Every candidate M5 generates today creates
    exactly one Pattern with exactly one PatternVersion (`kind="generated"`)
    -- the lineage concept exists for forward-compatibility (e.g. a
    future "regenerate variation of this pattern" feature), not because
    today's generator produces multiple versions of anything."""

    __tablename__ = "patterns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="generated")  # "generated" | "uploaded" (future)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    versions: Mapped[list["PatternVersion"]] = relationship(back_populates="pattern")


class PatternVersion(Base):
    """THE SOURCE OF TRUTH for one structural candidate -- see module
    docstring. `representation_json` is
    engine.generation_contract.StructuralRepresentation.to_dict()'s
    exact output (dot_points, edges, degree_distribution, Eulerian
    status, symmetry_coverage, dot_trace, ...) -- not a re-derived or
    trimmed subset. `fingerprint` is the D4+translation-canonical
    signature from engine.novelty.graph_fingerprint (stored as its
    Python repr since a tuple-of-tuples isn't directly JSON-safe as a
    column type) -- stored for future exact-duplicate lookups, but NOT
    indexed: real-Postgres verification this session found large
    patterns (500 dots) produce a fingerprint repr long enough to exceed
    Postgres's btree index row-size limit (2704 bytes) --
    `psycopg2.errors.ProgramLimitExceeded`, never visible against SQLite
    (no such limit there). Nothing in this codebase currently queries by
    this column (grepped before removing the index) so dropping it costs
    nothing today; a future exact-duplicate-lookup feature should index
    an MD5 hash of this value instead (Postgres's own suggested fix for
    long indexed text), not re-add a plain btree index here."""

    __tablename__ = "pattern_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    pattern_id: Mapped[str] = mapped_column(String(36), ForeignKey("patterns.id"), nullable=False, index=True)
    representation_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    fingerprint: Mapped[str] = mapped_column(Text, nullable=True)
    n_dots: Mapped[int] = mapped_column(Integer, nullable=False)
    n_distinct_edges: Mapped[int] = mapped_column(Integer, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    pattern: Mapped["Pattern"] = relationship(back_populates="versions")
    analysis: Mapped["PatternAnalysis"] = relationship(back_populates="pattern_version", uselist=False)
    verifications: Mapped[list["VerificationResult"]] = relationship(back_populates="pattern_version")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="pattern_version")


class PatternAnalysis(Base):
    """One row per PatternVersion, all analyzer outputs together
    (api/services/analysis.py). A single row (not one row per analyzer)
    because every analyzer runs on the SAME graph in the SAME request
    and nothing currently needs to version/compare analyzer runs
    independently of the structure they analyzed."""

    __tablename__ = "pattern_analysis"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    pattern_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("pattern_versions.id"), unique=True, nullable=False)

    # GraphAnalyzer
    vertices: Mapped[int] = mapped_column(Integer, nullable=False)
    edges: Mapped[int] = mapped_column(Integer, nullable=False)
    distinct_edges: Mapped[int] = mapped_column(Integer, nullable=False)
    connected_components: Mapped[int] = mapped_column(Integer, nullable=False)
    graph_density: Mapped[float] = mapped_column(Float, nullable=True)

    # EulerianAnalyzer
    odd_degree_vertex_count: Mapped[int] = mapped_column(Integer, nullable=False)
    largest_component_covers_all_nodes: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_eulerian_circuit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    has_eulerian_path: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # MultiplicityAnalyzer
    max_multiplicity: Mapped[int] = mapped_column(Integer, nullable=False)
    multiplicity_distribution: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    multiplicity_violations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # SymmetryAnalyzer
    symmetry_coverage: Mapped[float] = mapped_column(Float, nullable=True)
    symmetry_transform: Mapped[str] = mapped_column(String(32), nullable=True)

    # ComplexityAnalyzer
    complexity_score: Mapped[float] = mapped_column(Float, nullable=True)
    density_score: Mapped[float] = mapped_column(Float, nullable=True)

    # NoveltyAnalyzer (populated only when a reference pool was supplied)
    novelty_score: Mapped[float] = mapped_column(Float, nullable=True)
    nearest_source_id: Mapped[str] = mapped_column(String(64), nullable=True)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    pattern_version: Mapped["PatternVersion"] = relationship(back_populates="analysis")


class VerificationResult(Base):
    """One row per verification ATTEMPT (a PatternVersion may be
    verified more than once, e.g. deterministic + M4.2 self-consistency
    are two separate rows, not merged into one) -- `method` distinguishes
    them. `model_version_id` is nullable because the deterministic
    structural-validity check (engine.validity.check_validity) is not
    produced by any trainable model/checkpoint -- forcing a FK there
    would misrepresent it as ML-verified."""

    __tablename__ = "verification_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    pattern_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("pattern_versions.id"), nullable=False, index=True)
    model_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("model_versions.id"), nullable=True)
    method: Mapped[str] = mapped_column(String(32), nullable=False)  # "structural_hard_gate" | "recognizer_self_consistency"
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    n_expected: Mapped[int] = mapped_column(Integer, nullable=True)
    n_detected: Mapped[int] = mapped_column(Integer, nullable=True)
    recall: Mapped[float] = mapped_column(Float, nullable=True)
    precision: Mapped[float] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    pattern_version: Mapped["PatternVersion"] = relationship(back_populates="verifications")
    model_version: Mapped["ModelVersion"] = relationship()


class Artifact(Base):
    """A rendered file derived FROM a PatternVersion -- never the source
    of truth (see module docstring). `storage_path` is relative to
    api/storage/ (never an absolute filesystem path exposed to a
    caller -- api routes serve artifact bytes through an endpoint, not
    by returning this path directly, so the platform can swap to real
    object storage (S3/GCS) later by changing only how this path is
    interpreted, not the schema)."""

    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    pattern_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("pattern_versions.id"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(16), nullable=False, default="svg")
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, default="image/svg+xml")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    pattern_version: Mapped["PatternVersion"] = relationship(back_populates="artifacts")


class GenerationResult(Base):
    """One generated candidate -- links a GenerationRun to the
    PatternVersion it produced. Summary fields (`is_valid`, `seed`) are
    denormalized from PatternVersion/the run for cheap list queries;
    PatternVersion remains authoritative for anything not duplicated
    here."""

    __tablename__ = "generation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("generation_runs.id"), nullable=False, index=True)
    pattern_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("pattern_versions.id"), nullable=False)
    # BigInteger, not Integer: a random seed is 4 random bytes
    # (api/services/generation.py, int.from_bytes(os.urandom(4), "big")),
    # i.e. up to 2**32-1 -- real-Postgres verification this session found
    # this overflows Postgres's Integer (32-bit signed, max 2**31-1) on
    # roughly half of randomly generated seeds (psycopg2.errors.
    # NumericValueOutOfRange), invisible against SQLite (dynamically
    # typed, no such limit).
    seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    run: Mapped["GenerationRun"] = relationship(back_populates="results")
    pattern_version: Mapped["PatternVersion"] = relationship()
