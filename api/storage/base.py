from __future__ import annotations

from typing import Protocol

class Storage(Protocol):
    def save(self, relative_path: str, content: bytes | str, content_type: str) -> None:
        """Save content (bytes or str) to storage."""
        ...

    def get(self, relative_path: str) -> bytes | None:
        """Get content as bytes from storage."""
        ...

    def delete(self, relative_path: str) -> None:
        """Delete file/object from storage."""
        ...

    def exists(self, relative_path: str) -> bool:
        """Check if file/object exists in storage."""
        ...

    def url(self, relative_path: str) -> str:
        """Get public or signed URL for the object."""
        ...

    # Compatibility methods to avoid breaking existing code in PULLI
    def write(self, relative_path: str, content: str, content_type: str) -> None:
        ...

    def write_bytes(self, relative_path: str, content: bytes, content_type: str) -> None:
        ...

    def read(self, relative_path: str) -> str | None:
        ...

    def read_bytes(self, relative_path: str) -> bytes | None:
        ...
