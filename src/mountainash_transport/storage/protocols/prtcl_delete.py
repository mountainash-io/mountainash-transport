from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable


@runtime_checkable
class StorageDeleteProtocol(Protocol):
    """Protocol for deleting files from storage."""

    def delete_file(self, path: str) -> None:
        """Delete a file with backend-native idempotence and typed I/O failures."""
        ...

    def delete_many(self, paths: Iterable[str]) -> None:
        """Delete every path, attempting all of them; a missing path counts as deleted.

        Raises ``BulkDeleteError`` once at the end, listing in input order every
        path that could not be deleted with its typed ``StorageError``.
        """
        ...
