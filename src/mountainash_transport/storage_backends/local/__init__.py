"""Local filesystem storage backend."""

from __future__ import annotations

from mountainash_transport.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.storage_registry import register_storage_backend
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol

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

    def __init__(self, storage_profile: StorageProfileProtocol, *, auth_profile=None) -> None:
        self.storage_profile = storage_profile
        self.auth_profile = auth_profile


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
