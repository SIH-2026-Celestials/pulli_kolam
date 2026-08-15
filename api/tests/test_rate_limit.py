"""Unit tests for api/rate_limit.py's sliding-window limiter itself --
direct function calls, not through the full app/DB, and with the
PYTEST_CURRENT_TEST auto-disable (see rate_limit.py's own docstring)
explicitly bypassed via monkeypatch so these tests actually exercise the
enforcement path a real deployment would hit.
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi import HTTPException, Request

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from api import rate_limit as rl  # noqa: E402


def _fake_request(ip: str = "203.0.113.1") -> Request:
    scope = {
        "type": "http", "client": (ip, 12345), "headers": [], "method": "POST", "path": "/x",
        "query_string": b"", "server": ("test", 80), "scheme": "http",
    }
    return Request(scope)


@pytest.fixture(autouse=True)
def _reset_hits():
    rl._hits.clear()
    yield
    rl._hits.clear()


def _enable_rate_limiting(monkeypatch):
    """The limiter no-ops under pytest by design (see rate_limit.py's
    `PYTEST_CURRENT_TEST` check). pytest re-writes that env var at every
    phase transition (setup -> call -> teardown), so deleting it from a
    fixture's setup doesn't survive into the test body -- it must be
    deleted from WITHIN the test function itself (the "call" phase),
    after pytest's own last write for that phase."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)


def test_allows_up_to_the_limit_then_429s(monkeypatch):
    _enable_rate_limiting(monkeypatch)
    req = _fake_request()
    for _ in range(3):
        rl.enforce_rate_limit(req, "test-bucket", 3)  # must not raise
    with pytest.raises(HTTPException) as exc_info:
        rl.enforce_rate_limit(req, "test-bucket", 3)
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["code"] == "RATE_LIMITED"


def test_429_response_has_retry_after_header(monkeypatch):
    _enable_rate_limiting(monkeypatch)
    req = _fake_request()
    rl.enforce_rate_limit(req, "test-bucket", 1)
    with pytest.raises(HTTPException) as exc_info:
        rl.enforce_rate_limit(req, "test-bucket", 1)
    assert "Retry-After" in exc_info.value.headers
    assert int(exc_info.value.headers["Retry-After"]) > 0


def test_different_ips_get_separate_buckets(monkeypatch):
    _enable_rate_limiting(monkeypatch)
    req_a = _fake_request("203.0.113.1")
    req_b = _fake_request("203.0.113.2")
    rl.enforce_rate_limit(req_a, "test-bucket", 1)
    rl.enforce_rate_limit(req_b, "test-bucket", 1)  # must NOT raise -- different IP


def test_authenticated_client_id_isolates_users_behind_the_same_ip(monkeypatch):
    """The generation endpoint now passes client_id=f"user:{id}" (see
    api/routes_generations.py) specifically so two different logged-in
    users sharing one IP (office network, NAT) don't exhaust each
    other's quota."""
    _enable_rate_limiting(monkeypatch)
    shared_ip_request_user_a = _fake_request("203.0.113.9")
    shared_ip_request_user_b = _fake_request("203.0.113.9")

    rl.enforce_rate_limit(shared_ip_request_user_a, "generations", 1, client_id="user:1")
    with pytest.raises(HTTPException):
        rl.enforce_rate_limit(shared_ip_request_user_a, "generations", 1, client_id="user:1")

    # User B, same IP, different client_id -- must NOT be blocked by
    # user A's usage.
    rl.enforce_rate_limit(shared_ip_request_user_b, "generations", 1, client_id="user:2")
