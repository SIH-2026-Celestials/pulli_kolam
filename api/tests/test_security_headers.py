"""Regression tests for api/security_headers.py's middleware and the
CORS `allow_methods` fix (DELETE was missing, which would have broken
DELETE /api/v1/generations/{id} for any real cross-origin browser --
found and fixed this session, see api/main.py).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

client = TestClient(app)


def test_security_headers_present_on_success_response():
    r = client.get("/api/v1/health/live")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["x-frame-options"] == "DENY"
    assert "max-age=31536000" in r.headers["strict-transport-security"]
    assert r.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"


def test_security_headers_present_on_error_response():
    """Headers must not be an artifact of only the happy path -- an error
    response (401 here, no auth cookie) must carry them too."""
    r = client.get("/api/v1/generations")
    assert r.status_code == 401
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"


def test_docs_gets_a_swagger_compatible_csp_not_the_strict_default():
    r = client.get("/docs")
    assert r.status_code == 200
    csp = r.headers["content-security-policy"]
    assert "cdn.jsdelivr.net" in csp
    assert csp != "default-src 'none'; frame-ancestors 'none'"


def test_cors_preflight_allows_delete_for_the_artifact_deletion_endpoint():
    """Regression test for a real bug: allow_methods was ["GET", "POST"],
    which omitted DELETE entirely -- a real cross-origin browser (the
    Vercel frontend calling this Render backend) would fail CORS
    preflight on DELETE /api/v1/generations/{id} and never even send the
    real request. Verified live against a real server this session
    before adding this test; this makes it a permanent regression check."""
    r = client.options(
        "/api/v1/generations/some-id",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200
    assert "DELETE" in r.headers["access-control-allow-methods"]
