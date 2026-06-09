"""HTTPConnection — leaf connection creating an authenticated httpx.Client."""
from __future__ import annotations

import typing as t

from typing_extensions import Self

import httpx

from mountainash_transport._core.auth.strategies import AuthStrategy
from mountainash_transport.connections.errors import (
    ConnectionTimeoutError,
    TransportConnectionError,
)
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
from .._core.protocols import ConnectionProtocol

class HTTPConnection(ConnectionProtocol):
    """Creates an authenticated httpx.Client from profile config + auth strategy."""

    def __init__(
        self,
        profile: StorageProfileProtocol,
        auth_strategy: AuthStrategy,
    ) -> None:
        self._profile = profile
        self._auth_strategy = auth_strategy
        self._client: httpx.Client | None = None

    def connect(self) -> Self:
        kwargs = self._profile.to_handler_kwargs()
        kwargs = self._auth_strategy.apply(kwargs)
        try:
            self._client = httpx.Client(**kwargs)
        except httpx.TimeoutException as exc:
            raise ConnectionTimeoutError(
                f"Timeout creating HTTP client: {exc}"
            ) from exc
        except httpx.ConnectError as exc:
            raise TransportConnectionError(
                f"Connection failed: {exc}"
            ) from exc
        except Exception as exc:
            raise TransportConnectionError(
                f"Failed to create HTTP client: {exc}"
            ) from exc
        return self

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None

    @property
    def client(self) -> httpx.Client | None:
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: t.Any) -> None:
        self.disconnect()
