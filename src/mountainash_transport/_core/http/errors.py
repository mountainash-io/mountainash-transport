"""HTTP transport error hierarchy.

These exceptions are independent of the StorageError hierarchy in _core/exceptions.py.
Consumers (e.g. the HTTP storage backend) are responsible for mapping HTTP errors
to storage errors where needed.

Hierarchy
---------
HttpTransportError (base)
├── HttpResponseError        status_code, headers, url, method
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

import re
import typing as t

from mountainash_transport._core.safe_display import safe_location

# Response headers an error may carry. Location-valued ones are shown in display form,
# WWW-Authenticate as its auth-scheme names only, the rest verbatim (server-defined tokens).
_SAFE_HEADERS = frozenset({
    "accept-ranges", "content-encoding", "content-length", "content-location",
    "content-range", "content-type", "date", "etag", "last-modified", "location",
    "retry-after", "www-authenticate",
})
_URL_HEADERS = frozenset({"location", "content-location"})
_TOKEN_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&'*+-.^_`|~"
)


_HAS_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")


def _auth_schemes(value: str) -> str:
    """Auth-scheme names of a WWW-Authenticate value, in order; parameters are dropped.

    One linear pass: a scheme is the first token at the start or after a comma that is
    not followed by ``=``; quoted strings are skipped whole.
    """
    schemes: list[str] = []
    i, n = 0, len(value)
    expect_scheme = True
    while i < n:
        char = value[i]
        if char == ",":
            expect_scheme = True
            i += 1
            continue
        if char in " \t":
            i += 1
            continue
        start = i
        while i < n and value[i] not in " \t=,\"":
            i += 1
        token = value[start:i]
        while i < n and value[i] in " \t":
            i += 1
        if i < n and value[i] == "=":
            # parameter (or token68 padding): skip '='s, then a quoted or bare value
            while i < n and value[i] == "=":
                i += 1
            while i < n and value[i] in " \t":
                i += 1
            if i < n and value[i] == '"':
                i += 1
                while i < n and value[i] != '"':
                    i += 2 if value[i] == "\\" else 1
                i += 1
            else:
                while i < n and value[i] != ",":
                    i += 1
            expect_scheme = False
        elif token:
            if expect_scheme and all(c in _TOKEN_CHARS for c in token):
                schemes.append(token)
            expect_scheme = False
        elif i < n and value[i] == '"':
            i += 1
            while i < n and value[i] != '"':
                i += 2 if value[i] == "\\" else 1
            i += 1
        else:
            i += 1
    return ", ".join(schemes)


def _location_header(value: str, base: t.Optional[str]) -> str:
    """Display form of a Location-style value, resolved against *base* when one is known."""
    from urllib.parse import urljoin

    value = value.strip()
    if _HAS_SCHEME.match(value):
        # Absolute: safe_location needs no valid host to drop userinfo, query and fragment.
        return safe_location(value)
    if base is not None:
        try:
            return safe_location(urljoin(base, value))
        except ValueError:
            pass
    # No base (or unparseable): a reference shows only its path, never userinfo/query/fragment.
    if value.startswith("//"):
        end = min((i for i in (value.find(c, 2) for c in "/?#") if i != -1), default=len(value))
        value = "//" + value[2:end].rpartition("@")[2] + value[end:]
    return value[: min((i for i in (value.find(c) for c in "?#") if i != -1), default=len(value))]


def _safe_headers(headers: t.Mapping[str, str], base: t.Optional[str] = None) -> dict[str, str]:
    safe: dict[str, str] = {}
    for name, value in headers.items():
        key = name.lower()
        if key not in _SAFE_HEADERS:
            continue
        if key in _URL_HEADERS:
            safe[key] = _location_header(value, base)
        elif key == "www-authenticate":
            safe[key] = _auth_schemes(value)
        else:
            safe[key] = value
    return safe


class HttpTransportError(Exception):
    """Base class for all HTTP transport exceptions.

    Transport builds every message from a location's display form, a fixed
    category and an exception class name (W8 safe-location display).
    """


class HttpResponseError(HttpTransportError):
    """Raised when the server returns an error HTTP response.

    Parameters
    ----------
    message:
        Human-readable description of the error.
    status_code:
        The HTTP status code received.
    headers:
        Response headers as a mapping, reduced to an allow-list of safe headers;
        Location and Content-Location are resolved against ``url`` and shown in display
        form, WWW-Authenticate keeps only its auth-scheme names. The body is deliberately
        not carried.
    url:
        The request URL; stored in display form and used to resolve relative Location values.
    method:
        The HTTP method used (GET, POST, etc.).
    """

    def __init__(
        self,
        message: str = "",
        *,
        status_code: t.Optional[int] = None,
        headers: t.Optional[t.Mapping[str, str]] = None,
        url: t.Optional[str] = None,
        method: t.Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.headers = _safe_headers(headers, url) if headers is not None else None
        self.url = safe_location(url) if url is not None else None
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
        url: t.Optional[str] = None,
        method: t.Optional[str] = None,
        retry_after: t.Optional[float] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status_code,
            headers=headers,
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


TRUSTED_ERRORS: tuple[type[HttpTransportError], ...] = (
    HttpTransportError,
    HttpResponseError,
    HttpClientError,
    HttpNotFoundError,
    HttpAuthenticationError,
    HttpForbiddenError,
    HttpRateLimitError,
    HttpConflictError,
    HttpServerError,
    HttpBadGatewayError,
    HttpServiceUnavailableError,
    HttpGatewayTimeoutError,
    HttpConnectionError,
    HttpTimeoutError,
    HttpRedirectError,
    HttpProtocolError,
    HttpRequestError,
    HttpDecodeError,
)
