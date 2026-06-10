"""HTTP transport foundation — error hierarchy and shared client utilities."""

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
