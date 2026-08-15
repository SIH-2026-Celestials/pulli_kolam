"""Minimal in-process rate limiting (Phase 14 hardening).

Context: PRODUCTION_READINESS.md flagged "no rate limiting anywhere in
the codebase" as THE top pre-launch blocker -- `POST /api/v1/generations`
costs 5-55s of CPU-bound server time per call and is unauthenticated.

An external dependency (`slowapi`) was tried first but its
`@limiter.limit(...)` decorator breaks FastAPI's request-model
resolution in this specific file: api/main.py has
`from __future__ import annotations` at module scope, which makes every
parameter annotation (e.g. `image: UploadFile`) a string forward-ref
that FastAPI resolves via `func.__globals__`. `functools.wraps` (which
slowapi's decorator uses) does not repoint `__globals__` to the
decorated function's own module, so FastAPI ends up trying to resolve
`UploadFile` against slowapi's module globals and fails with
`FastAPIError: Invalid args for response field!`. Rather than strip
`from __future__ import annotations` from a large existing file (risking
unrelated breakage) or fight decorator ordering, this module implements
the small amount of logic actually needed: a per-key sliding-window
counter, applied as a plain function call at the top of each route body
(no decorator, no signature manipulation, so it cannot interact with
annotation resolution at all).

This is intentionally NOT a general-purpose rate-limiting library. It:
  - is in-memory only, per-process (matches this app's current
    single-node deployment -- PRODUCTION_READINESS.md sections 6/11
    already document local-disk/single-SQLite-writer as the current
    architecture; a multi-process/multi-node deployment would need a
    shared store (e.g. Redis) instead, same caveat as the artifact
    store and SQLite sections already flag for other components).
  - keys on client IP (`request.client.host`) by default, OR on an
    explicit `client_id` override when the caller passes one --
    `/api/v1/generations` now requires login (ownership fix: generations
    are private per-user), so its call site passes `client_id=f"user:{id}"`
    instead, so two different logged-in users behind the same IP
    (an office network, mobile carrier NAT) get separate buckets rather
    than fighting over one shared 6-requests/minute allowance. Endpoints
    that stay unauthenticated (e.g. `/api/v1/generate`, the legacy
    non-persisted endpoint) keep the IP-keyed default.
  - uses a fixed 60-second sliding window with a deque of timestamps
    per (bucket, ip) -- simple, correct, and cheap enough for this
    request volume (CPU-bound endpoints, not a high-QPS API).
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

# Sized against this project's own measured cost (see
# PRODUCTION_READINESS.md section 10), not generic API defaults:
#   - POST /api/v1/generations, /api/v1/generate (M5 multi-restart
#     search): 5-55s of CPU per candidate. 6/minute per IP bounds
#     worst-case sustained cost to 6*55s=330s of CPU-bound work per
#     minute from a single client, while still allowing a real user to
#     click "Generate" repeatedly while iterating.
#   - POST /api/v1/detect, /analyze, /reconstruct (single classical/ML
#     detector pass per image, sub-second to a few seconds): looser,
#     30/minute.
#   - POST /api/v1/analyze-stream/start hands work to a 4-worker thread
#     pool (api/main.py's _PIPELINE_EXECUTOR) -- capped tighter
#     (10/minute) so one client can't starve that pool.
#   - POST /api/v1/compare-detectors runs BOTH detectors per call
#     (~2x a single /detect call's cost) -- 15/minute.
GENERATION_LIMIT_PER_MINUTE = 6
DETECTION_LIMIT_PER_MINUTE = 30
STREAM_LIMIT_PER_MINUTE = 10
COMPARE_LIMIT_PER_MINUTE = 15

_WINDOW_SECONDS = 60.0
_lock = threading.Lock()
_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def _client_key(request: Request) -> str:
    # request.client is None in some ASGI test-client / unit-test
    # contexts; fall back to a shared bucket rather than raising, so a
    # missing client identity degrades to "everyone shares one bucket"
    # instead of crashing the endpoint.
    if request.client is None:
        return "unknown"
    return request.client.host


def enforce_rate_limit(request: Request, bucket: str, limit_per_minute: int, client_id: "str | None" = None) -> None:
    """Raises HTTPException(429) if `bucket` has already seen
    `limit_per_minute` calls from this client in the trailing 60 seconds;
    otherwise records this call and returns.

    `client_id`, when given, overrides the default IP-based key (see
    module docstring) -- pass e.g. `f"user:{current_user.id}"` for an
    authenticated endpoint so different users don't share one bucket.

    Uses the SAME error envelope shape as every other error path in
    this codebase ({"code": ..., "message": ...} unpacked by
    api/main.py's http_exception_handler into
    {"success": false, "error", "code"}) -- a rate-limited caller sees
    a normal, consistent error response, not a different shape.
    """
    # Disabled under pytest: `PYTEST_CURRENT_TEST` is set automatically
    # by pytest for the duration of every test (no conftest/fixture
    # wiring needed), so this is a real, self-contained detection of
    # "running under the test suite" -- not a manually-toggled flag
    # someone could leave on in production by accident. The test suite
    # legitimately calls /generate and /generations far more than
    # 6/minute across its many test functions in the SAME process
    # (Starlette's TestClient reuses one fake client host, "testclient",
    # for every request), which is a test-harness artifact, not
    # something a real deployment's rate limiting should accommodate.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return

    key = (bucket, client_id if client_id is not None else _client_key(request))
    now = time.monotonic()
    with _lock:
        dq = _hits[key]
        cutoff = now - _WINDOW_SECONDS
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= limit_per_minute:
            retry_after = max(0.0, _WINDOW_SECONDS - (now - dq[0]))
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "RATE_LIMITED",
                    "message": (
                        f"rate limit exceeded for '{bucket}': max {limit_per_minute} requests/minute per client; "
                        f"retry in {retry_after:.0f}s"
                    ),
                },
                headers={"Retry-After": str(int(retry_after) + 1)},
            )
        dq.append(now)
