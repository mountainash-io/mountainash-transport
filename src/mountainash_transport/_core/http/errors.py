"""HTTP transport error hierarchy.

These exceptions are independent of the StorageError hierarchy in _core/exceptions.py.
Consumers (e.g. the HTTP storage backend) are responsible for mapping HTTP errors
to storage errors where needed.

Hierarchy
---------
HttpTransportError (base)
├── HttpResponseError        status_code, headers, body_preview, url, method
│   ├── HttpClientError      4xx
│   │   ├── HttpNotFoundError            404
│   │   ├── HttpAuthenticationError      401
│   │   ├── HttpForbiddenError           403
│   │   ├── HttpRateLimitError           429  + retry_after: float | None
│   │   └── HttpConflictError            409
│   └── HttpServerError      5xx
│       ├── HttpBadGatewayError          502
│       ├── HttpServiceUnavailableError  503
│       └── HttpGatewayTimeoutError      504
├── HttpConnectionError      DNS, TCP, TLS, proxy
├── HttpTimeoutError         connect, read, write, pool
├── HttpRedirectError        unhandled 3xx, too many redirects
├── HttpProtocolError        HTTP/2 framing, decoding
├── HttpRequestError         invalid URL, unsupported protocol
└── HttpDecodeError          JSON parse, encoding errors
"""

from __future__ import annotations

import typing as t


class HttpTransportError(Exception):
    """Base class for all HTTP transport exceptions."""


class HttpResponseError(HttpTransportError):
    """Raised when the server returns an error HTTP response.

    Parameters
    ----------
    message:
        Human-readable description of the error.
    status_code:
        The HTTP status code received.
    headers:
        Response headers as a mapping.
    body_preview:
        A truncated preview of the response body (for logging/debugging).
    url:
        The request URL.
    method:
        The HTTP method used (GET, POST, etc.).
    """

    def __init__(
        self,
        message: str = "",
        *,
        status_code: t.Optional[int] = None,
        headers: t.Optional[t.Mapping[str, str]] = None,
        body_preview: t.Optional[str] = None,
        url: t.Optional[str] = None,
        method: t.Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.headers = headers
        self.body_preview = body_preview
        self.url = url
        self.method = method


class HttpClientError(HttpResponseError):
    """Raised for HTTP 4xx client errors."""


class HttpNotFoundError(HttpClientError):
    """Raised for HTTP 404 Not Found."""


class HttpAuthenticationError(HttpClientError):
    """Raised for HTTP 401 Unauthorized."""


class HttpForbiddenError(HttpClientError):
    """Raised for HTTP 403 Forbidden."""


class HttpRateLimitError(HttpClientError):
    """Raised for HTTP 429 Too Many Requests.

    Parameters
    ----------
    retry_after:
        Number of seconds to wait before retrying, if supplied by the server.
    """

    def __init__(
        self,
        message: str = "",
        *,
        status_code: t.Optional[int] = None,
        headers: t.Optional[t.Mapping[str, str]] = None,
        body_preview: t.Optional[str] = None,
        url: t.Optional[str] = None,
        method: t.Optional[str] = None,
        retry_after: t.Optional[float] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status_code,
            headers=headers,
            body_preview=body_preview,
            url=url,
            method=method,
        )
        self.retry_after = retry_after


class HttpConflictError(HttpClientError):
    """Raised for HTTP 409 Conflict."""


class HttpServerError(HttpResponseError):
    """Raised for HTTP 5xx server errors."""


class HttpBadGatewayError(HttpServerError):
    """Raised for HTTP 502 Bad Gateway."""


class HttpServiceUnavailableError(HttpServerError):
    """Raised for HTTP 503 Service Unavailable."""


class HttpGatewayTimeoutError(HttpServerError):
    """Raised for HTTP 504 Gateway Timeout."""


class HttpConnectionError(HttpTransportError):
    """Raised when a connection cannot be established (DNS, TCP, TLS, proxy)."""


class HttpTimeoutError(HttpTransportError):
    """Raised when a request times out (connect, read, write, or pool timeout)."""


class HttpRedirectError(HttpTransportError):
    """Raised for unhandled 3xx responses or too-many-redirects situations."""


class HttpProtocolError(HttpTransportError):
    """Raised for low-level HTTP protocol errors (e.g. HTTP/2 framing, decoding)."""


class HttpRequestError(HttpTransportError):
    """Raised when the request itself is invalid (invalid URL, unsupported scheme)."""


class HttpDecodeError(HttpTransportError):
    """Raised when a response body cannot be decoded (JSON parse error, encoding issues)."""


# ---------------------------------------------------------------------------
# Status code → error class mapping
# ---------------------------------------------------------------------------

_STATUS_MAP: dict[int, type[HttpResponseError]] = {
    401: HttpAuthenticationError,
    403: HttpForbiddenError,
    404: HttpNotFoundError,
    409: HttpConflictError,
    429: HttpRateLimitError,
    502: HttpBadGatewayError,
    503: HttpServiceUnavailableError,
    504: HttpGatewayTimeoutError,
}


def map_status_to_error(status_code: int) -> type[HttpResponseError]:
    """Return the most specific error class for the given HTTP status code.

    For exactly-known codes the specific subclass is returned.
    For other 4xx codes ``HttpClientError`` is returned.
    For other 5xx codes ``HttpServerError`` is returned.
    All other codes raise ``ValueError``.

    Parameters
    ----------
    status_code:
        An integer HTTP status code.

    Returns
    -------
    type[HttpResponseError]
        The error class (not an instance).

    Raises
    ------
    ValueError
        If the status code is not in the 4xx or 5xx range.
    """
    if status_code in _STATUS_MAP:
        return _STATUS_MAP[status_code]
    if 400 <= status_code < 500:
        return HttpClientError
    if 500 <= status_code < 600:
        return HttpServerError
    raise ValueError(
        f"status_code {status_code!r} is not a 4xx or 5xx error code; "
        "cannot map to an HttpResponseError subclass."
    )
