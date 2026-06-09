"""Tests for HTTPStorageBackend — auth and profile integration."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import httpx
import pytest

from mountainash_utils_files.storage_backends.http import HTTPStorageBackend


@pytest.mark.unit
class TestHTTPBackendClientCreation:
    def test_bare_client_when_no_profile(self):
        backend = HTTPStorageBackend(None)
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
        backend = HTTPStorageBackend(profile)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            backend._get_client()
            mock_client.assert_called_once_with(**expected_kwargs)

    def test_client_cached_after_first_call(self):
        backend = HTTPStorageBackend(None)
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
        auth_profile = TokenAuth(TOKEN=SecretStr("tok"))
        backend = get_storage_backend(
            CONST_STORAGE_PROVIDER_TYPE.HTTP, None, auth_profile=auth_profile,
        )
        assert backend.auth_profile is auth_profile

    def test_auth_stored_on_all_backends(self):
        """All backends accept and store auth via the unified constructor."""
        from mountainash_auth_client import TokenAuth
        from pydantic import SecretStr
        auth_profile = TokenAuth(TOKEN=SecretStr("tok"))
        backend = get_storage_backend(
            CONST_STORAGE_PROVIDER_TYPE.S3, None, auth_profile=auth_profile,
        )
        # S3 backend stores auth but doesn't use it for client creation.
        assert backend.auth_profile is auth_profile


from mountainash_auth_client import NoAuth, TokenAuth, PasswordAuth
from pydantic import SecretStr


@pytest.mark.unit
class TestHTTPBackendAuthPrecedence:
    def test_direct_auth_creates_headers(self):
        auth_profile = TokenAuth(TOKEN=SecretStr("direct"))
        backend = HTTPStorageBackend(None, auth_profile=auth_profile)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock()
            backend._get_client()
            call_kwargs = mock_client.call_args[1]
            assert call_kwargs["headers"]["Authorization"] == "Bearer direct"

    def test_auth_flows_through_profile_adapter(self):
        """When a profile is present, auth is forwarded to to_handler_kwargs."""
        profile = MagicMock()
        auth_profile = TokenAuth(TOKEN=SecretStr("new"))
        # Simulate adapter producing kwargs with auth already resolved.
        profile.to_handler_kwargs.return_value = {
            "timeout": httpx.Timeout(connect=5.0, read=15.0, write=60.0, pool=5.0),
            "follow_redirects": True,
            "verify": True,
            "headers": {"Authorization": "Bearer new", "X-Custom": "keep"},
        }
        backend = HTTPStorageBackend(profile, auth_profile=auth_profile)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock()
            backend._get_client()
            # Verify auth was passed through to to_handler_kwargs.
            profile.to_handler_kwargs.assert_called_once_with(auth_profile=auth_profile)
            call_kwargs = mock_client.call_args[1]
            assert call_kwargs["headers"]["Authorization"] == "Bearer new"
            assert call_kwargs["headers"]["X-Custom"] == "keep"
            assert "timeout" in call_kwargs

    def test_noauth_flows_through_profile_adapter(self):
        """NoAuth is forwarded to profile adapter which strips Authorization."""
        profile = MagicMock()
        profile.to_handler_kwargs.return_value = {
            "headers": {"X-Custom": "keep"},
        }
        backend = HTTPStorageBackend(profile, auth_profile=NoAuth())
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock()
            backend._get_client()
            profile.to_handler_kwargs.assert_called_once_with(auth_profile=NoAuth())
            call_kwargs = mock_client.call_args[1]
            assert "Authorization" not in call_kwargs.get("headers", {})
            assert call_kwargs["headers"]["X-Custom"] == "keep"

    def test_profile_only_no_auth(self):
        profile = MagicMock()
        profile.to_handler_kwargs.return_value = {
            "headers": {"Authorization": "Bearer profonly"},
        }
        backend = HTTPStorageBackend(profile)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock()
            backend._get_client()
            profile.to_handler_kwargs.assert_called_once_with(auth_profile=None)
            call_kwargs = mock_client.call_args[1]
            assert call_kwargs["headers"]["Authorization"] == "Bearer profonly"

    def test_password_auth_direct(self):
        import base64
        auth_profile = PasswordAuth(USERNAME="user", PASSWORD=SecretStr("pass"))
        backend = HTTPStorageBackend(None, auth_profile=auth_profile)
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
        auth_profile = TokenAuth(TOKEN=SecretStr("facadetok"))
        facade = StorageFacade.from_path("https://example.com/file.txt", auth_profile=auth_profile)
        assert facade._backend.auth_profile is auth_profile

    def test_from_path_without_auth(self):
        facade = StorageFacade.from_path("https://example.com/file.txt")
        assert facade._backend.auth_profile is None

    def test_non_http_provider_with_auth_accepted(self):
        """All backends accept auth via the unified constructor signature."""
        auth_profile = TokenAuth(TOKEN=SecretStr("tok"))
        # S3 backend accepts auth without error (stores but doesn't use it).
        facade = StorageFacade(
            provider_type=CONST_STORAGE_PROVIDER_TYPE.S3,
            storage_profile=None,
            auth_profile=auth_profile,
        )
        assert facade._backend.auth_profile is auth_profile
