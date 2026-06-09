"""S3 storage backend — unified S3-family handler.

A single :class:`S3StorageBackend` class is registered against all five
S3-compatible provider types (S3, S3Express, R2, MinIO, B2). Per-flavor
differences (endpoint URL, ``use_ssl`` defaults, ``region_name="auto"`` for
R2) are handled inside :class:`S3ConnectionMixin` by reading
``auth_params.settings.FLAVOR`` when available.

Backwards-compatible class aliases are exported so legacy imports
(``from mountainash_transport.storage.backends.s3 import R2StorageBackend``
or via the deleted ``storage_backends.r2`` module) still resolve.
"""

from __future__ import annotations

import typing as t

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.storage.registry import register_storage_backend
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol

from .s3_connection import S3ConnectionMixin
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
    S3ConnectionMixin,
    S3ReadMixin,
    S3WriteMixin,
    S3ListMixin,
    S3DeleteMixin,
    S3MetadataMixin,
    S3CopyMixin,
):
    """Unified S3-family storage backend.

    Wraps boto3 for AWS S3, AWS S3 Express One Zone, Cloudflare R2, MinIO,
    and Backblaze B2. Flavor dispatch happens in :meth:`connect` via
    ``auth_params.settings.FLAVOR`` (default ``"aws"``).

    Note: None of the S3-compatible services implement a real directory
    concept, so :class:`StorageDirectoryProtocol` is intentionally **not**
    implemented.
    """

    def __init__(self, storage_profile: StorageProfileProtocol, *, auth_profile=None) -> None:

        self.storage_profile = storage_profile
        self.auth_profile = auth_profile
        self._client: t.Any = None


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
    "S3ConnectionMixin",
    "S3ReadMixin",
    "S3WriteMixin",
    "S3ListMixin",
    "S3DeleteMixin",
    "S3MetadataMixin",
    "S3CopyMixin",
]
