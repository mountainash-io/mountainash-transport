"""HTTPWriteMixin — write operations for HTTP/HTTPS."""
from __future__ import annotations

import typing as t

import httpx

from mountainash_transport._core.exceptions import StorageConnectionError
from mountainash_transport.storage.protocols import StorageWriteProtocol

from ._helpers import _raise_for_status


class HTTPWriteMixin(StorageWriteProtocol):
    """Write mixin for HTTP/HTTPS storage."""

    def write_from_bytes(self, path: str, data: bytes) -> None:
        """Upload bytes to a resource via HTTP PUT.

        Args:
            path: Full HTTP/HTTPS URL of the target resource.
            data: Bytes to upload.
        """
        client = self._get_client()  # type: ignore[attr-defined]
        try:
            response = client.put(path, content=data)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout writing {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)

    def write_from_stream(self, path: str, stream: t.BinaryIO) -> None:
        """Upload a binary stream to a resource via HTTP PUT.

        Args:
            path: Full HTTP/HTTPS URL of the target resource.
            stream: Binary stream to read and upload.
        """
        client = self._get_client()  # type: ignore[attr-defined]
        try:
            response = client.put(path, content=stream.read())
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout writing {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)
