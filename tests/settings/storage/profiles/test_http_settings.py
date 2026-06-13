"""Tests for HTTPStorageProfile — HTTP/HTTPS provider settings."""
from __future__ import annotations

import pytest

from mountainash_auth_client import NoAuthProfile
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE


def _make(**overrides):
    """Return an HTTPStorageProfile with minimal required fields."""
    from mountainash_transport.settings.storage.profiles import HTTPStorageProfile

    kwargs = {
        "PROVIDER_TYPE": CONST_STORAGE_PROVIDER_TYPE.HTTP,
        "auth": NoAuthProfile(),
    }
    kwargs.update(overrides)
    return HTTPStorageProfile(**kwargs)


@pytest.mark.unit
class TestHTTPStorageProfileConstruction:
    def test_defaults(self):
        s = _make()
        assert s.TIMEOUT_CONNECT == 10.0
        assert s.TIMEOUT_READ == 30.0
        assert s.TIMEOUT_WRITE == 60.0
        assert s.FOLLOW_REDIRECTS is True
        assert s.MAX_REDIRECTS == 10
        assert s.VERIFY_SSL is True

    def test_custom_timeouts(self):
        s = _make(TIMEOUT_CONNECT=5.0, TIMEOUT_READ=15.0, TIMEOUT_WRITE=120.0)
        assert s.TIMEOUT_CONNECT == 5.0
        assert s.TIMEOUT_READ == 15.0
        assert s.TIMEOUT_WRITE == 120.0

    def test_custom_headers_none_default(self):
        s = _make()
        assert s.HEADERS is None


@pytest.mark.unit
class TestHTTPDescriptor:
    def test_descriptor_name(self):
        from mountainash_transport.settings.storage.profiles.http_storage_profile import HTTP_SPEC
        assert HTTP_SPEC.name == "http"

    def test_descriptor_provider_type(self):
        from mountainash_transport.settings.storage.profiles.http_storage_profile import HTTP_SPEC
        assert HTTP_SPEC.provider_type == CONST_STORAGE_PROVIDER_TYPE.HTTP

    def test_descriptor_sdk_is_httpx(self):
        from mountainash_transport.settings.storage.profiles.http_storage_profile import HTTP_SPEC
        assert HTTP_SPEC.sdk_package == "httpx"

    def test_descriptor_not_read_only(self):
        from mountainash_transport.settings.storage.profiles.http_storage_profile import HTTP_SPEC
        assert HTTP_SPEC.read_only is False

    def test_descriptor_no_multipart(self):
        from mountainash_transport.settings.storage.profiles.http_storage_profile import HTTP_SPEC
        assert HTTP_SPEC.supports_multipart is False


@pytest.mark.unit
class TestHTTPHandlerKwargs:
    def test_noauth_kwargs(self):
        s = _make()
        kw = s.to_handler_kwargs()
        assert kw["follow_redirects"] is True
        assert kw["max_redirects"] == 10
        assert kw["verify"] is True
        # No auth headers — auth is handled by the strategy layer.
        assert "Authorization" not in kw.get("headers", {})

    def test_timeout_object_in_kwargs(self):
        import httpx
        s = _make(TIMEOUT_CONNECT=2.0, TIMEOUT_READ=5.0, TIMEOUT_WRITE=10.0)
        kw = s.to_handler_kwargs()
        timeout = kw["timeout"]
        assert isinstance(timeout, httpx.Timeout)
        assert timeout.connect == 2.0
        assert timeout.read == 5.0
        assert timeout.write == 10.0

    def test_custom_headers_forwarded(self):
        s = _make(HEADERS={"X-Custom": "value"})
        kw = s.to_handler_kwargs()
        assert kw["headers"]["X-Custom"] == "value"

    def test_no_headers_key_when_empty(self):
        s = _make()
        kw = s.to_handler_kwargs()
        assert "headers" not in kw
