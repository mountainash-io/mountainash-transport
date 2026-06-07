"""Local filesystem storage backend."""

from __future__ import annotations

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.storage_registry import register_storage_backend

from .local_connection import LocalConnectionMixin
from .local_copy import LocalCopyMixin
from .local_delete import LocalDeleteMixin
from .local_directory import LocalDirectoryMixin
from .local_list import LocalListMixin
from .local_metadata import LocalMetadataMixin
from .local_read import LocalReadMixin
from .local_write import LocalWriteMixin


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
class LocalStorageBackend(
    LocalConnectionMixin,
    LocalReadMixin,
    LocalWriteMixin,
    LocalListMixin,
    LocalDeleteMixin,
    LocalMetadataMixin,
    LocalCopyMixin,
    LocalDirectoryMixin,
):
    """Unified local filesystem storage backend composed from mixins."""

    def __init__(self, profile=None, *, auth=None) -> None:
        self.auth_params = profile


__all__ = [
    "LocalStorageBackend",
    "LocalConnectionMixin",
    "LocalReadMixin",
    "LocalWriteMixin",
    "LocalListMixin",
    "LocalDeleteMixin",
    "LocalMetadataMixin",
    "LocalCopyMixin",
    "LocalDirectoryMixin",
]
