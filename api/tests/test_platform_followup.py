"""M7 platform integration (follow-up) tests: Generator interface,
paginated history, export endpoints, DB indexes. Real generation (no
mocking), same skip-if-fixture-missing convention as the rest of
api/tests/.
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


def test_generator_interface_m5generator_produces_real_candidate():
    """Unit-level: M5Generator (the Generator Protocol's only
    registered implementation) produces a real, structurally sound
    candidate object without going through the API layer at all."""
    from api.services.generator_interface import M5Generator

    generator = M5Generator()
    assert generator.name == "M5"
    assert generator.available is True

    candidate = generator.generate_one(seed=321)
    assert candidate.seed == 321
    assert hasattr(candidate.structural_object, "graph")
    assert hasattr(candidate.structural_object, "is_valid")


def test_list_generations_paginated():
    # ensure at least one result exists
    client.post("/api/v1/generations", json={"seed": 1001, "count": 1})

    r = client.get("/api/v1/generations?page=1&page_size=1")
    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert len(body["items"]) == 1
    assert body["total"] >= 1
    item = body["items"][0]
    assert "svg" not in item  # list view must NOT include large payloads
    assert "representation" not in item
    assert "id" in item and "generator" in item and "is_valid" in item


def test_list_generations_invalid_page_rejected():
    r = client.get("/api/v1/generations?page=0")
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_REQUEST"

    r2 = client.get("/api/v1/generations?page_size=1000")
    assert r2.status_code == 422


def test_export_svg_png_json():
    r = client.post("/api/v1/generations", json={"seed": 1002, "count": 1})
    result_id = r.json()["candidates"][0]["id"]

    r_svg = client.get(f"/api/v1/generations/{result_id}/export?format=svg")
    assert r_svg.status_code == 200
    assert r_svg.headers["content-type"].startswith("image/svg+xml")
    assert b"<svg" in r_svg.content

    r_png = client.get(f"/api/v1/generations/{result_id}/export?format=png")
    assert r_png.status_code == 200
    assert r_png.headers["content-type"] == "image/png"
    assert r_png.content[:8] == b"\x89PNG\r\n\x1a\n"  # real PNG magic bytes, not a stub

    r_json = client.get(f"/api/v1/generations/{result_id}/export?format=json")
    assert r_json.status_code == 200
    assert r_json.headers["content-type"].startswith("application/json")
    import json as _json

    parsed = _json.loads(r_json.content)
    assert "dot_points" in parsed and "edges" in parsed


def test_export_invalid_format_rejected():
    r = client.post("/api/v1/generations", json={"seed": 1003, "count": 1})
    result_id = r.json()["candidates"][0]["id"]
    r2 = client.get(f"/api/v1/generations/{result_id}/export?format=pdf")
    assert r2.status_code == 422
    assert r2.json()["code"] == "INVALID_REQUEST"


def test_export_not_found():
    r = client.get("/api/v1/generations/does-not-exist/export?format=svg")
    assert r.status_code == 404
    assert r.json()["code"] == "NOT_FOUND"


def test_artifact_store_rejects_path_traversal():
    from api.services.artifact_store import LocalArtifactStore

    store = LocalArtifactStore()
    with pytest.raises(ValueError):
        store.write("../../etc/passwd", "malicious", "text/plain")
