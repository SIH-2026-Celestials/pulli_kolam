"""Object storage Protocol -- the interface every backend (LocalStorage,
R2Storage) implements identically, so callers never branch on which
backend is active.

Keys, not paths: `key` is a backend-relative identifier (e.g.
"artifacts/<uuid>.svg"), never an absolute filesystem path and never
exposed to API clients directly -- callers get a URL via `url()`
instead. This matches api/services/artifact_store.py's existing
"storage_path is always store-relative" rule, extended to also cover a
remote (R2) backend where there is no filesystem path at all.
"""

from __future__ import annotations

from typing import Protocol


class ObjectStorage(Protocol):
    def save(self, key: str, content: bytes, content_type: str) -> None:
        """Write `content` under `key`, creating any needed structure.
        Overwrites if `key` already exists (artifact keys are
        UUID-derived in this codebase, so overwrite is a no-op in
        practice, never a real collision)."""
        ...

    def get(self, key: str) -> "bytes | None":
        """Return the object's bytes, or None if `key` doesn't exist."""
        ...

    def delete(self, key: str) -> None:
        """Remove the object at `key`. No error if it doesn't exist --
        deletion is idempotent, matching typical cleanup-job semantics
        (see docs/DEPLOYMENT.md's artifact retention section)."""
        ...

    def exists(self, key: str) -> bool:
        ...

    def url(self, key: str) -> str:
        """A URL the FRONTEND can use to fetch this object.

        LocalStorage: a backend-relative path meant to be served through
        the FastAPI app itself (api/routes_generations.py's export
        endpoint already streams bytes through the API, not a static
        file server) -- this method exists for interface parity, not
        because local dev serves objects by URL today.

        R2Storage: see its own docstring -- this is deliberately NOT a
        public bucket URL for every object. R2 is private by default;
        only api/routes_generations.py's export endpoint (which already
        enforces "generation ID must exist in our own database" before
        it serves anything) hands out a URL, so nothing here bypasses
        that ownership check by handing the frontend a raw bucket URL of
        its own."""
        ...
