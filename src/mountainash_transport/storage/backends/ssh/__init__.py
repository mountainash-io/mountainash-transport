"""SFTP storage backend — read, write, list, delete, and metadata via paramiko."""
from __future__ import annotations

import errno
import io
import typing as t
from datetime import datetime

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.dataclasses.file_metadata import FileMetadata
from mountainash_transport._core.exceptions import (
    PathNotFoundError,
    StorageConnectionError,
    StorageError,
)
from mountainash_transport.storage.registry import register_storage_backend
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol


def _is_not_found(exc: BaseException) -> bool:
    if isinstance(exc, FileNotFoundError):
        return True
    if isinstance(exc, IOError) and getattr(exc, "errno", None) == errno.ENOENT:
        return True
    return False


def _wrap_sftp_error(exc: BaseException, path: str) -> StorageError:
    if _is_not_found(exc):
        return PathNotFoundError(f"Path not found: {path}")
    if isinstance(exc, PermissionError) or (
        isinstance(exc, IOError) and getattr(exc, "errno", None) == errno.EACCES
    ):
        return StorageError(f"Permission denied: {path}")
    if isinstance(exc, IOError) and getattr(exc, "errno", None) in (
        errno.ENOTDIR, errno.EISDIR
    ):
        return StorageError(f"Invalid path type: {path}")
    return StorageError(f"SFTP error for {path}: {exc}")


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.SSH)
class SFTPStorageBackend:
    """SFTP storage backend — implements Read, Write, List, Delete, Metadata."""

    def __init__(
        self,
        storage_profile: StorageProfileProtocol | None = None,
        *,
        connection: t.Any = None,
    ) -> None:
        self._connection = connection
        self.storage_profile = storage_profile

    def _get_client(self) -> t.Any:
        if self._connection is not None and self._connection.client is not None:
            return self._connection.client
        raise StorageConnectionError(
            "SFTPStorageBackend requires a connection — use create_connection()"
        )

    def read_to_bytes(self, path: str) -> bytes:
        sftp = self._get_client()
        try:
            with sftp.open(path, "rb") as f:
                return f.read()
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

    def read_to_stream(self, path: str) -> t.BinaryIO:
        data = self.read_to_bytes(path)
        return io.BytesIO(data)

    def write_from_bytes(self, path: str, data: bytes) -> None:
        sftp = self._get_client()
        try:
            with sftp.open(path, "wb") as f:
                f.write(data)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

    def write_from_stream(self, path: str, stream: t.BinaryIO) -> None:
        self.write_from_bytes(path, stream.read())

    def list_paths(self, path: str) -> list[str]:
        sftp = self._get_client()
        try:
            entries = sftp.listdir_attr(path)
            return [entry.filename for entry in entries]
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

    def delete_path(self, path: str) -> None:
        sftp = self._get_client()
        try:
            sftp.remove(path)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

    def path_exists(self, path: str) -> bool:
        sftp = self._get_client()
        try:
            sftp.stat(path)
            return True
        except (FileNotFoundError, IOError):
            return False

    def get_metadata(self, path: str) -> FileMetadata:
        sftp = self._get_client()
        try:
            stat = sftp.stat(path)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

        filename = path.rsplit("/", 1)[-1] if "/" in path else path
        directory = path.rsplit("/", 1)[0] if "/" in path else "/"

        last_modified = None
        mtime = getattr(stat, "st_mtime", None)
        if mtime is not None:
            try:
                last_modified = datetime.fromtimestamp(mtime)
            except (ValueError, OSError):
                pass

        return FileMetadata(
            filename=filename,
            directory=directory,
            full_path=path,
            size=getattr(stat, "st_size", 0) or 0,
            last_modified=last_modified,
            source="sftp",
        )

    def get_size(self, path: str) -> int:
        sftp = self._get_client()
        try:
            stat = sftp.stat(path)
            return getattr(stat, "st_size", 0) or 0
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc


__all__ = ["SFTPStorageBackend"]
