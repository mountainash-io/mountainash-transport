"""Tests for HTTPStorageBackend — auth and profile integration."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import httpx
import pytest

from mountainash_utils_files.storage_backends.http import HTTPStorageBackend


@pytest.mark.unit
class TestHTTPBackendClientCreation:
    def test_bare_client_when_no_auth_params(self):
        backend = HTTPStorageBackend(auth_params=None)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            backend._get_client()
            mock_client.assert_called_once_with()

    def test_profile_kwargs_forwarded_to_client(self):
        profile = MagicMock()
        expected_kwargs = {
            "timeout": httpx.Timeout(connect=5.0, read=15.0, write=60.0, pool=5.0),
            "follow_redirects": True,
            "max_redirects": 10,
            "verify": True,
            "headers": {"Authorization": "Bearer tok123"},
        }
        profile.to_handler_kwargs.return_value = expected_kwargs
        backend = HTTPStorageBackend(auth_params=profile)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            backend._get_client()
            mock_client.assert_called_once_with(**expected_kwargs)

    def test_client_cached_after_first_call(self):
        backend = HTTPStorageBackend(auth_params=None)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            c1 = backend._get_client()
            c2 = backend._get_client()
            assert c1 is c2
            mock_client.assert_called_once()


from mountainash_utils_files.storage_registry.registry import get_storage_backend
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE


@pytest.mark.unit
class TestRegistryAuthForwarding:
    def test_auth_forwarded_to_http_backend(self):
        from mountainash_auth_client import TokenAuth
        from pydantic import SecretStr
        auth = TokenAuth(token=SecretStr("tok"))
        backend = get_storage_backend(
            CONST_STORAGE_PROVIDER_TYPE.HTTP, auth_params=None, auth=auth,
        )
        assert backend.auth is auth

    def test_auth_ignored_for_backend_without_auth_param(self):
        from mountainash_auth_client import TokenAuth
        from pydantic import SecretStr
        auth = TokenAuth(token=SecretStr("tok"))
        backend = get_storage_backend(
            CONST_STORAGE_PROVIDER_TYPE.S3, auth_params=None, auth=auth,
        )
        assert not hasattr(backend, "auth") or backend.auth is None


from mountainash_auth_client import NoAuth, TokenAuth, PasswordAuth
from pydantic import SecretStr


@pytest.mark.unit
class TestHTTPBackendAuthPrecedence:
    def test_direct_auth_creates_headers(self):
        auth = TokenAuth(token=SecretStr("direct"))
        backend = HTTPStorageBackend(auth_params=None, auth=auth)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock()
            backend._get_client()
            call_kwargs = mock_client.call_args[1]
            assert call_kwargs["headers"]["Authorization"] == "Bearer direct"

    def test_auth_overrides_profile_auth_header(self):
        profile = MagicMock()
        profile.to_handler_kwargs.return_value = {
            "timeout": httpx.Timeout(connect=5.0, read=15.0, write=60.0, pool=5.0),
            "follow_redirects": True,
            "verify": True,
            "headers": {"Authorization": "Bearer old", "X-Custom": "keep"},
        }
        auth = TokenAuth(token=SecretStr("new"))
        backend = HTTPStorageBackend(auth_params=profile, auth=auth)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock()
            backend._get_client()
            call_kwargs = mock_client.call_args[1]
            assert call_kwargs["headers"]["Authorization"] == "Bearer new"
            assert call_kwargs["headers"]["X-Custom"] == "keep"
            assert "timeout" in call_kwargs

    def test_noauth_strips_profile_authorization(self):
        profile = MagicMock()
        profile.to_handler_kwargs.return_value = {
            "headers": {"Authorization": "Bearer fromprofile", "X-Custom": "keep"},
        }
        backend = HTTPStorageBackend(auth_params=profile, auth=NoAuth())
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock()
            backend._get_client()
            call_kwargs = mock_client.call_args[1]
            assert "Authorization" not in call_kwargs.get("headers", {})
            assert call_kwargs["headers"]["X-Custom"] == "keep"

    def test_profile_only_no_auth(self):
        profile = MagicMock()
        profile.to_handler_kwargs.return_value = {
            "headers": {"Authorization": "Bearer profonly"},
        }
        backend = HTTPStorageBackend(auth_params=profile)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock()
            backend._get_client()
            call_kwargs = mock_client.call_args[1]
            assert call_kwargs["headers"]["Authorization"] == "Bearer profonly"

    def test_password_auth_direct(self):
        import base64
        auth = PasswordAuth(username="user", password=SecretStr("pass"))
        backend = HTTPStorageBackend(auth_params=None, auth=auth)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock()
            backend._get_client()
            call_kwargs = mock_client.call_args[1]
            expected = "Basic " + base64.b64encode(b"user:pass").decode()
            assert call_kwargs["headers"]["Authorization"] == expected


from mountainash_utils_files.storage_facade.facade import StorageFacade


@pytest.mark.unit
class TestFacadeAuthParam:
    def test_from_path_passes_auth_to_backend(self):
        auth = TokenAuth(token=SecretStr("facadetok"))
        facade = StorageFacade.from_path("https://example.com/file.txt", auth=auth)
        assert facade._backend.auth is auth

    def test_from_path_without_auth(self):
        facade = StorageFacade.from_path("https://example.com/file.txt")
        assert facade._backend.auth is None

    def test_non_http_provider_with_auth_raises(self):
        auth = TokenAuth(token=SecretStr("tok"))
        with pytest.raises(ValueError, match="auth= is not supported"):
            StorageFacade(
                provider_type=CONST_STORAGE_PROVIDER_TYPE.S3,
                auth_params=None,
                auth=auth,
            )
