"""HTTP backend translation without changing engine retry or request policy."""
from __future__ import annotations

import contextlib
import typing as t

from mountainash_transport._core.exceptions import (
    AuthenticationError, ObjectChangedError, PathNotFoundError,
    PermissionDeniedError, StorageConnectionError, StorageError,
)
from mountainash_transport._core.redact import raise_redacted, redact_url
from mountainash_transport._core.http.errors import (
    HttpAuthenticationError, HttpClientError, HttpConnectionError,
    HttpForbiddenError, HttpNotFoundError, HttpRequestError,
    HttpTimeoutError, HttpTransportError,
)


def _map_error(exc: Exception, path: str) -> StorageError | None:
    import httpx

    path = redact_url(path)
    if isinstance(exc, (StorageError, HttpRequestError, httpx.InvalidURL,
                        httpx.UnsupportedProtocol, httpx.LocalProtocolError)):
        return None
    if isinstance(exc, HttpNotFoundError):
        return PathNotFoundError(path)
    if isinstance(exc, HttpAuthenticationError):
        return AuthenticationError(path)
    if isinstance(exc, HttpForbiddenError):
        return PermissionDeniedError(path)
    if isinstance(exc, HttpClientError) and exc.status_code == 412:
        return ObjectChangedError(path)
    if not isinstance(exc, (HttpTransportError, httpx.HTTPError, OSError)):
        return None
    # Classification follows the displayed cause chain; suppressed chains carry
    # none (raise_redacted drops them), and the engine already maps socket
    # failures to HttpConnectionError.
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (HttpConnectionError, HttpTimeoutError,
                                httpx.NetworkError, httpx.TimeoutException,
                                httpx.ProxyError, ConnectionError, TimeoutError)):
            return StorageConnectionError(f"{path}: {redact_url(str(exc))}")
        current = current.__cause__
    return StorageError(f"{path}: {redact_url(str(exc))}")


@contextlib.contextmanager
def _mapped(path: str) -> t.Iterator[None]:
    try:
        yield
    except Exception as exc:
        mapped = _map_error(exc, path)
        if mapped is None or mapped is exc:
            raise
        raise_redacted(mapped, exc)
