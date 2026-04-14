"""MinIO storage backend — mixin composition for MinIO object storage."""

from __future__ import annotations

import typing as t

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.storage_registry import register_storage_backend

from mountainash_utils_files.storage_backends.s3.s3_copy import S3CopyMixin
from mountainash_utils_files.storage_backends.s3.s3_delete import S3DeleteMixin
from mountainash_utils_files.storage_backends.s3.s3_list import S3ListMixin
from mountainash_utils_files.storage_backends.s3.s3_metadata import S3MetadataMixin
from mountainash_utils_files.storage_backends.s3.s3_read import S3ReadMixin
from mountainash_utils_files.storage_backends.s3.s3_write import S3WriteMixin

from .minio_connection import MinIOConnectionMixin


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.MINIO)
class MinIOStorageBackend(
    MinIOConnectionMixin,
    S3ReadMixin,
    S3WriteMixin,
    S3ListMixin,
    S3DeleteMixin,
    S3MetadataMixin,
    S3CopyMixin,
):
    """MinIO storage backend composed from mixins.

    Reuses all S3 operation mixins — only the connection mixin differs,
    pointing boto3 at a custom MinIO endpoint with ``use_ssl=False`` by default.

    Note: MinIO has no real directory concept in the S3 sense, so
    :class:`~mountainash_utils_files.storage_protocols.StorageDirectoryProtocol`
    is intentionally **not** implemented.
    """

    def __init__(self, auth_params: t.Any) -> None:
        self.auth_params = auth_params
        self._client: t.Any = None


__all__ = [
    "MinIOStorageBackend",
    "MinIOConnectionMixin",
]
