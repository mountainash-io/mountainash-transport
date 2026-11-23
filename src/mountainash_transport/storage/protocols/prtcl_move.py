from __future__ import annotations

from typing import Protocol, runtime_checkable

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry


@runtime_checkable
class StorageMoveProtocol(Protocol):
    """Protocol for renaming a file in place with the store's native rename.

    Implemented only by stores that have one (Local, SFTP); an existing
    destination is replaced. Stores without a rename (S3, HTTP) do not
    implement it, so a move there is never a silent copy and delete.
    """

    def move(self, source: str, destination: str, *, create_parents: bool = True) -> StorageEntry:
        """Rename *source* to *destination* and return its entry; I/O failures raise typed StorageError subclasses."""
        ...
