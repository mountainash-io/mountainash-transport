"""Tests for HTTPSettings — HTTP/HTTPS provider settings."""
from __future__ import annotations

import pytest

from mountainash_auth_client import NoAuth, PasswordAuth, TokenAuth
from pydantic import SecretStr

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE


def _make(**overrides):
    """Return an HTTPSettings with minimal required fields."""
    from mountainash_utils_files.settings.providers.http_settings import HTTPSettings

    kwargs = {
        "PROVIDER_TYPE": CONST_STORAGE_PROVIDER_TYPE.HTTP,
        "auth": NoAuth(),
    }
    kwargs.update(overrides)
    return HTTPSettings(**kwargs)


@pytest.mark.unit
class TestHTTPSettingsConstruction:
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
        from mountainash_utils_files.settings.providers.http_settings import HTTP_SPEC
        assert HTTP_SPEC.name == "http"

    def test_descriptor_provider_type(self):
        from mountainash_utils_files.settings.providers.http_settings import HTTP_SPEC
        assert HTTP_SPEC.provider_type == CONST_STORAGE_PROVIDER_TYPE.HTTP

    def test_descriptor_sdk_is_httpx(self):
        from mountainash_utils_files.settings.providers.http_settings import HTTP_SPEC
        assert HTTP_SPEC.sdk_package == "httpx"

    def test_descriptor_not_read_only(self):
        from mountainash_utils_files.settings.providers.http_settings import HTTP_SPEC
        assert HTTP_SPEC.read_only is False

    def test_descriptor_no_multipart(self):
        from mountainash_utils_files.settings.providers.http_settings import HTTP_SPEC
        assert HTTP_SPEC.supports_multipart is False


@pytest.mark.unit
class TestHTTPHandlerKwargs:
    def test_noauth_kwargs(self):
        s = _make()
        kw = s.to_handler_kwargs()
        assert kw["follow_redirects"] is True
        assert kw["max_redirects"] == 10
        assert kw["verify"] is True
        assert "Authorization" not in kw.get("headers", {})

    def test_token_auth_produces_bearer_header(self):
        s = _make(auth=TokenAuth(token=SecretStr("mytoken")))
        kw = s.to_handler_kwargs()
        assert kw["headers"]["Authorization"] == "Bearer mytoken"

    def test_password_auth_produces_basic_header(self):
        import base64
        s = _make(auth=PasswordAuth(username="user", password=SecretStr("pass")))
        kw = s.to_handler_kwargs()
        expected = "Basic " + base64.b64encode(b"user:pass").decode()
        assert kw["headers"]["Authorization"] == expected

    def test_timeout_object_in_kwargs(self):
        import httpx
        s = _make(TIMEOUT_CONNECT=2.0, TIMEOUT_READ=5.0, TIMEOUT_WRITE=10.0)
        kw = s.to_handler_kwargs()
        timeout = kw["timeout"]
        assert isinstance(timeout, httpx.Timeout)
        assert timeout.connect == 2.0
        assert timeout.read == 5.0
        assert timeout.write == 10.0

    def test_custom_headers_merged_with_auth(self):
        s = _make(
            HEADERS={"X-Custom": "value"},
            auth=TokenAuth(token=SecretStr("tok")),
        )
        kw = s.to_handler_kwargs()
        assert kw["headers"]["X-Custom"] == "value"
        assert kw["headers"]["Authorization"] == "Bearer tok"


@pytest.mark.unit
class TestResolveAuthHeaders:
    """Direct tests for _resolve_auth_headers — covers OAuth2 types."""

    def test_noauth_returns_empty(self):
        from mountainash_utils_files.settings.adapters.http import _resolve_auth_headers
        from mountainash_auth_client import NoAuth
        assert _resolve_auth_headers(NoAuth()) == {}

    def test_oauth2_with_token(self):
        from mountainash_utils_files.settings.adapters.http import _resolve_auth_headers
        from mountainash_auth_client import OAuth2Auth
        auth = OAuth2Auth(token=SecretStr("oauthtoken"))
        assert _resolve_auth_headers(auth) == {"Authorization": "Bearer oauthtoken"}

    def test_oauth2_without_token(self):
        from mountainash_utils_files.settings.adapters.http import _resolve_auth_headers
        from mountainash_auth_client import OAuth2Auth
        auth = OAuth2Auth(client_id="id", client_secret=SecretStr("secret"))
        assert _resolve_auth_headers(auth) == {}

    def test_oauth2_authcode_with_access_token(self):
        from mountainash_utils_files.settings.adapters.http import _resolve_auth_headers
        from mountainash_auth_client import OAuth2AuthCodeAuth
        auth = OAuth2AuthCodeAuth(
            client_id="id",
            client_secret=SecretStr("secret"),
            access_token=SecretStr("myaccess"),
        )
        assert _resolve_auth_headers(auth) == {"Authorization": "Bearer myaccess"}

    def test_oauth2_authcode_without_access_token(self):
        from mountainash_utils_files.settings.adapters.http import _resolve_auth_headers
        from mountainash_auth_client import OAuth2AuthCodeAuth
        auth = OAuth2AuthCodeAuth(
            client_id="id",
            client_secret=SecretStr("secret"),
        )
        assert _resolve_auth_headers(auth) == {}

    def test_none_returns_empty(self):
        from mountainash_utils_files.settings.adapters.http import _resolve_auth_headers
        assert _resolve_auth_headers(None) == {}
