"""HTTPConnection — leaf connection creating an authenticated httpx.Client."""
from __future__ import annotations

import typing as t
from types import TracebackType

from typing_extensions import Self

import httpx

from mountainash_transport.connections.errors import (
    ConnectionTimeoutError,
    TransportConnectionError,
)
from .._core.protocols import ConnectionProtocol

class HTTPConnection(ConnectionProtocol):
    """Creates an authenticated httpx.Client from connect kwargs + auth strategy."""

    def __init__(self, connect_kwargs: dict[str, t.Any]) -> None:
        self._connect_kwargs = connect_kwargs
        self._client: httpx.Client | None = None

    def connect(self) -> Self:
        self.disconnect()
        kwargs = dict(self._connect_kwargs)
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
        client, self._client = self._client, None
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                raise TransportConnectionError(f"Failed to close HTTP client: {exc}") from exc

    @property
    def client(self) -> httpx.Client | None:
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None,
        exc_value: BaseException | None, traceback: TracebackType | None,
    ) -> None:
        try:
            self.disconnect()
        except BaseException as cleanup:
            if exc_value is None:
                raise
            exc_value.add_note(f"Connection cleanup also failed: {cleanup!r}")
            for note in getattr(cleanup, "__notes__", ()):
                exc_value.add_note(note)
