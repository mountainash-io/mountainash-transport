"""SFTP storage backend — read, write, list, delete, and metadata via paramiko."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.exceptions import StorageConnectionError
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
from mountainash_transport.storage.registry import register_storage_backend

from ._helpers import _is_not_found, _wrap_sftp_error
from .sftp_delete import SFTPDeleteMixin
from .sftp_directory import SFTPDirectoryMixin
from .sftp_metadata import SFTPMetadataMixin
from .sftp_read import SFTPReadMixin
from .sftp_write import SFTPWriteMixin


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.SSH)
class SFTPStorageBackend(
    SFTPReadMixin,
    SFTPWriteMixin,
    SFTPDeleteMixin,
    SFTPMetadataMixin,
    SFTPDirectoryMixin,
):
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


__all__ = [
    "SFTPStorageBackend",
    "SFTPReadMixin",
    "SFTPWriteMixin",
    "SFTPDeleteMixin",
    "SFTPMetadataMixin",
    "SFTPDirectoryMixin",
    "_is_not_found",
    "_wrap_sftp_error",
]
