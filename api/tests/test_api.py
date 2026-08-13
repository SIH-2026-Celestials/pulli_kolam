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
    # 422: syntactically valid multipart request, semantically invalid
    # parameter value -- see api/main.py's _validate_detector_param.
    with open(SYNTH_IMAGE, "rb") as f:
        r = client.post("/api/v1/detect", files={"image": ("k.jpg", f, "image/jpeg")}, data={"detector": "quantum"})
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False
    assert body["code"] == "INVALID_DETECTOR"


def test_detect_malformed_upload_rejected():
    # 415: the content-type itself is rejected before any image bytes
    # are inspected -- see api/main.py's _save_upload_to_temp.
    r = client.post("/api/v1/detect", files={"image": ("bad.txt", b"not an image", "text/plain")})
    assert r.status_code == 415
    body = r.json()
    assert body["success"] is False
    assert body["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_detect_empty_upload_rejected():
    r = client.post("/api/v1/detect", files={"image": ("empty.jpg", b"", "image/jpeg")})
    assert r.status_code == 400
    assert r.json()["code"] == "EMPTY_UPLOAD"


def test_detect_oversized_upload_rejected():
    oversized = b"\xff" * (20 * 1024 * 1024 + 1)
    r = client.post("/api/v1/detect", files={"image": ("big.jpg", oversized, "image/jpeg")})
    assert r.status_code == 413
    body = r.json()
    assert body["success"] is False
    assert body["code"] == "UPLOAD_TOO_LARGE"


def test_ml_detector_unavailable_returns_503_not_silent_fallback(monkeypatch):
    """When the ML checkpoint can't load, the API must return an explicit
    503 -- never silently substitute the classical detector's result."""
    import api.main as main_module

    def _boom(self):
        raise RuntimeError("simulated missing checkpoint")

    monkeypatch.setattr(main_module.get_detector("ml").__class__, "_ensure_loaded", _boom)
    with open(SYNTH_IMAGE, "rb") as f:
        r = client.post("/api/v1/detect", files={"image": ("k.jpg", f, "image/jpeg")}, data={"detector": "ml"})
    assert r.status_code == 503
    body = r.json()
    assert body["success"] is False
    assert body["code"] == "ML_MODEL_UNAVAILABLE"
    assert "detections" not in body  # no partial/fake detector result on failure


def test_cors_preflight_allows_configured_origin():
    # CORS_ORIGINS is read once at process start (api/main.py module
    # scope), so this exercises the dev-default origin list rather than
    # a runtime override -- see test_cors_preflight_rejects_unconfigured_origin
    # for the negative case, on the same running app instance.
    r = client.options(
        "/api/v1/detect",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_preflight_rejects_unconfigured_origin():
    r = client.options(
        "/api/v1/detect",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in r.headers


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


# ============================================================
# Integration proof: detector=ml genuinely controls the DOWNSTREAM
# graph/analysis/reconstruction pipeline, not just /detect's own
# response. This is the specific claim that must be verified with real
# data, not merely asserted -- both endpoints returning HTTP 200 proves
# nothing about which detector's Lattice actually built the graph.
#
# Fixture: real_photos/kolam1_raaj.jpg is a real (non-synthetic) photo
# on which the classical detector reliably finds 0 dots (Otsu/distance-
# transform dot detection fails on this specific photo's lighting) while
# the ML detector reliably finds a large, non-trivial dot set. This
# sharp divergence is exactly what makes it a strong fixture: if
# /analyze or /reconstruct with detector=ml were silently using the
# classical detector's (empty) result instead, these tests would fail
# immediately and unambiguously -- not require a subtle diff.
# ============================================================

REAL_IMAGE = os.path.join(os.path.dirname(__file__), "..", "..", "real_photos", "kolam1_raaj.jpg")
_real_image_skip = pytest.mark.skipif(not os.path.exists(REAL_IMAGE), reason="real_photos/ fixture missing")


@_real_image_skip
def test_classical_and_ml_detect_genuinely_different_dot_counts_on_same_image():
    """Precondition for every test below: the two detectors must
    actually disagree on this fixture, or the rest of this section
    proves nothing."""
    with open(REAL_IMAGE, "rb") as f:
        classical = client.post("/api/v1/detect", files={"image": ("k.jpg", f, "image/jpeg")}, data={"detector": "classical"}).json()
    with open(REAL_IMAGE, "rb") as f:
        ml = client.post("/api/v1/detect", files={"image": ("k.jpg", f, "image/jpeg")}, data={"detector": "ml"}).json()
    assert classical["count"] != ml["count"]
    assert ml["count"] > 0


@_real_image_skip
def test_analyze_detector_selection_controls_the_actual_graph_built():
    """The core Phase-3 claim: /analyze's graph.nodes must equal the
    SELECTED detector's own dot_count, for BOTH detectors independently
    -- proving analysis runs against whichever detector's Lattice was
    actually produced, not a fixed/default one."""
    with open(REAL_IMAGE, "rb") as f:
        classical = client.post("/api/v1/analyze", files={"image": ("k.jpg", f, "image/jpeg")}, data={"detector": "classical"}).json()
    with open(REAL_IMAGE, "rb") as f:
        ml = client.post("/api/v1/analyze", files={"image": ("k.jpg", f, "image/jpeg")}, data={"detector": "ml"}).json()

    assert classical["detector"] == "classical"
    assert ml["detector"] == "ml"
    # Each detector's graph.nodes must match ITS OWN dot_count exactly --
    # this is only possible if the graph was built from that detector's
    # own Lattice (engine.image_io.trace_path is index-aligned on
    # lattice_coords, see engine/ml_contract.py).
    assert classical["graph"]["nodes"] == classical["dot_count"]
    assert ml["graph"]["nodes"] == ml["dot_count"]
    # And the two results must genuinely differ -- not two calls that
    # both silently landed on the same (e.g. always-classical) path.
    assert classical["dot_count"] != ml["dot_count"]
    assert classical["graph"]["nodes"] != ml["graph"]["nodes"]
    # Model attribution must match the selected detector.
    assert classical["model"]["name"].startswith("Classical")
    assert ml["model"]["name"] == "DotHeatmapNetV2"


@_real_image_skip
def test_reconstruct_detector_selection_controls_the_actual_graph_used():
    """Same claim as above, for /reconstruct -- on this fixture,
    classical (0 dots) must hit the explicit 'nothing to reconstruct'
    path while ml (many dots) must actually run reconstruction, proving
    reconstruction consumed the ML detector's own graph, not a shared/
    default classical one."""
    with open(REAL_IMAGE, "rb") as f:
        classical = client.post("/api/v1/reconstruct", files={"image": ("k.jpg", f, "image/jpeg")}, data={"detector": "classical"}).json()
    with open(REAL_IMAGE, "rb") as f:
        ml = client.post("/api/v1/reconstruct", files={"image": ("k.jpg", f, "image/jpeg")}, data={"detector": "ml"}).json()

    assert classical["graph"]["nodes"] == 0
    assert "note" in classical["reconstruction"]  # "no dots detected"

    assert ml["graph"]["nodes"] > 0
    assert "is_valid" in ml["reconstruction"]  # real reconstruction ran, not the empty-note branch
    assert ml["model"]["name"] == "DotHeatmapNetV2"


@_real_image_skip
def test_ml_pipeline_acceptance_metrics_consistent_across_endpoints():
    """Phase-8 acceptance test: the SAME ML-derived structure must
    produce identical node/edge counts whether observed through /detect
    (via a redundant /analyze call), /analyze, or /reconstruct -- proving
    one coherent pipeline, not three independently-run detectors that
    happen to agree by coincidence. Also cross-checks the API's reported
    connectivity against an independent networkx recomputation from the
    same detector, run directly against the engine (not through the API),
    as an end-to-end sanity check spanning both layers."""
    with open(REAL_IMAGE, "rb") as f:
        detect_r = client.post("/api/v1/detect", files={"image": ("k.jpg", f, "image/jpeg")}, data={"detector": "ml"}).json()
    with open(REAL_IMAGE, "rb") as f:
        analyze_r = client.post("/api/v1/analyze", files={"image": ("k.jpg", f, "image/jpeg")}, data={"detector": "ml"}).json()
    with open(REAL_IMAGE, "rb") as f:
        reconstruct_r = client.post("/api/v1/reconstruct", files={"image": ("k.jpg", f, "image/jpeg")}, data={"detector": "ml"}).json()

    # Dot/node counts must agree across all three independent requests.
    assert detect_r["count"] == analyze_r["dot_count"]
    assert analyze_r["graph"]["nodes"] == reconstruct_r["graph"]["nodes"]
    assert analyze_r["graph"]["edges"] == reconstruct_r["graph"]["edges"]

    # Independent engine-level recomputation (bypassing the API/detector
    # abstraction entirely) must match the API's own connectivity report.
    from experiments.m4_2.ml_lattice_detector import LearnedLatticeDetectorV2
    from engine import image_io, validity as validity_module

    ml_detector = LearnedLatticeDetectorV2()
    preprocessed = image_io.preprocess(REAL_IMAGE)
    lattice = ml_detector(preprocessed)
    edges = image_io.trace_path(preprocessed, lattice)
    import networkx as nx
    G = nx.MultiGraph()
    G.add_nodes_from(lattice.lattice_coords)
    for a, b in edges:
        G.add_edge(a, b)

    independent_validity = validity_module.check_validity(G)
    odd_degree_nodes = [n for n, d in G.degree() if d % 2 == 1]

    assert G.number_of_nodes() == analyze_r["graph"]["nodes"]
    assert independent_validity["connected_components"] == analyze_r["validity"]["connected_components"]
    assert independent_validity["is_eulerian_circuit"] == analyze_r["validity"]["is_eulerian_circuit"]

    # Recorded for visibility (Phase 8's "record these values" ask) --
    # not asserted against a fixed expectation, since detection is a
    # real model's output, not a hardcoded fixture.
    print(
        f"\n[acceptance] image=kolam1_raaj.jpg dots={detect_r['count']} "
        f"lattice_points={len(lattice.lattice_coords)} "
        f"graph_nodes={G.number_of_nodes()} graph_edges={G.number_of_edges()} "
        f"connected_components={independent_validity['connected_components']} "
        f"odd_degree_nodes={len(odd_degree_nodes)} "
        f"reconstruction_valid={reconstruct_r['reconstruction'].get('is_valid')} "
        f"detect_ms={detect_r['processing_ms']} "
        f"analyze_total_ms={analyze_r['timing_ms']['total']} "
        f"reconstruct_total_ms={reconstruct_r['timing_ms']['total']}"
    )


@_real_image_skip
def test_compare_mode_runs_both_detectors_independently_not_merged():
    """Compare mode must genuinely run classical AND ml separately and
    report both counts un-merged -- on this fixture, that means
    classical=0 and ml>0 reported side by side, not averaged/combined."""
    with open(REAL_IMAGE, "rb") as f:
        r = client.post("/api/v1/compare-detectors", files={"image": ("k.jpg", f, "image/jpeg")})
    body = r.json()
    assert body["classical"]["count"] == 0
    assert body["ml"]["count"] > 0
    assert body["agreement"]["classical_count"] == 0
    assert body["agreement"]["ml_count"] == body["ml"]["count"]
