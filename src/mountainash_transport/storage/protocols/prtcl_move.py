from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageMoveProtocol(Protocol):
    """Protocol for renaming a file in place with the store's native rename.

    Implemented only by stores that have one (Local, SFTP); an existing
    destination is replaced. Stores without a rename (S3, HTTP) do not
    implement it, so a move there is never a silent copy and delete.
    """

    def move(self, source: str, destination: str, *, create_parents: bool = True) -> None:
        """Rename *source* to *destination*; backend I/O failures raise typed StorageError subclasses."""
        ...
