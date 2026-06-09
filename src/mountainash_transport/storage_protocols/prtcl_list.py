from __future__ import annotations

from typing import Protocol, runtime_checkable

from mountainash_transport.dataclasses.file_metadata import FileMetadata


@runtime_checkable
class StorageListProtocol(Protocol):
    """Protocol for listing files and directories in storage."""

    def list_files(self, prefix: str) -> list[FileMetadata]:
        """List all files under the given prefix."""
        ...

    def list_directories(self, prefix: str) -> list[str]:
        """List all directories under the given prefix."""
        ...
