"""M5: /api/v1/generate endpoint tests. Uses FastAPI's TestClient. The
underlying search is real (no mocking) -- a single-candidate request
takes on the order of 10-60s (see experiments/m5_generation's benchmark
report for the honest latency distribution), so these tests are
deliberately kept to count=1 requests and are skipped entirely if the
trained checkpoint/split manifest this endpoint depends on aren't
present (same "skip if fixture missing" convention test_api.py already
uses for its own real-detector fixtures)."""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from api.generation_service import CHECKPOINT_PATH, SPLIT_MANIFEST_PATH  # noqa: E402
from api.main import app  # noqa: E402

client = TestClient(app)

pytestmark = pytest.mark.skipif(
    not (CHECKPOINT_PATH.exists() and SPLIT_MANIFEST_PATH.exists()),
    reason="M5 placement-scorer checkpoint or split manifest missing",
)


def test_generate_default_request():
    r = client.post("/api/v1/generate", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert len(body["candidates"]) == 1
    candidate = body["candidates"][0]
    assert "is_valid" in candidate
    assert candidate["n_dots"] > 0
    assert candidate["render_svg"].startswith("<svg")
    assert body["model"]["n_parameters"] > 0
    assert body["constraints"]["motif_library_size"] > 0


def test_generate_seed_reproducibility():
    r1 = client.post("/api/v1/generate", json={"seed": 123, "count": 1})
    r2 = client.post("/api/v1/generate", json={"seed": 123, "count": 1})
    assert r1.status_code == 200 and r2.status_code == 200
    c1, c2 = r1.json()["candidates"][0], r2.json()["candidates"][0]
    assert c1["is_valid"] == c2["is_valid"]
    assert c1["n_distinct_edges"] == c2["n_distinct_edges"]
    assert c1["n_edge_instances"] == c2["n_edge_instances"]


def test_generate_different_seeds_can_diverge():
    r1 = client.post("/api/v1/generate", json={"seed": 1, "count": 1})
    r2 = client.post("/api/v1/generate", json={"seed": 2, "count": 1})
    assert r1.status_code == 200 and r2.status_code == 200
    # not asserting they MUST differ (small search spaces can coincide) --
    # only that both are well-formed, real, independent responses
    assert r1.json()["candidates"][0]["seed"] == 1
    assert r2.json()["candidates"][0]["seed"] == 2


def test_generate_invalid_count_rejected():
    r = client.post("/api/v1/generate", json={"count": 0})
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False
    assert body["code"] == "INVALID_REQUEST"

    r2 = client.post("/api/v1/generate", json={"count": 999})
    assert r2.status_code == 422


def test_generate_response_identifies_generator():
    """Integration addition: the response must name which generator
    implementation produced it (api/schemas.py's GenerateResponse.generator),
    so a future generator swap is distinguishable without a response-shape
    change (see engine/generation_contract.py and INTEGRATION.md)."""
    r = client.post("/api/v1/generate", json={"count": 1})
    assert r.status_code == 200
    assert r.json()["generator"] == "m5"


def test_generate_multiple_candidates():
    """Integration addition: count>1 must return that many independently
    seeded candidates in one response (base_seed + i per api/main.py's
    generate()), not just repeat count=1's behavior N times."""
    r = client.post("/api/v1/generate", json={"seed": 500, "count": 3})
    assert r.status_code == 200
    body = r.json()
    candidates = body["candidates"]
    assert len(candidates) == 3
    assert [c["seed"] for c in candidates] == [500, 501, 502]
    # each candidate is a real, independently rendered SVG, not a
    # duplicate of the first
    assert all(c["render_svg"].startswith("<svg") for c in candidates)


def test_generate_service_unavailable_returns_structured_error():
    """Integration addition: if GenerationService reports unavailable
    (checkpoint/manifest failed to load), the endpoint must return the
    project's standard {success, error, code} envelope at 503 -- not a
    raw exception or a silent fallback to a different generator."""
    from api.generation_service import get_generation_service

    service = get_generation_service()
    # force the already-loaded singleton into a failure state, matching
    # what a real checkpoint-load failure looks like from the endpoint's
    # point of view (_load_error set, _motif_library left as-is)
    original_error = service._load_error
    service._load_error = "simulated checkpoint load failure"
    try:
        r = client.post("/api/v1/generate", json={"count": 1})
        assert r.status_code == 503
        body = r.json()
        assert body["success"] is False
        assert body["code"] == "GENERATION_MODEL_UNAVAILABLE"
        assert "simulated checkpoint load failure" in body["error"]
    finally:
        service._load_error = original_error


def test_generate_no_fabricated_novelty_claim():
    """The per-request response must not assert a specific novelty
    percentage it hasn't actually computed against ground truth (that
    aggregate measurement belongs to the benchmark report, not a single
    request) -- see api/main.py's generate() docstring."""
    r = client.post("/api/v1/generate", json={"count": 1})
    assert r.status_code == 200
    note = r.json()["candidates"][0]["novelty_note"]
    assert "%" not in note
