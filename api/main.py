from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.main import app
from api.v1_router import router as v1_router

# Include /api/v1 endpoints
app.include_router(v1_router)

__all__ = ["app"]
