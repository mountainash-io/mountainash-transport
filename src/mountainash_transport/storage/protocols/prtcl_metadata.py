from __future__ import annotations

from typing import Protocol, runtime_checkable

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry


@runtime_checkable
class StorageMetadataProtocol(Protocol):
    """Retrieve metadata; backend failures raise typed StorageError subclasses."""

    def get_metadata(self, path: str) -> StorageEntry:
        """Retrieve metadata for a file, directory, or object-store resource."""
        ...

    def path_exists(self, path: str) -> bool:
        """Return False only for established absence; operational failures raise."""
        ...

    def get_size(self, path: str) -> int | None:
        """Return size (including zero), or None if present with unknown size.

        Missing resources raise PathNotFoundError; operational failures raise
        their typed storage error rather than returning None.
        """
        ...
