"""Shared pytest fixtures for api/tests/.

Autouse rate-limit reset: api/rate_limit.py's in-process hit counters
are module-level global state (by design -- see its docstring, this is
a real per-process limiter, not a mock). Left alone, running the full
test suite in one process means every test sharing the TestClient's
"testclient" IP bucket -- tests later in the run start seeing real 429s
from the earlier tests' generation calls, which is a test-isolation
artifact of running many requests in one process, not a product bug.
Resetting the counters before each test keeps each test's rate-limit
behavior independent of run order/position, matching how the limiter
actually behaves in production (one bucket per real client, not one
bucket per test suite).
"""

import os
import pytest

os.environ["PULLI_TESTING"] = "true"


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from api.rate_limit import _hits

    _hits.clear()
    yield
    _hits.clear()
