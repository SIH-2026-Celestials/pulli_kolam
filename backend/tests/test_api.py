from __future__ import annotations

import os
import sys
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"


def test_v1_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_v1_model_endpoint():
    response = client.get("/api/v1/model")
    assert response.status_code == 200
    data = response.json()
    assert "architecture" in data
    assert data["architecture"] == "DotHeatmapNet"


def test_gallery_endpoint():
    response = client.get("/api/gallery")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_generate_endpoint():
    payload = {
        "specifications": "7x7 D4 symmetrical kolam with corner loops",
        "count": 10,
        "symmetry_group": "D4",
    }
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["generated_count"] == 10
    assert len(data["kolams"]) == 10


def test_analyze_with_default_sample():
    response = client.post("/api/analyze")
    assert response.status_code == 200
    data = response.json()
    assert "analysis_id" in data
    assert "symmetry" in data
    assert "validity" in data


def test_v1_detect_endpoint():
    response = client.post("/api/v1/detect")
    assert response.status_code == 200
    data = response.json()
    assert "dot_count" in data or "count" in data
    assert "dots" in data or "detections" in data


def test_v1_reconstruct_endpoint():
    response = client.post("/api/v1/reconstruct")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_v1_compare_detectors_endpoint():
    response = client.post("/api/v1/compare-detectors")
    assert response.status_code == 200
    data = response.json()
    assert "classical" in data
    assert "ml" in data
    assert "comparison" in data
