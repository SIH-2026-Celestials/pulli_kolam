"""M7 platform integration (follow-up): artifact storage abstraction.

`LocalArtifactStore` (disk under api/storage/) is the only concrete
implementation today -- acceptable for development per this task's own
instruction ("current local artifact storage is acceptable for
development... do not introduce cloud storage yet unless already
configured"). `ArtifactStore` is the seam a future `ObjectArtifactStore`
(S3/GCS) would implement; `api/services/generation.py` depends on this
Protocol, not on `pathlib.Path` directly, so that swap would touch only
this file plus whichever concrete store gets registered.

`storage_path` (persisted on the `Artifact` DB row) is always a
STORE-RELATIVE path (e.g. "artifacts/<uuid>.svg"), never an absolute
filesystem path -- callers never see or need the underlying disk
location, satisfying "do not expose filesystem paths to clients."
"""

from __future__ import annotations

import os
from api.storage.base import Storage as ArtifactStore
from api.storage.local import LocalStorage

_store: ArtifactStore | None = None

def get_artifact_store() -> ArtifactStore:
    global _store
    if _store is None:
        provider = os.environ.get("STORAGE_PROVIDER", "local").lower().strip()
        if provider == "r2":
            # Lazy import: boto3 is only loaded when R2 is actually requested,
            # avoiding top-level crashes in envs without boto3 installed.
            from api.storage.r2 import R2Storage
            # Verify R2 config exists
            if all(os.environ.get(k) for k in ("R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")):
                _store = R2Storage()
            else:
                import sys
                print(
                    "[pulli-api] Warning: STORAGE_PROVIDER=r2 set but credentials missing. Falling back to LocalStorage.",
                    file=sys.stderr
                )
                _store = LocalStorage()
        else:
            _store = LocalStorage()
    return _store


# ---------------------------------------------------------------------------
# Backward-compatibility alias
# Tests and legacy callers may import LocalArtifactStore by name.
# ---------------------------------------------------------------------------
LocalArtifactStore = LocalStorage
