"""M5 Phase: lazy singleton wiring engine.learned_generation into the
API layer, same lazy-load discipline api/detectors.py's MLDetector
already uses for DotHeatmapNetV2 -- the scorer checkpoint and motif
library are loaded once, on first request, not at import time (so the
API process still starts even if the checkpoint is missing; the
endpoint then reports 503, same convention as ML_MODEL_UNAVAILABLE).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

_REPO_ROOT = Path(__file__).resolve().parent.parent
_M5_DIR = _REPO_ROOT / "experiments" / "m5_generation"
CHECKPOINT_PATH = _M5_DIR / "checkpoints" / "placement_scorer.pt"
SPLIT_MANIFEST_PATH = _M5_DIR / "data" / "split_manifest.json"

# How many held-out (test-split) source patterns feed the motif library
# and provide candidate target layouts -- fixed at process start, not
# rebuilt per-request (rebuilding per request would make identical seeds
# non-reproducible if the manifest ever changed mid-process).
N_LIBRARY_SOURCES = 5


class GenerationService:
    def __init__(self):
        self._scorer = None
        self._motif_library = None
        self._layouts = None  # list[(name, set[(int,int)])]
        self._library_sources = None
        self._load_error: str | None = None

    def _ensure_loaded(self):
        if self._motif_library is not None or self._load_error is not None:
            return
        try:
            from engine.learned_scoring import load_scorer

            if not CHECKPOINT_PATH.exists():
                raise RuntimeError(f"placement scorer checkpoint not found at {CHECKPOINT_PATH}")
            self._scorer = load_scorer(CHECKPOINT_PATH)

            if not SPLIT_MANIFEST_PATH.exists():
                raise RuntimeError(f"split manifest not found at {SPLIT_MANIFEST_PATH}")
            manifest = json.loads(SPLIT_MANIFEST_PATH.read_text())
            test_sources = [tuple(s.split("#")) for s in manifest["test"]]
            test_sources = [(c, int(p)) for c, p in test_sources]

            from engine.dataset import load_kolam
            from engine.generation_api import motif_library_from_sources

            library_sources = test_sources[:N_LIBRARY_SOURCES]
            self._library_sources = library_sources
            self._motif_library = motif_library_from_sources(list(library_sources))

            layouts = []
            for collection, pid in test_sources:
                pattern = load_kolam(collection, pid)
                layouts.append((f"{collection}#{pid}", pattern.dot_points))
            self._layouts = layouts
        except Exception as e:  # noqa: BLE001 -- captured, surfaced as 503 by the endpoint
            self._load_error = f"{type(e).__name__}: {e}"

    @property
    def available(self) -> bool:
        self._ensure_loaded()
        return self._load_error is None

    @property
    def load_error(self) -> str | None:
        self._ensure_loaded()
        return self._load_error

    def layout_for_seed(self, seed: int):
        self._ensure_loaded()
        name, dots = self._layouts[seed % len(self._layouts)]
        return name, dots

    @property
    def scorer(self):
        self._ensure_loaded()
        return self._scorer

    @property
    def motif_library(self):
        self._ensure_loaded()
        return self._motif_library

    @property
    def library_sources(self):
        self._ensure_loaded()
        return self._library_sources

    def reference_lattice_dims(self) -> tuple[int, int]:
        """Bounding-box (width, height) of the first held-out layout --
        used only to describe the request in the response, since actual
        per-candidate layouts vary by seed (see layout_for_seed)."""
        self._ensure_loaded()
        dots = self._layouts[0][1]
        return (max(p[0] for p in dots) + 1, max(p[1] for p in dots) + 1)


_service: GenerationService | None = None


def get_generation_service() -> GenerationService:
    global _service
    if _service is None:
        _service = GenerationService()
    return _service
