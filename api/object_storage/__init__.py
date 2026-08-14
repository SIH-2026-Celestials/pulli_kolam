"""Object storage abstraction (Phase 5/6 of the deployment-hardening task).

Named `api/object_storage/` rather than the literal `api/storage/` the
task suggested -- `api/storage/` already exists on disk as the LOCAL
ARTIFACT ROOT DIRECTORY (api/storage/artifacts/*.svg etc., written by
api/services/artifact_store.py's LocalArtifactStore), not a Python
package. Putting new source files inside it would mix code with
hundreds of runtime-generated binary artifacts in the same directory --
confirmed by inspecting the repo before writing this (per this task's
own "do not assume anything" instruction), not a guess.

`get_object_storage()` is the single factory both the existing
api/services/artifact_store.py and any future caller should use --
returns LocalStorage (api/object_storage/local.py) unless
STORAGE_BACKEND=r2, in which case it returns R2Storage
(api/object_storage/r2.py), reading R2_* env vars documented in
docs/DEPLOYMENT.md and .env.example.
"""

from __future__ import annotations

import os

from api.object_storage.base import ObjectStorage

_store: "ObjectStorage | None" = None


def get_object_storage() -> ObjectStorage:
    global _store
    if _store is not None:
        return _store

    backend = os.environ.get("STORAGE_BACKEND", "local").strip().lower()
    if backend == "r2":
        from api.object_storage.r2 import R2Storage

        _store = R2Storage.from_env()
    elif backend == "local":
        from api.object_storage.local import LocalStorage

        _store = LocalStorage()
    else:
        raise RuntimeError(f"STORAGE_BACKEND must be 'local' or 'r2', got {backend!r}")
    return _store


def reset_object_storage_cache() -> None:
    """Test-only: force the next get_object_storage() call to rebuild
    the singleton (e.g. after changing STORAGE_BACKEND mid-process)."""
    global _store
    _store = None
