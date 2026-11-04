from __future__ import annotations

from typing import Protocol, runtime_checkable

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry


@runtime_checkable
class StorageDirectoryProtocol(Protocol):
    """Manage directories, translating backend I/O into StorageError subclasses."""

    def list_dir(self, path: str) -> list[StorageEntry]:
        """List the direct children of a directory, returning StorageEntry objects."""
        ...

    def mkdir(self, path: str, *, parents: bool = True) -> None:
        """Create a directory.

        With parents=True, create missing ancestors and accept an existing
        directory. With parents=False, create only the final directory and
        fail if its parent is missing or the destination already exists.
        """
        ...

    def rmdir(self, path: str, *, recursive: bool = False) -> None:
        """Remove the directory at *path*.

        By default only an empty directory is removed; a non-empty one raises
        ``StorageError`` and is left untouched. ``recursive=True`` removes the
        directory and everything beneath it; symbolic links inside are removed,
        never followed. A missing path raises ``PathNotFoundError``; a file or a
        link to a directory raises ``StorageError`` and is not removed, in
        either mode.
        """
        ...
