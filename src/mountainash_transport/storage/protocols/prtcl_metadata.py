from __future__ import annotations

from typing import Protocol, runtime_checkable

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry


@runtime_checkable
class StorageMetadataProtocol(Protocol):
    """Protocol for retrieving file metadata from storage."""

    def get_metadata(self, path: str) -> StorageEntry:
        """Retrieve metadata for the file at the given path."""
        ...

    def path_exists(self, path: str) -> bool:
        """Check whether a file or directory exists at the given path."""
        ...

    def get_size(self, path: str) -> int | None:
        """Return the size in bytes of the file at the given path, or None if unknown."""
        ...
