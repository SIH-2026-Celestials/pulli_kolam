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
