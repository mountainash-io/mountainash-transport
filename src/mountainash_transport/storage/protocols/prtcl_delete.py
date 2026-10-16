from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageDeleteProtocol(Protocol):
    """Protocol for deleting files from storage."""

    def delete_file(self, path: str) -> None:
        """Delete a file with backend-native idempotence and typed I/O failures."""
        ...
