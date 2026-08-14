"""M4.2 Phase K: API endpoint tests. Uses FastAPI's TestClient (no
actual server process needed). Run with KMP_DUPLICATE_LIB_OK=TRUE (the
API imports both torch and engine.image_io -- see api/main.py's module
docstring for why)."""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from api.main import app  # noqa: E402

client = TestClient(app)

SYNTH_IMAGE = os.path.join(os.path.dirname(__file__), "..", "..", "synthetic_photos", "kolam19_k1.jpg")
pytestmark = pytest.mark.skipif(not os.path.exists(SYNTH_IMAGE), reason="synthetic_photos/ fixture missing")


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["classical_detector_available"] is True


def test_model_info():
    r = client.get("/api/v1/model")
    assert r.status_code == 200
    body = r.json()
    assert "classical_detector" in body
    assert "ml_checkpoint_exists" in body


def test_detect_classical_default():
    with open(SYNTH_IMAGE, "rb") as f:
        r = client.post("/api/v1/detect", files={"image": ("k.jpg", f, "image/jpeg")})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["detector"] == "classical"
    assert body["count"] == len(body["detections"])
    assert body["image"]["width"] > 0 and body["image"]["height"] > 0
    # coordinates must be in ORIGINAL image space, not model-input/heatmap space
    for det in body["detections"]:
        assert 0 <= det["x"] <= body["image"]["width"] * 1.05  # small tolerance for deskew edge effects
        assert 0 <= det["y"] <= body["image"]["height"] * 1.05


def test_detect_explicit_detector_selection():
    with open(SYNTH_IMAGE, "rb") as f:
        r = client.post("/api/v1/detect", files={"image": ("k.jpg", f, "image/jpeg")}, data={"detector": "classical"})
    assert r.status_code == 200
    assert r.json()["detector"] == "classical"


def test_detect_invalid_detector_name():
    with open(SYNTH_IMAGE, "rb") as f:
        r = client.post("/api/v1/detect", files={"image": ("k.jpg", f, "image/jpeg")}, data={"detector": "quantum"})
    assert r.status_code == 400
    assert r.json()["success"] is False


def test_detect_malformed_upload_rejected():
    r = client.post("/api/v1/detect", files={"image": ("bad.txt", b"not an image", "text/plain")})
    assert r.status_code == 400
    assert r.json()["success"] is False


def test_detect_empty_upload_rejected():
    r = client.post("/api/v1/detect", files={"image": ("empty.jpg", b"", "image/jpeg")})
    assert r.status_code == 400


def test_analyze_returns_graph_motifs_validity():
    with open(SYNTH_IMAGE, "rb") as f:
        r = client.post("/api/v1/analyze", files={"image": ("k.jpg", f, "image/jpeg")})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "graph" in body and set(body["graph"].keys()) == {"nodes", "edges", "distinct_edges"}
    assert "motifs" in body and "motif_count" in body["motifs"]
    assert "validity" in body and "is_eulerian_circuit" in body["validity"]
    # no networkx object leaked -- every value must be JSON primitive
    import json
    json.dumps(body)  # raises if anything non-serializable slipped through


def test_reconstruct_returns_structured_result():
    with open(SYNTH_IMAGE, "rb") as f:
        r = client.post("/api/v1/reconstruct", files={"image": ("k.jpg", f, "image/jpeg")})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "reconstruction" in body
    import json
    json.dumps(body)


def test_compare_detectors_reports_both_sides():
    with open(SYNTH_IMAGE, "rb") as f:
        r = client.post("/api/v1/compare-detectors", files={"image": ("k.jpg", f, "image/jpeg")})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["classical"]["detector"] == "classical"
    assert body["ml"]["detector"] == "ml"
    assert "agreement" in body


def test_detect_default_is_classical_not_ml():
    """Production-default rule: omitting `detector` must select
    classical, never ml, per the task's explicit fallback-behavior rule."""
    with open(SYNTH_IMAGE, "rb") as f:
        r = client.post("/api/v1/detect", files={"image": ("k.jpg", f, "image/jpeg")})
    assert r.json()["detector"] == "classical"


def test_cors_allows_local_frontend_origin():
    """Regression test for a real bug found via browser E2E testing (not
    caught by TestClient-based tests, since TestClient never enforces
    CORS the way a real browser does): without CORSMiddleware, every
    request from the Vite dev frontend (a different origin: 5173/5174 vs
    this API's 8000) was silently blocked by the browser before it ever
    reached an endpoint, making every /detect page action fail with a
    misleading "backend unavailable" message despite the server working
    fine. Assert the middleware is actually wired, not just that it's
    imported."""
    r = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_non_local_origin():
    """The allow-list is a localhost-only regex, not a blanket wildcard --
    confirm a non-local origin does not get an allow-origin header back."""
    r = client.get("/api/v1/health", headers={"Origin": "https://evil.example.com"})
    assert r.status_code == 200  # request still succeeds (no credentials involved)
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers.keys()}
