from __future__ import annotations

from typing import Protocol, runtime_checkable

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry


@runtime_checkable
class StorageDirectoryProtocol(Protocol):
    """Protocol for managing directories in storage."""

    def list_dir(self, path: str) -> list[StorageEntry]:
        """List the direct children of a directory, returning StorageEntry objects."""
        ...

    def mkdir(self, path: str, *, parents: bool = True) -> None:
        """Create a directory at the given path, optionally creating parent directories."""
        ...

    def rmdir(self, path: str) -> None:
        """Remove the directory at the given path."""
        ...
