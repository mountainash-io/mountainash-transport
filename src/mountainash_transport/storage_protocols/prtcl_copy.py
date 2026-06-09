from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageCopyProtocol(Protocol):
    """Protocol for copying files within or across storage locations."""

    def copy(self, source: str, destination: str) -> None:
        """Copy a file from source path to destination path."""
        ...
