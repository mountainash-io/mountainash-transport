"""HTTP/HTTPS storage backend — read, write, and metadata via HttpRequestEngine."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.exceptions import StorageConnectionError
from mountainash_transport._core.http.policy import RequestPolicy
from mountainash_transport.storage.registry import register_storage_backend
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol

from .http_metadata import HTTPMetadataMixin
from .http_read import HTTPReadMixin
from .http_write import HTTPWriteMixin

if t.TYPE_CHECKING:
    from mountainash_transport._core.http.auth_protocol import AuthStrategy
    from mountainash_transport._core.http.engine import HttpRequestEngine


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.HTTP)
class HTTPStorageBackend(HTTPReadMixin, HTTPWriteMixin, HTTPMetadataMixin):
    """HTTP/HTTPS storage backend.

    Implements StorageReadProtocol, StorageWriteProtocol,
    and StorageMetadataProtocol using HttpRequestEngine.
    """

    def __init__(
        self,
        storage_profile: StorageProfileProtocol | None = None,
        *,
        connection: t.Any = None,
        auth_strategy: AuthStrategy | None = None,
        policy: RequestPolicy | None = None,
        engine: HttpRequestEngine | None = None,
        location_check: t.Callable[[str], None] | None = None,
    ) -> None:
        if engine is not None and location_check is not None:
            raise ValueError(
                "location_check cannot be combined with an injected engine; "
                "construct the engine with location_check"
            )
        self._connection = connection
        self.storage_profile = storage_profile
        self._engine: HttpRequestEngine | None = None

        if engine is not None:
            self._engine = engine
        elif connection is not None:
            client = connection.client
            if client is None:
                raise StorageConnectionError(
                    "HTTP backend requires a connected connection"
                )
            from mountainash_transport._core.http.engine import HttpRequestEngine

            self._engine = HttpRequestEngine(
                client=client,
                auth_strategy=auth_strategy,
                policy=policy or RequestPolicy(),
                location_check=location_check,
            )

    def _get_engine(self) -> HttpRequestEngine:
        if self._engine is None:
            raise StorageConnectionError(
                "HTTP backend requires a connection or engine"
            )
        return self._engine


__all__ = [
    "HTTPStorageBackend",
    "HTTPReadMixin",
    "HTTPWriteMixin",
    "HTTPMetadataMixin",
]
