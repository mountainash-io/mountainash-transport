# storage_facade/facade.py

"""StorageFacade — protocol-checked dispatch to registered storage backends."""

from __future__ import annotations

import typing
from typing import BinaryIO

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.dataclasses.file_metadata import FileMetadata
from mountainash_utils_files.exceptions import UnsupportedOperationError
from mountainash_utils_files.storage_protocols import (
    StorageCopyProtocol,
    StorageDeleteProtocol,
    StorageDirectoryProtocol,
    StorageListProtocol,
    StorageMetadataProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
)
from mountainash_utils_files.storage_registry import get_storage_backend


class StorageFacade:
    """Unified user-facing API that dispatches to protocol-checked backends.

    Each operation checks that the underlying backend implements the required
    protocol before delegating, raising :class:`UnsupportedOperationError`
    if the backend does not support the operation.
    """

    def __init__(
        self,
        provider_type: CONST_STORAGE_PROVIDER_TYPE,
        auth_params: typing.Any = None,
    ) -> None:
        self._backend = get_storage_backend(provider_type, auth_params)

    # ------------------------------------------------------------------
    # Convenience factories
    # ------------------------------------------------------------------

    @classmethod
    def for_local(cls) -> StorageFacade:
        """Return a StorageFacade backed by the local filesystem."""
        return cls(CONST_STORAGE_PROVIDER_TYPE.LOCAL, auth_params=None)

    # ------------------------------------------------------------------
    # Protocol introspection
    # ------------------------------------------------------------------

    def supports(self, protocol: type) -> bool:
        """Return True if the backend implements *protocol*."""
        return isinstance(self._backend, protocol)

    def _require(self, protocol: type, operation: str) -> None:
        """Raise UnsupportedOperationError if the backend lacks *protocol*."""
        if not isinstance(self._backend, protocol):
            raise UnsupportedOperationError(
                f"{type(self._backend).__name__} does not support '{operation}'"
            )

    # ------------------------------------------------------------------
    # Read operations (StorageReadProtocol)
    # ------------------------------------------------------------------

    def read(self, path: str) -> bytes:
        """Read file contents and return as bytes."""
        self._require(StorageReadProtocol, "read")
        return self._backend.read_to_bytes(path)

    def read_stream(self, path: str) -> BinaryIO:
        """Read file contents and return as a binary stream."""
        self._require(StorageReadProtocol, "read_stream")
        return self._backend.read_to_stream(path)

    # ------------------------------------------------------------------
    # Write operations (StorageWriteProtocol)
    # ------------------------------------------------------------------

    def write(self, path: str, data: bytes) -> None:
        """Write bytes data to a file at *path*."""
        self._require(StorageWriteProtocol, "write")
        self._backend.write_from_bytes(path, data)

    def write_stream(self, path: str, stream: BinaryIO) -> None:
        """Write data from a binary stream to a file at *path*."""
        self._require(StorageWriteProtocol, "write_stream")
        self._backend.write_from_stream(path, stream)

    # ------------------------------------------------------------------
    # List operations (StorageListProtocol)
    # ------------------------------------------------------------------

    def list_files(self, prefix: str) -> list[FileMetadata]:
        """List all files under *prefix*."""
        self._require(StorageListProtocol, "list_files")
        return self._backend.list_files(prefix)

    def list_directories(self, prefix: str) -> list[str]:
        """List all directories under *prefix*."""
        self._require(StorageListProtocol, "list_directories")
        return self._backend.list_directories(prefix)

    # ------------------------------------------------------------------
    # Delete operations (StorageDeleteProtocol)
    # ------------------------------------------------------------------

    def delete(self, path: str) -> None:
        """Delete the file at *path*."""
        self._require(StorageDeleteProtocol, "delete")
        self._backend.delete_file(path)

    # ------------------------------------------------------------------
    # Metadata operations (StorageMetadataProtocol)
    # ------------------------------------------------------------------

    def exists(self, path: str) -> bool:
        """Return True if *path* exists on the backend."""
        self._require(StorageMetadataProtocol, "exists")
        return self._backend.path_exists(path)

    def metadata(self, path: str) -> FileMetadata:
        """Return metadata for the file at *path*."""
        self._require(StorageMetadataProtocol, "metadata")
        return self._backend.get_metadata(path)

    def get_size(self, path: str) -> int:
        """Return the size in bytes of the file at *path*."""
        self._require(StorageMetadataProtocol, "get_size")
        return self._backend.get_size(path)

    # ------------------------------------------------------------------
    # Copy operations (StorageCopyProtocol)
    # ------------------------------------------------------------------

    def copy(self, source: str, destination: str) -> None:
        """Copy file from *source* to *destination* within the same backend."""
        self._require(StorageCopyProtocol, "copy")
        self._backend.copy(source, destination)

    # ------------------------------------------------------------------
    # Directory operations (StorageDirectoryProtocol)
    # ------------------------------------------------------------------

    def mkdir(self, path: str, parents: bool = True) -> None:
        """Create a directory at *path*, optionally creating parent directories."""
        self._require(StorageDirectoryProtocol, "mkdir")
        self._backend.mkdir(path, parents=parents)

    def rmdir(self, path: str) -> None:
        """Remove the directory at *path*."""
        self._require(StorageDirectoryProtocol, "rmdir")
        self._backend.rmdir(path)
