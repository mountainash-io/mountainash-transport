"""S3 Express storage backend — mixin composition for AWS S3 Express One Zone."""

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

from .s3express_connection import S3ExpressConnectionMixin


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS)
class S3ExpressStorageBackend(
    S3ExpressConnectionMixin,
    S3ReadMixin,
    S3WriteMixin,
    S3ListMixin,
    S3DeleteMixin,
    S3MetadataMixin,
    S3CopyMixin,
):
    """AWS S3 Express One Zone storage backend composed from mixins.

    Reuses all S3 operation mixins — only the connection mixin differs,
    allowing future S3 Express-specific session handling without modifying
    the operation layer.

    Note: S3 Express has no real directory concept, so
    :class:`~mountainash_utils_files.storage_protocols.StorageDirectoryProtocol`
    is intentionally **not** implemented.
    """

    def __init__(self, auth_params: t.Any) -> None:
        self.auth_params = auth_params
        self._client: t.Any = None


__all__ = [
    "S3ExpressStorageBackend",
    "S3ExpressConnectionMixin",
]
