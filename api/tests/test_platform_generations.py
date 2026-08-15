"""M7 platform integration tests: persisted generation endpoints,
analysis, verification, and model registry. Real generation (no
mocking) -- same latency profile as api/tests/test_generate_endpoint.py,
same skip-if-fixture-missing convention.
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from api.db.database import get_session, init_db  # noqa: E402
from api.db.seed import seed_models  # noqa: E402
from api.generation_service import CHECKPOINT_PATH, SPLIT_MANIFEST_PATH  # noqa: E402
from api.main import app  # noqa: E402

client = TestClient(app)

pytestmark = pytest.mark.skipif(
    not (CHECKPOINT_PATH.exists() and SPLIT_MANIFEST_PATH.exists()),
    reason="M5 placement-scorer checkpoint or split manifest missing",
)


@pytest.fixture(scope="module", autouse=True)
def _ensure_db():
    init_db()
    session = get_session()
    try:
        seed_models(session)
    finally:
        session.close()


@pytest.fixture(scope="module", autouse=True)
def _logged_in_user(_ensure_db):
    """POST /api/v1/generations and friends require login (ownership
    fix -- generations are private per-user, not a public feed; see
    api/routes_generations.py's `_get_owned_generation`). `client` is a
    module-level TestClient, so its cookie jar carries this session
    across every test in this file, matching a real logged-in browser."""
    from api.auth.db import init_db as init_auth_db

    init_auth_db()
    client.post(
        "/api/v1/auth/register",
        json={"email": "platform_test_user@example.com", "password": "TestPassword123!", "display_name": "Platform Test"},
    )
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "platform_test_user@example.com", "password": "TestPassword123!"},
    )
    assert r.status_code == 200, r.text


def test_models_registry_lists_all_three_families():
    r = client.get("/api/v1/models")
    assert r.status_code == 200
    body = r.json()
    names = {m["model_name"] for m in body["models"]}
    assert names == {"M5", "M4.2", "M6"}


def test_m5_is_the_only_production_model():
    r = client.get("/api/v1/models")
    body = r.json()
    production = [m for m in body["models"] if m["status"] == "production"]
    assert len(production) == 1
    assert production[0]["model_name"] == "M5"
    research = [m for m in body["models"] if m["status"] == "research"]
    assert research[0]["model_name"] == "M6"


def test_get_model_by_id():
    r = client.get("/api/v1/models")
    mv_id = r.json()["models"][0]["id"]
    r2 = client.get(f"/api/v1/models/{mv_id}")
    assert r2.status_code == 200
    assert r2.json()["model"]["id"] == mv_id


def test_get_model_not_found():
    r = client.get("/api/v1/models/does-not-exist")
    assert r.status_code == 404
    assert r.json()["success"] is False
    assert r.json()["code"] == "NOT_FOUND"


def test_create_generation_persists_and_is_retrievable():
    r = client.post("/api/v1/generations", json={"seed": 777, "count": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["model_version"] == "v1.0"
    candidate = body["candidates"][0]
    assert candidate["seed"] == 777
    assert candidate["render_svg"].startswith("<svg")
    assert "analysis" in candidate
    assert "graph" in candidate["analysis"]

    result_id = candidate["id"]
    r2 = client.get(f"/api/v1/generations/{result_id}")
    assert r2.status_code == 200
    detail = r2.json()
    assert detail["seed"] == 777
    assert detail["render_svg"].startswith("<svg")
    assert detail["representation"]["n_nodes"] > 0
    assert len(detail["verification"]) >= 1
    assert detail["verification"][0]["method"] == "structural_hard_gate"


def test_get_generation_mathematics():
    r = client.post("/api/v1/generations", json={"seed": 778, "count": 1})
    result_id = r.json()["candidates"][0]["id"]

    r2 = client.get(f"/api/v1/generations/{result_id}/mathematics")
    assert r2.status_code == 200
    math = r2.json()["mathematics"]
    assert "graph" in math and "eulerian" in math and "multiplicity" in math
    assert "symmetry" in math and "complexity" in math
    assert math["graph"]["vertices"] > 0


def test_get_generation_graph():
    r = client.post("/api/v1/generations", json={"seed": 779, "count": 1})
    result_id = r.json()["candidates"][0]["id"]

    r2 = client.get(f"/api/v1/generations/{result_id}/graph")
    assert r2.status_code == 200
    graph = r2.json()["graph"]
    assert len(graph["dot_points"]) > 0
    assert isinstance(graph["edges"], list)


def test_get_generation_not_found():
    r = client.get("/api/v1/generations/does-not-exist")
    assert r.status_code == 404
    assert r.json()["code"] == "NOT_FOUND"


def test_create_generation_invalid_count_rejected():
    r = client.post("/api/v1/generations", json={"count": 0})
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_REQUEST"

    r2 = client.post("/api/v1/generations", json={"count": 999})
    assert r2.status_code == 422


def test_analyze_pattern_endpoint_accepts_submitted_representation():
    # A tiny hand-built square graph -- 4 dots, 4 edges, one connected
    # component, every vertex degree 2 -> Eulerian circuit.
    body = {
        "dot_points": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "edges": [[[0, 0], [1, 0]], [[1, 0], [1, 1]], [[1, 1], [0, 1]], [[0, 1], [0, 0]]],
    }
    r = client.post("/api/v1/patterns/analyze", json=body)
    assert r.status_code == 200
    analysis = r.json()["analysis"]
    assert analysis["graph"]["vertices"] == 4
    assert analysis["eulerian"]["is_eulerian_circuit"] is True
    assert analysis["eulerian"]["odd_degree_vertex_count"] == 0


def test_verify_pattern_endpoint():
    body = {
        "dot_points": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "edges": [[[0, 0], [1, 0]], [[1, 0], [1, 1]], [[1, 1], [0, 1]], [[0, 1], [0, 0]]],
    }
    r = client.post("/api/v1/patterns/verify", json=body)
    assert r.status_code == 200
    v = r.json()["verification"]
    assert v["method"] == "structural_hard_gate"
    assert v["is_valid"] is True


def test_verify_pattern_detects_invalid_structure():
    # A single dangling edge with two odd-degree vertices, one component:
    # has an Eulerian PATH (not a circuit) -- still passes the hard gate
    # (an open single-stroke is valid). Use a genuinely disconnected
    # structure to exercise the invalid case.
    body = {
        "dot_points": [[0, 0], [1, 0], [5, 5], [6, 5]],
        "edges": [[[0, 0], [1, 0]], [[5, 5], [6, 5]]],
    }
    r = client.post("/api/v1/patterns/verify", json=body)
    assert r.status_code == 200
    assert r.json()["verification"]["is_valid"] is False


def test_legacy_generate_endpoint_still_works_unchanged():
    """Backward compatibility: the pre-existing /api/v1/generate endpoint
    (not persisted) must keep working exactly as before -- this platform
    integration is additive, not a replacement."""
    r = client.post("/api/v1/generate", json={"seed": 42, "count": 1})
    assert r.status_code == 200
    assert r.json()["generator"] == "m5"


# ============================================================
# Ownership regression tests (Phase 9's explicit requirement: "a user
# must never be able to retrieve another user's private generation
# merely by knowing its ID"). `client` is logged in as
# platform_test_user@example.com for the whole module (see
# `_logged_in_user`); `_anon_client`/`_other_user_client` below are
# deliberately SEPARATE TestClient instances so their cookie jars never
# collide with the module's primary logged-in session.
# ============================================================

def test_create_generation_requires_login():
    anon = TestClient(app)
    r = anon.post("/api/v1/generations", json={"seed": 900, "count": 1})
    assert r.status_code == 401


def test_get_generation_requires_login():
    anon = TestClient(app)
    r = anon.get("/api/v1/generations/does-not-exist")
    assert r.status_code == 401


def test_list_generations_requires_login():
    anon = TestClient(app)
    r = anon.get("/api/v1/generations")
    assert r.status_code == 401


def _other_user_client() -> TestClient:
    other = TestClient(app)
    other.post(
        "/api/v1/auth/register",
        json={"email": "platform_other_user@example.com", "password": "TestPassword123!", "display_name": "Other User"},
    )
    r = other.post(
        "/api/v1/auth/login",
        json={"email": "platform_other_user@example.com", "password": "TestPassword123!"},
    )
    assert r.status_code == 200, r.text
    return other


def test_cannot_retrieve_another_users_generation():
    """The core ownership check: user A creates a generation, user B
    (logged in, real session, real account) must get the SAME 404 a
    nonexistent id would give -- never a 403 that would confirm the id
    is real but someone else's, and never the actual data."""
    r = client.post("/api/v1/generations", json={"seed": 901, "count": 1})
    assert r.status_code == 200
    result_id = r.json()["candidates"][0]["id"]

    other = _other_user_client()
    r2 = other.get(f"/api/v1/generations/{result_id}")
    assert r2.status_code == 404
    assert r2.json()["code"] == "NOT_FOUND"


def test_cannot_retrieve_another_users_generation_mathematics_graph_or_export():
    r = client.post("/api/v1/generations", json={"seed": 902, "count": 1})
    result_id = r.json()["candidates"][0]["id"]

    other = _other_user_client()
    assert other.get(f"/api/v1/generations/{result_id}/mathematics").status_code == 404
    assert other.get(f"/api/v1/generations/{result_id}/graph").status_code == 404
    assert other.get(f"/api/v1/generations/{result_id}/export?format=svg").status_code == 404


def test_list_generations_only_shows_own_results():
    """User B's history must not include user A's generations, even
    though both exist in the same database."""
    r = client.post("/api/v1/generations", json={"seed": 903, "count": 1})
    my_result_id = r.json()["candidates"][0]["id"]

    other = _other_user_client()
    r2 = other.get("/api/v1/generations?page=1&page_size=100")
    assert r2.status_code == 200
    other_ids = {item["id"] for item in r2.json()["items"]}
    assert my_result_id not in other_ids


# ============================================================
# Artifact deletion (Phase 1's explicit test list: successful deletion,
# missing artifact, unauthorized deletion, database failure, storage
# failure).
# ============================================================

def test_delete_generation_success_removes_db_rows_and_storage_object():
    """1. Successful deletion: after DELETE, the result is truly gone --
    both the DB row (re-GET returns 404) and the underlying storage file
    (no longer exists on disk, via the same LocalStorage the app itself
    uses)."""
    from api.db.database import get_session as _get_session
    from api.db.models import Artifact, GenerationResult, PatternAnalysis, PatternVersion, VerificationResult
    from api.services.artifact_store import get_artifact_store

    r = client.post("/api/v1/generations", json={"seed": 910, "count": 1})
    result_id = r.json()["candidates"][0]["id"]

    session = _get_session()
    try:
        result_row = session.get(GenerationResult, result_id)
        pv_id = result_row.pattern_version_id
        artifact_paths = [a.storage_path for a in session.query(Artifact).filter_by(pattern_version_id=pv_id).all()]
    finally:
        session.close()
    assert artifact_paths, "expected at least one Artifact row for a fresh generation"
    store = get_artifact_store()
    assert all(store.exists(p) for p in artifact_paths), "artifact file(s) should exist before deletion"

    r_del = client.delete(f"/api/v1/generations/{result_id}")
    assert r_del.status_code == 204

    # Re-GET returns the same 404 as any nonexistent id.
    assert client.get(f"/api/v1/generations/{result_id}").status_code == 404

    session = _get_session()
    try:
        assert session.get(GenerationResult, result_id) is None
        assert session.get(PatternVersion, pv_id) is None
        assert session.query(PatternAnalysis).filter_by(pattern_version_id=pv_id).count() == 0
        assert session.query(VerificationResult).filter_by(pattern_version_id=pv_id).count() == 0
        assert session.query(Artifact).filter_by(pattern_version_id=pv_id).count() == 0
    finally:
        session.close()

    assert not any(store.exists(p) for p in artifact_paths), "artifact file(s) should be gone from storage after deletion"


def test_delete_generation_missing_returns_404():
    """2. Missing artifact: deleting an id that never existed is a clean
    404, not a 500 or a silent no-op."""
    r = client.delete("/api/v1/generations/does-not-exist")
    assert r.status_code == 404
    assert r.json()["code"] == "NOT_FOUND"


def test_delete_generation_unauthorized_is_rejected_and_nothing_is_deleted():
    """3. Unauthorized deletion: user B can never delete user A's
    generation -- same 404-not-403 convention as every other ownership
    check here, AND the row must still exist afterward (verified via
    user A's own client, not just "the delete call returned an error")."""
    r = client.post("/api/v1/generations", json={"seed": 911, "count": 1})
    result_id = r.json()["candidates"][0]["id"]

    other = _other_user_client()
    r_del = other.delete(f"/api/v1/generations/{result_id}")
    assert r_del.status_code == 404

    # Still retrievable by its real owner -- nothing was actually deleted.
    assert client.get(f"/api/v1/generations/{result_id}").status_code == 200


def test_delete_generation_database_failure_returns_500_and_rolls_back(monkeypatch):
    """4. Database failure: if the delete transaction fails partway
    through, the request reports a clean 500 (not a crash, not a silent
    partial success) and the row is verifiably still intact afterward --
    proving the rollback actually happened, not just that an exception
    was caught."""
    from api.db.database import get_session as _get_session
    from api.db.models import GenerationResult

    r = client.post("/api/v1/generations", json={"seed": 912, "count": 1})
    result_id = r.json()["candidates"][0]["id"]

    from sqlalchemy.orm import Session as SqlAlchemySession

    def _boom(self, *args, **kwargs):
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(SqlAlchemySession, "commit", _boom)
    r_del = client.delete(f"/api/v1/generations/{result_id}")
    assert r_del.status_code == 500
    assert r_del.json()["code"] == "DELETE_FAILED"
    monkeypatch.undo()

    # The row must still be fully intact -- the failed commit did not
    # leave a half-applied delete.
    session = _get_session()
    try:
        assert session.get(GenerationResult, result_id) is not None
    finally:
        session.close()
    assert client.get(f"/api/v1/generations/{result_id}").status_code == 200


def test_delete_generation_storage_failure_still_deletes_db_rows(monkeypatch):
    """5. Storage failure: if the underlying storage backend can't
    delete the file (network error, R2 unreachable, etc.), the DB rows
    are still removed -- per the endpoint's documented safety ordering,
    a storage-cleanup failure must never block or fail the DB deletion,
    since the alternative (leave the DB row) would produce the strictly
    worse dangling-reference failure mode."""
    from api.db.database import get_session as _get_session
    from api.db.models import GenerationResult
    from api.services.artifact_store import get_artifact_store

    r = client.post("/api/v1/generations", json={"seed": 913, "count": 1})
    result_id = r.json()["candidates"][0]["id"]

    store = get_artifact_store()

    def _boom(self, relative_path):
        raise RuntimeError("simulated storage failure")

    monkeypatch.setattr(type(store), "delete", _boom)
    r_del = client.delete(f"/api/v1/generations/{result_id}")
    monkeypatch.undo()

    assert r_del.status_code == 204  # storage failure is logged, not surfaced as a request failure
    session = _get_session()
    try:
        assert session.get(GenerationResult, result_id) is None
    finally:
        session.close()
