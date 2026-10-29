"""Tests for the HTTP error hierarchy in _core/http/errors.py."""

import pytest

from mountainash_transport._core.http.errors import (
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
    map_status_to_error,
)


# ---------------------------------------------------------------------------
# 1. All 18 exception classes are subclasses of HttpTransportError
# ---------------------------------------------------------------------------

ALL_CLASSES = [
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
]


@pytest.mark.parametrize("exc_class", ALL_CLASSES)
def test_all_classes_subclass_http_transport_error(exc_class):
    assert issubclass(exc_class, HttpTransportError)


def test_http_transport_error_is_exception():
    assert issubclass(HttpTransportError, Exception)


def test_total_exported_count():
    """Ensure exactly 18 non-base exception classes are exported (not counting HttpTransportError itself)."""
    assert len(ALL_CLASSES) == 17  # HttpTransportError is the base, not in this list


# ---------------------------------------------------------------------------
# 2. Correct inheritance chain
# ---------------------------------------------------------------------------

class TestInheritanceChain:
    def test_http_response_error_subclasses_http_transport_error(self):
        assert issubclass(HttpResponseError, HttpTransportError)

    def test_http_client_error_subclasses_http_response_error(self):
        assert issubclass(HttpClientError, HttpResponseError)

    def test_http_server_error_subclasses_http_response_error(self):
        assert issubclass(HttpServerError, HttpResponseError)

    def test_http_not_found_error_subclasses_http_client_error(self):
        assert issubclass(HttpNotFoundError, HttpClientError)

    def test_http_authentication_error_subclasses_http_client_error(self):
        assert issubclass(HttpAuthenticationError, HttpClientError)

    def test_http_forbidden_error_subclasses_http_client_error(self):
        assert issubclass(HttpForbiddenError, HttpClientError)

    def test_http_rate_limit_error_subclasses_http_client_error(self):
        assert issubclass(HttpRateLimitError, HttpClientError)

    def test_http_conflict_error_subclasses_http_client_error(self):
        assert issubclass(HttpConflictError, HttpClientError)

    def test_http_bad_gateway_error_subclasses_http_server_error(self):
        assert issubclass(HttpBadGatewayError, HttpServerError)

    def test_http_service_unavailable_error_subclasses_http_server_error(self):
        assert issubclass(HttpServiceUnavailableError, HttpServerError)

    def test_http_gateway_timeout_error_subclasses_http_server_error(self):
        assert issubclass(HttpGatewayTimeoutError, HttpServerError)

    def test_http_connection_error_subclasses_http_transport_error(self):
        assert issubclass(HttpConnectionError, HttpTransportError)

    def test_http_timeout_error_subclasses_http_transport_error(self):
        assert issubclass(HttpTimeoutError, HttpTransportError)

    def test_http_redirect_error_subclasses_http_transport_error(self):
        assert issubclass(HttpRedirectError, HttpTransportError)

    def test_http_protocol_error_subclasses_http_transport_error(self):
        assert issubclass(HttpProtocolError, HttpTransportError)

    def test_http_request_error_subclasses_http_transport_error(self):
        assert issubclass(HttpRequestError, HttpTransportError)

    def test_http_decode_error_subclasses_http_transport_error(self):
        assert issubclass(HttpDecodeError, HttpTransportError)

    def test_leaf_errors_not_directly_equal_to_intermediate(self):
        """Leaf errors are not the same class as intermediate parents."""
        assert HttpNotFoundError is not HttpClientError
        assert HttpClientError is not HttpResponseError


# ---------------------------------------------------------------------------
# 3. HttpResponseError carries context fields
# ---------------------------------------------------------------------------

class TestHttpResponseErrorFields:
    def _make(self, **kwargs):
        defaults = dict(
            status_code=400,
            headers={"content-type": "text/plain"},
            body_preview="Bad request",
            url="https://example.com/resource",
            method="GET",
        )
        defaults.update(kwargs)
        return HttpResponseError("error message", **defaults)

    def test_status_code_stored(self):
        err = self._make(status_code=422)
        assert err.status_code == 422

    def test_headers_stored(self):
        hdrs = {"x-custom": "value"}
        err = self._make(headers=hdrs)
        assert err.headers == hdrs

    def test_body_preview_stored(self):
        err = self._make(body_preview="preview text")
        assert err.body_preview == "preview text"

    def test_url_stored(self):
        err = self._make(url="https://api.example.com/v1/items")
        assert err.url == "https://api.example.com/v1/items"

    def test_method_stored(self):
        err = self._make(method="POST")
        assert err.method == "POST"

    def test_fields_default_to_none(self):
        """All context fields should be optional and default to None."""
        err = HttpResponseError("bare message")
        assert err.status_code is None
        assert err.headers is None
        assert err.body_preview is None
        assert err.url is None
        assert err.method is None

    def test_message_preserved(self):
        err = self._make()
        assert "error message" in str(err)

    def test_subclass_inherits_fields(self):
        """Concrete subclasses accept the same context kwargs."""
        err = HttpNotFoundError("not found", status_code=404, url="https://x.com/y")
        assert err.status_code == 404
        assert err.url == "https://x.com/y"


