"""Local disk backend -- development default (STORAGE_BACKEND unset or
"local"). Same root and same path-traversal guard as the pre-existing
api/services/artifact_store.py:LocalArtifactStore (that class is
unchanged and still what api/services/generation.py calls today; this
is a parallel, save/get/delete/exists/url-shaped implementation of the
SAME storage semantics for callers that go through
api/object_storage.get_object_storage() instead -- see that module's
docstring for why two entry points exist during this migration, and
docs/DEPLOYMENT.md for the plan to consolidate onto this one)."""

from __future__ import annotations

from pathlib import Path


class LocalStorage:
    def __init__(self, root: "Path | None" = None):
        self.root = root or (Path(__file__).resolve().parent.parent / "storage")
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        resolved = (self.root / key).resolve()
        if not str(resolved).startswith(str(self.root.resolve())):
            raise ValueError(f"object key escapes storage root: {key!r}")
        return resolved

    def save(self, key: str, content: bytes, content_type: str) -> None:  # noqa: ARG002 -- content_type unused for local disk (no metadata store)
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def get(self, key: str) -> "bytes | None":
        path = self._resolve(key)
        if not path.exists():
            return None
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        path.unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def url(self, key: str) -> str:
        # Not a real HTTP URL -- local dev never serves objects directly
        # by path (api/routes_generations.py's export endpoint streams
        # bytes through the API instead). Returned for interface parity
        # with R2Storage.url(); do not treat this as web-accessible.
        return f"/local-storage/{key}"
