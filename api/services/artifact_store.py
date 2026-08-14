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

from pathlib import Path
from typing import Protocol


class ArtifactStore(Protocol):
    def write(self, relative_path: str, content: str, content_type: str) -> None: ...
    def write_bytes(self, relative_path: str, content: bytes, content_type: str) -> None: ...
    def read(self, relative_path: str) -> "str | None": ...
    def read_bytes(self, relative_path: str) -> "bytes | None": ...
    def exists(self, relative_path: str) -> bool: ...


class LocalArtifactStore:
    """Disk-backed store rooted at `api/storage/`. Every `relative_path`
    is resolved under this root and never allowed to escape it (rejects
    `..` path traversal) -- the one safety property that matters even
    for a purely local/dev store, since `relative_path` values are
    ultimately derived from database-generated UUIDs, not raw user
    input, but defense-in-depth costs nothing here."""

    def __init__(self, root: "Path | None" = None):
        self.root = root or (Path(__file__).resolve().parent.parent / "storage")
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        resolved = (self.root / relative_path).resolve()
        if not str(resolved).startswith(str(self.root.resolve())):
            raise ValueError(f"artifact path escapes storage root: {relative_path!r}")
        return resolved

    def write(self, relative_path: str, content: str, content_type: str) -> None:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_bytes(self, relative_path: str, content: bytes, content_type: str) -> None:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def read(self, relative_path: str) -> "str | None":
        path = self._resolve(relative_path)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def read_bytes(self, relative_path: str) -> "bytes | None":
        path = self._resolve(relative_path)
        if not path.exists():
            return None
        return path.read_bytes()

    def exists(self, relative_path: str) -> bool:
        return self._resolve(relative_path).exists()


_store: "LocalArtifactStore | None" = None


def get_artifact_store() -> ArtifactStore:
    global _store
    if _store is None:
        _store = LocalArtifactStore()
    return _store
