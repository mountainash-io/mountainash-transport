"""SFTP storage backend — read, ranged read, write, delete, metadata, directories and enumeration via paramiko."""
from __future__ import annotations

import contextlib
import typing as t

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.exceptions import StorageConnectionError
from mountainash_transport._core.retry import ExecutorRetry, retry_policy_from
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
from mountainash_transport.storage.registry import register_storage_backend

from .sftp_delete import SFTPDeleteMixin
from .sftp_directory import SFTPDirectoryMixin
from .sftp_enumerate import SFTPEnumerateMixin
from .sftp_metadata import SFTPMetadataMixin
from .sftp_move import SFTPMoveMixin
from .sftp_read import SFTPReadMixin
from .sftp_write import SFTPWriteMixin

if t.TYPE_CHECKING:
    from mountainash_transport._core.dataclasses import EnumerateResult, StorageEntry
    from mountainash_transport._core.ranged_io import RangedSource


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.SFTP)
class SFTPStorageBackend(
    SFTPReadMixin,
    SFTPWriteMixin,
    SFTPDeleteMixin,
    SFTPMetadataMixin,
    SFTPDirectoryMixin,
    SFTPEnumerateMixin,
    SFTPMoveMixin,
):
    """SFTP storage backend: Read (including ranged reads), Write, Delete, Metadata, Directory, Enumerate and Move.

    Every operation that loses its SSH session is retried under the profile's
    ``RETRY_*`` fields, reconnecting before each retry. A stream returned by
    ``read_to_stream`` or ``open_ranged`` is not: only opening it is retried.
    ``write_from_stream`` is retried only for a seekable source, which is sent
    again from the position it started at. A ``move`` whose reply was lost
    with the session finds its source gone on retry and raises ``PathNotFoundError``.
    """

    def __init__(
        self,
        storage_profile: StorageProfileProtocol | None = None,
        *,
        connection: t.Any = None,
    ) -> None:
        self._connection = connection
        self.storage_profile = storage_profile
        self._retry = ExecutorRetry(retry_policy_from(storage_profile),
                                    is_transient=self._is_transient, recover=self._reconnect)

    def _get_client(self) -> t.Any:
        if self._connection is not None and self._connection.client is not None:
            return self._connection.client
        raise StorageConnectionError(
            "SFTPStorageBackend requires a connection — use create_connection()"
        )

    def _is_transient(self, exc: BaseException) -> bool:
        """A lost session, or a failed reconnect whatever its cause; never a path, permission or auth error.

        The connection layer does not keep paramiko's reason for a failed
        reconnect, so a password or host key rejected on reconnect is tried
        again until the attempts run out.
        """
        from mountainash_transport.connections.errors import TransportConnectionError  # [http] stack

        return self._connection is not None and isinstance(exc, (StorageConnectionError, TransportConnectionError))

    def _reconnect(self) -> None:
        # A dropped session still looks connected; close what is left, then connect afresh.
        with contextlib.suppress(Exception):
            self._connection.disconnect()
        self._connection.connect()

    def read_to_bytes(self, path: str) -> bytes:
        return self._retry.call(lambda: super(SFTPStorageBackend, self).read_to_bytes(path))

    def read_to_stream(self, path: str) -> t.BinaryIO:
        return self._retry.call(lambda: super(SFTPStorageBackend, self).read_to_stream(path))

    def open_ranged(self, path: str) -> RangedSource:
        return self._retry.call(lambda: super(SFTPStorageBackend, self).open_ranged(path))

    def write_from_bytes(self, path: str, data: bytes, *, create_parents: bool = True) -> None:
        self._retry.call(lambda: super(SFTPStorageBackend, self).write_from_bytes(
            path, data, create_parents=create_parents))

    def write_from_stream(self, path: str, stream: t.BinaryIO, *, create_parents: bool = True) -> None:
        seekable = stream.seekable()
        start = stream.tell() if seekable else 0

        def upload() -> None:
            if seekable:
                stream.seek(start)
            super(SFTPStorageBackend, self).write_from_stream(path, stream, create_parents=create_parents)

        self._retry.call(upload, replayable=seekable)

    def delete_file(self, path: str) -> None:
        self._retry.call(lambda: super(SFTPStorageBackend, self).delete_file(path))

    def path_exists(self, path: str) -> bool:
        return self._retry.call(lambda: super(SFTPStorageBackend, self).path_exists(path))

    def get_metadata(self, path: str) -> StorageEntry:
        return self._retry.call(lambda: super(SFTPStorageBackend, self).get_metadata(path))

    def get_size(self, path: str) -> int | None:
        return self._retry.call(lambda: super(SFTPStorageBackend, self).get_size(path))

    def list_dir(self, path: str) -> list[StorageEntry]:
        return self._retry.call(lambda: super(SFTPStorageBackend, self).list_dir(path))

    def mkdir(self, path: str, *, parents: bool = True) -> None:
        self._retry.call(lambda: super(SFTPStorageBackend, self).mkdir(path, parents=parents))

    def rmdir(self, path: str, *, recursive: bool = False) -> None:
        self._retry.call(lambda: super(SFTPStorageBackend, self).rmdir(path, recursive=recursive))

    def list_objects(
        self, prefix: str, *, delimiter: str | None = None, max_results: int | None = None,
    ) -> EnumerateResult:
        return self._retry.call(lambda: super(SFTPStorageBackend, self).list_objects(
            prefix, delimiter=delimiter, max_results=max_results))

    def move(self, source: str, destination: str, *, create_parents: bool = True) -> None:
        self._retry.call(lambda: super(SFTPStorageBackend, self).move(
            source, destination, create_parents=create_parents))


__all__ = [
    "SFTPStorageBackend",
    "SFTPReadMixin",
    "SFTPWriteMixin",
    "SFTPDeleteMixin",
    "SFTPMetadataMixin",
    "SFTPDirectoryMixin",
    "SFTPEnumerateMixin",
]
