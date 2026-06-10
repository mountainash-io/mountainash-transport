"""HTTPReadMixin — read operations for HTTP/HTTPS."""
from __future__ import annotations

import io
import typing as t

import httpx

from mountainash_transport._core.exceptions import StorageConnectionError
from mountainash_transport.storage.protocols import StorageReadProtocol

from ._helpers import _raise_for_status


class HTTPReadMixin(StorageReadProtocol):
    """Read mixin for HTTP/HTTPS storage."""

    def read_to_bytes(self, path: str) -> bytes:
        """Download a resource and return its contents as bytes.

        Args:
            path: Full HTTP/HTTPS URL of the resource.

        Returns:
            Response body as bytes.
        """
        client = self._get_client()  # type: ignore[attr-defined]
        try:
            response = client.get(path)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout reading {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)
        return response.content

    def read_to_stream(self, path: str) -> t.BinaryIO:
        """Download a resource and return a binary stream.

        Args:
            path: Full HTTP/HTTPS URL of the resource.

        Returns:
            A :class:`io.BytesIO` stream containing the response body.
        """
        client = self._get_client()  # type: ignore[attr-defined]
        try:
            response = client.get(path)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout reading {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)
        return io.BytesIO(response.content)
