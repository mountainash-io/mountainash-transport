"""S3 storage backend — unified S3-family handler.

A single :class:`S3StorageBackend` class is registered against all five
S3-compatible provider types (S3, S3Express, R2, MinIO, B2). Per-flavor
differences (endpoint URL, ``use_ssl`` defaults, ``region_name="auto"`` for
R2) are resolved at connection time via :class:`S3Connection`.

Backwards-compatible class aliases are exported so legacy imports
(``from mountainash_transport.storage.backends.s3 import R2StorageBackend``
or via the deleted ``storage_backends.r2`` module) still resolve.
"""

from __future__ import annotations

import typing as t

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.exceptions import StorageConnectionError
from mountainash_transport.storage.registry import register_storage_backend
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol

from .s3_copy import S3CopyMixin
from .s3_delete import S3DeleteMixin
from .s3_list import S3ListMixin
from .s3_metadata import S3MetadataMixin
from .s3_read import S3ReadMixin
from .s3_write import S3WriteMixin


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3)
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS)
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.R2)
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.MINIO)
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.B2)
class S3StorageBackend(
    S3ReadMixin,
    S3WriteMixin,
    S3ListMixin,
    S3DeleteMixin,
    S3MetadataMixin,
    S3CopyMixin,
):
    """Unified S3-family storage backend.

    Wraps boto3 for AWS S3, AWS S3 Express One Zone, Cloudflare R2, MinIO,
    and Backblaze B2. Connection management is handled by the injected
    :class:`S3Connection` instance.

    Note: None of the S3-compatible services implement a real directory
    concept, so :class:`StorageDirectoryProtocol` is intentionally **not**
    implemented.
    """

    def __init__(self, storage_profile: StorageProfileProtocol, *, connection=None) -> None:

        self.storage_profile = storage_profile
        self._connection = connection
        self._client: t.Any = None

    def connect(self) -> None:
        """Delegate to injected S3Connection, or raise if none provided."""
        if self._connection is None:
            raise StorageConnectionError(
                "S3StorageBackend requires a connection — use create_connection()"
            )
        if not self._connection.is_connected:
            self._connection.connect()
        self._client = self._connection.client

    def disconnect(self) -> None:
        """Release the cached boto3 client."""
        self._client = None

    def is_connected(self) -> bool:
        """Return True if a client has been created."""
        return self._client is not None


# --- Backwards-compatible aliases ------------------------------------------
# Preserves ``from mountainash_transport.storage.backends.s3 import
# R2StorageBackend`` etc. Also allows the shim modules
# ``storage_backends.{r2,s3express,minio}`` to simply re-export these names.
R2StorageBackend = S3StorageBackend
S3ExpressStorageBackend = S3StorageBackend
MinIOStorageBackend = S3StorageBackend
B2StorageBackend = S3StorageBackend


__all__ = [
    "S3StorageBackend",
    "R2StorageBackend",
    "S3ExpressStorageBackend",
    "MinIOStorageBackend",
    "B2StorageBackend",
    "S3ReadMixin",
    "S3WriteMixin",
    "S3ListMixin",
    "S3DeleteMixin",
    "S3MetadataMixin",
    "S3CopyMixin",
]