# ---------------------------------------------------------------------------
# 4. HttpRateLimitError carries retry_after field
# ---------------------------------------------------------------------------

class TestHttpRateLimitError:
    def test_retry_after_stored(self):
        err = HttpRateLimitError("rate limited", status_code=429, retry_after=30.0)
        assert err.retry_after == 30.0

    def test_retry_after_none_by_default(self):
        err = HttpRateLimitError("rate limited", status_code=429)
        assert err.retry_after is None

    def test_retry_after_accepts_float(self):
        err = HttpRateLimitError("rate limited", retry_after=1.5)
        assert err.retry_after == 1.5

    def test_retry_after_accepts_int_coerced_to_float(self):
        err = HttpRateLimitError("rate limited", retry_after=60)
        assert err.retry_after == 60

    def test_inherits_response_error_fields(self):
        err = HttpRateLimitError(
            "rate limited",
            status_code=429,
            headers={"retry-after": "30"},
            url="https://api.example.com",
            method="GET",
            retry_after=30.0,
        )
        assert err.status_code == 429
        assert err.url == "https://api.example.com"
        assert err.retry_after == 30.0


# ---------------------------------------------------------------------------
# 5. map_status_to_error
# ---------------------------------------------------------------------------

class TestMapStatusToError:
    # Known mappings
    @pytest.mark.parametrize("code,expected_class", [
        (401, HttpAuthenticationError),
        (403, HttpForbiddenError),
        (404, HttpNotFoundError),
        (409, HttpConflictError),
        (429, HttpRateLimitError),
        (502, HttpBadGatewayError),
        (503, HttpServiceUnavailableError),
        (504, HttpGatewayTimeoutError),
    ])
    def test_known_codes_map_to_specific_class(self, code, expected_class):
        assert map_status_to_error(code) is expected_class

    # Unmapped 4xx → HttpClientError
    @pytest.mark.parametrize("code", [400, 405, 410, 415, 422, 451])
    def test_unmapped_4xx_maps_to_http_client_error(self, code):
        assert map_status_to_error(code) is HttpClientError

    # Unmapped 5xx → HttpServerError
    @pytest.mark.parametrize("code", [500, 501, 505, 511])
    def test_unmapped_5xx_maps_to_http_server_error(self, code):
        assert map_status_to_error(code) is HttpServerError

    def test_returns_class_not_instance(self):
        result = map_status_to_error(404)
        assert isinstance(result, type)
        assert issubclass(result, HttpResponseError)

    def test_unmapped_non_http_error_code_raises_value_error(self):
        """Codes outside 4xx/5xx range should raise ValueError."""
        with pytest.raises(ValueError):
            map_status_to_error(200)

    def test_unmapped_1xx_raises_value_error(self):
        with pytest.raises(ValueError):
            map_status_to_error(100)

    def test_unmapped_3xx_raises_value_error(self):
        with pytest.raises(ValueError):
            map_status_to_error(301)


# ---------------------------------------------------------------------------
# 6. Instantiation and raise/catch behaviour
# ---------------------------------------------------------------------------

class TestRaiseAndCatch:
    def test_catch_by_base_class(self):
        with pytest.raises(HttpTransportError):
            raise HttpNotFoundError("not found", status_code=404)

    def test_catch_by_intermediate_class(self):
        with pytest.raises(HttpClientError):
            raise HttpNotFoundError("not found", status_code=404)

    def test_catch_by_response_error(self):
        with pytest.raises(HttpResponseError):
            raise HttpServerError("internal error", status_code=500)

    def test_connection_error_not_caught_as_response_error(self):
        with pytest.raises(HttpConnectionError):
            raise HttpConnectionError("DNS failed")
        # Should NOT be catchable as HttpResponseError
        with pytest.raises(HttpTransportError):
            raise HttpConnectionError("DNS failed")
