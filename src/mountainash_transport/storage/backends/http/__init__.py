"""HTTP/HTTPS storage backend — read, write, and metadata via httpx."""
from __future__ import annotations

import httpx

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.exceptions import StorageConnectionError
from mountainash_transport.storage.registry import register_storage_backend
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol

# from ._helpers import _raise_for_status
from .http_metadata import HTTPMetadataMixin
from .http_read import HTTPReadMixin
from .http_write import HTTPWriteMixin


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.HTTP)
class HTTPStorageBackend(HTTPReadMixin, HTTPWriteMixin, HTTPMetadataMixin):
    """HTTP/HTTPS storage backend.

    Implements StorageReadProtocol, StorageWriteProtocol,
    and StorageMetadataProtocol using httpx.
    """

    def __init__(
        self,
        storage_profile: StorageProfileProtocol | None = None,
        *,
        connection=None,
    ) -> None:
        self._connection = connection
        self.storage_profile = storage_profile

    def _get_client(self) -> httpx.Client:
        if self._connection is not None and self._connection.client is not None:
            return self._connection.client
        raise StorageConnectionError(
            "HTTPStorageBackend requires a connection — use create_connection()"
        )


__all__ = [
    "HTTPStorageBackend",
    "HTTPReadMixin",
    "HTTPWriteMixin",
    "HTTPMetadataMixin",
]
