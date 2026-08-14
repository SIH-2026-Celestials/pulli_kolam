from __future__ import annotations

import os
from pathlib import Path
from api.storage.base import Storage

class LocalStorage(Storage):
    """Disk-backed store. Every relative_path is resolved under the storage root."""

    def __init__(self, root: Path | None = None):
        self.root = root or (Path(__file__).resolve().parent.parent / "storage")
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        resolved = (self.root / relative_path).resolve()
        if not str(resolved).startswith(str(self.root.resolve())):
            raise ValueError(f"path traversal attempt: {relative_path!r} escapes root")
        return resolved

    def save(self, relative_path: str, content: bytes | str, content_type: str) -> None:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_bytes(content)

    def get(self, relative_path: str) -> bytes | None:
        path = self._resolve(relative_path)
        if not path.exists():
            return None
        return path.read_bytes()

    def delete(self, relative_path: str) -> None:
        path = self._resolve(relative_path)
        if path.exists():
            path.unlink()

    def exists(self, relative_path: str) -> bool:
        return self._resolve(relative_path).exists()

    def url(self, relative_path: str) -> str:
        # For local storage, return a relative API url or base url path
        return f"/api/v1/generations/artifacts/{relative_path}"

    # Compatibility methods
    def write(self, relative_path: str, content: str, content_type: str) -> None:
        self.save(relative_path, content, content_type)

    def write_bytes(self, relative_path: str, content: bytes, content_type: str) -> None:
        self.save(relative_path, content, content_type)

    def read(self, relative_path: str) -> str | None:
        val = self.get(relative_path)
        if val is None:
            return None
        return val.decode("utf-8")

    def read_bytes(self, relative_path: str) -> bytes | None:
        return self.get(relative_path)
