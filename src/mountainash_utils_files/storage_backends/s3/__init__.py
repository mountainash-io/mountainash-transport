"""S3 storage backend — mixin composition for AWS S3."""

from __future__ import annotations

import typing as t

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.storage_registry import register_storage_backend

from .s3_connection import S3ConnectionMixin
from .s3_copy import S3CopyMixin
from .s3_delete import S3DeleteMixin
from .s3_list import S3ListMixin
from .s3_metadata import S3MetadataMixin
from .s3_read import S3ReadMixin
from .s3_write import S3WriteMixin


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3)
class S3StorageBackend(
    S3ConnectionMixin,
    S3ReadMixin,
    S3WriteMixin,
    S3ListMixin,
    S3DeleteMixin,
    S3MetadataMixin,
    S3CopyMixin,
):
    """Unified AWS S3 storage backend composed from mixins.

    Note: S3 has no real directory concept, so
    :class:`~mountainash_utils_files.storage_protocols.StorageDirectoryProtocol`
    is intentionally **not** implemented.
    """

    def __init__(self, auth_params: t.Any) -> None:
        self.auth_params = auth_params
        self._client: t.Any = None


__all__ = [
    "S3StorageBackend",
    "S3ConnectionMixin",
    "S3ReadMixin",
    "S3WriteMixin",
    "S3ListMixin",
    "S3DeleteMixin",
    "S3MetadataMixin",
    "S3CopyMixin",
]
