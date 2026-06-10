"""HTTPReadMixin — read operations for HTTP/HTTPS."""
from __future__ import annotations

import io
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
from mountainash_transport.storage.protocols import StorageReadProtocol


class HTTPReadMixin(StorageReadProtocol):
    """Read mixin for HTTP/HTTPS storage."""

    def read_to_bytes(self, path: str) -> bytes:
        """Download a resource and return its contents as bytes.

        Args:
            path: Full HTTP/HTTPS URL of the resource.

        Returns:
            Response body as bytes.
        """
        engine = self._get_engine()  # type: ignore[attr-defined]
        try:
            response = engine.request("GET", path)
            return response.content
        except HttpNotFoundError as exc:
            raise PathNotFoundError(path) from exc
        except (HttpAuthenticationError, HttpForbiddenError) as exc:
            raise AuthenticationError(path) from exc
        except HttpTransportError as exc:
            raise StorageError(str(exc)) from exc

    def read_to_stream(self, path: str) -> t.BinaryIO:
        """Download a resource and return a binary stream.

        Args:
            path: Full HTTP/HTTPS URL of the resource.

        Returns:
            A :class:`io.BytesIO` stream containing the response body.
        """
        engine = self._get_engine()  # type: ignore[attr-defined]
        try:
            response = engine.request("GET", path)
            return io.BytesIO(response.content)
        except HttpNotFoundError as exc:
            raise PathNotFoundError(path) from exc
        except (HttpAuthenticationError, HttpForbiddenError) as exc:
            raise AuthenticationError(path) from exc
        except HttpTransportError as exc:
            raise StorageError(str(exc)) from exc
