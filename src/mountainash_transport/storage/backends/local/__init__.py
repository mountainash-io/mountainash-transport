"""Local filesystem storage backend."""

from __future__ import annotations

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.storage.registry import register_storage_backend
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol

from .local_copy import LocalCopyMixin
from .local_delete import LocalDeleteMixin
from .local_directory import LocalDirectoryMixin
from .local_list import LocalListMixin
from .local_metadata import LocalMetadataMixin
from .local_read import LocalReadMixin
from .local_write import LocalWriteMixin


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
class LocalStorageBackend(
    LocalReadMixin,
    LocalWriteMixin,
    LocalListMixin,
    LocalDeleteMixin,
    LocalMetadataMixin,
    LocalCopyMixin,
    LocalDirectoryMixin,
):
    """Unified local filesystem storage backend composed from mixins."""

    def __init__(self, storage_profile: StorageProfileProtocol, *, connection=None) -> None:
        self.storage_profile = storage_profile
        self._connection = connection

    def connect(self) -> None:
        """No-op: local filesystem requires no connection."""

    def disconnect(self) -> None:
        """No-op: local filesystem requires no disconnection."""

    def is_connected(self) -> bool:
        """Always connected for local filesystem."""
        return True


__all__ = [
    "LocalStorageBackend",
    "LocalReadMixin",
    "LocalWriteMixin",
    "LocalListMixin",
    "LocalDeleteMixin",
    "LocalMetadataMixin",
    "LocalCopyMixin",
    "LocalDirectoryMixin",
]
