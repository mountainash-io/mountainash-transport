"""HTTPWriteMixin — write operations for HTTP/HTTPS."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.exceptions import (
    AuthenticationError,
    PathNotFoundError,
    StorageError,
)
from mountainash_transport._core.http.errors import (
    HttpAuthenticationError,
    HttpForbiddenError,
    HttpNotFoundError,
    HttpTransportError,
)
from mountainash_transport.storage.protocols import StorageWriteProtocol


class HTTPWriteMixin(StorageWriteProtocol):
    """Write mixin for HTTP/HTTPS storage."""

    def write_from_bytes(self, path: str, data: bytes) -> None:
        """Upload bytes to a resource via HTTP PUT.

        Args:
            path: Full HTTP/HTTPS URL of the target resource.
            data: Bytes to upload.
        """
        engine = self._get_engine()  # type: ignore[attr-defined]
        try:
            engine.request("PUT", path, content=data)
        except HttpNotFoundError as exc:
            raise PathNotFoundError(path) from exc
        except (HttpAuthenticationError, HttpForbiddenError) as exc:
            raise AuthenticationError(path) from exc
        except HttpTransportError as exc:
            raise StorageError(str(exc)) from exc

    def write_from_stream(self, path: str, stream: t.BinaryIO) -> None:
        """Upload a binary stream to a resource via HTTP PUT.

        Args:
            path: Full HTTP/HTTPS URL of the target resource.
            stream: Binary stream to read and upload.
        """
        engine = self._get_engine()  # type: ignore[attr-defined]
        try:
            engine.request("PUT", path, stream=stream)
        except HttpNotFoundError as exc:
            raise PathNotFoundError(path) from exc
        except (HttpAuthenticationError, HttpForbiddenError) as exc:
            raise AuthenticationError(path) from exc
        except HttpTransportError as exc:
            raise StorageError(str(exc)) from exc
