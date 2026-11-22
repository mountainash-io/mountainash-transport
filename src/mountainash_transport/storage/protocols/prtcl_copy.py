from __future__ import annotations

from typing import Protocol, runtime_checkable

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry


@runtime_checkable
class StorageCopyProtocol(Protocol):
    """Protocol for copying files within or across storage locations."""

    def copy(self, source: str, destination: str) -> StorageEntry:
        """Copy a file and return the copy's entry; I/O failures raise typed StorageError subclasses."""
        ...
