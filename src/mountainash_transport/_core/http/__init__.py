"""HTTP transport foundation — error hierarchy and shared client utilities."""

import typing as _t

if _t.TYPE_CHECKING:
    from .engine import HttpRequestEngine

from .errors import (
    HttpTransportError,
    HttpResponseError,
    HttpClientError,
    HttpServerError,
    HttpNotFoundError,
    HttpAuthenticationError,
    HttpForbiddenError,
    HttpRateLimitError,
    HttpConflictError,
    HttpBadGatewayError,
    HttpServiceUnavailableError,
    HttpGatewayTimeoutError,
    HttpConnectionError,
    HttpTimeoutError,
    HttpRedirectError,
    HttpProtocolError,
    HttpRequestError,
    HttpDecodeError,
    map_status_to_error,
)
from .policy import (
    RetryPolicy,
    TimeoutPolicy,
    RedirectPolicy,
    RequestPolicy,
    SAFE_METHODS,
    IDEMPOTENT_METHODS,
)
from .response import HttpResponse, HttpStreamResponse


def __getattr__(name: str) -> _t.Any:
    if name != "HttpRequestEngine":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        from .engine import HttpRequestEngine
    except ImportError as exc:
        from mountainash_transport._core.extras import raise_for_missing_extra
        raise_for_missing_extra("HttpRequestEngine", "http", exc)
    return HttpRequestEngine


__all__ = [
    "HttpRequestEngine",
    # Errors
    "HttpTransportError",
    "HttpResponseError",
    "HttpClientError",
    "HttpServerError",
    "HttpNotFoundError",
    "HttpAuthenticationError",
    "HttpForbiddenError",
    "HttpRateLimitError",
    "HttpConflictError",
    "HttpBadGatewayError",
    "HttpServiceUnavailableError",
    "HttpGatewayTimeoutError",
    "HttpConnectionError",
    "HttpTimeoutError",
    "HttpRedirectError",
    "HttpProtocolError",
    "HttpRequestError",
    "HttpDecodeError",
    "map_status_to_error",
    # Policies
    "RetryPolicy",
    "TimeoutPolicy",
    "RedirectPolicy",
    "RequestPolicy",
    "SAFE_METHODS",
    "IDEMPOTENT_METHODS",
    # Responses
    "HttpResponse",
    "HttpStreamResponse",
]
