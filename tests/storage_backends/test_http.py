"""Tests for the HTTPStorageBackend."""
from __future__ import annotations

import io

import httpx
import pytest

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.exceptions import (
    AuthenticationError,
    PathNotFoundError,
    StorageConnectionError,
    StorageError,
)
def _transport(handler):
    return httpx.MockTransport(handler)


def _make_backend(transport: httpx.MockTransport):
    import mountainash_utils_files.storage_backends  # noqa: F401
    from mountainash_utils_files.storage_backends.http import HTTPStorageBackend
    backend = HTTPStorageBackend(None)
    backend._client = httpx.Client(transport=transport)
    return backend


class TestReadToBytes:
    def test_returns_response_body(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            return httpx.Response(200, content=b"hello world")
        backend = _make_backend(_transport(_handler))
        assert backend.read_to_bytes("https://example.com/file.txt") == b"hello world"

    def test_404_raises_path_not_found(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)
        backend = _make_backend(_transport(_handler))
        with pytest.raises(PathNotFoundError):
            backend.read_to_bytes("https://example.com/missing")

    def test_401_raises_authentication_error(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401)
        backend = _make_backend(_transport(_handler))
        with pytest.raises(AuthenticationError):
            backend.read_to_bytes("https://example.com/secret")

    def test_500_raises_storage_error(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)
        backend = _make_backend(_transport(_handler))
        with pytest.raises(StorageError):
            backend.read_to_bytes("https://example.com/error")


class TestReadToStream:
    def test_returns_readable_stream(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"stream data")
        backend = _make_backend(_transport(_handler))
        stream = backend.read_to_stream("https://example.com/file.txt")
        assert stream.read() == b"stream data"


class TestWriteFromBytes:
    def test_sends_put_with_body(self):
        captured: dict[str, bytes] = {}
        def _handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "PUT"
            captured["body"] = request.content
            return httpx.Response(200)
        backend = _make_backend(_transport(_handler))
        backend.write_from_bytes("https://example.com/upload", b"payload")
        assert captured["body"] == b"payload"

    def test_404_on_put_raises_path_not_found(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)
        backend = _make_backend(_transport(_handler))
        with pytest.raises(PathNotFoundError):
            backend.write_from_bytes("https://example.com/no-bucket", b"data")


class TestWriteFromStream:
    def test_sends_put_with_stream_content(self):
        captured: dict[str, bytes] = {}
        def _handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "PUT"
            captured["body"] = request.content
            return httpx.Response(200)
        backend = _make_backend(_transport(_handler))
        backend.write_from_stream("https://example.com/upload", io.BytesIO(b"streamed"))
        assert captured["body"] == b"streamed"


class TestPathExists:
    def test_2xx_returns_true(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "HEAD"
            return httpx.Response(200)
        backend = _make_backend(_transport(_handler))
        assert backend.path_exists("https://example.com/file") is True

    def test_404_returns_false(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)
        backend = _make_backend(_transport(_handler))
        assert backend.path_exists("https://example.com/missing") is False

    def test_500_raises(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)
        backend = _make_backend(_transport(_handler))
        with pytest.raises(StorageError):
            backend.path_exists("https://example.com/error")


class TestGetMetadata:
    def test_builds_file_metadata_from_headers(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={
                    "Content-Length": "1234",
                    "Content-Type": "text/plain",
                    "Last-Modified": "Wed, 07 May 2026 12:00:00 GMT",
                    "ETag": '"abc123"',
                },
            )
        backend = _make_backend(_transport(_handler))
        meta = backend.get_metadata("https://example.com/data.txt")
        assert meta.filename == "data.txt"
        assert meta.size == 1234
        assert meta.etag == '"abc123"'
        assert meta.source == "http"


class TestGetSize:
    def test_returns_content_length(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"Content-Length": "5678"})
        backend = _make_backend(_transport(_handler))
        assert backend.get_size("https://example.com/file") == 5678

    def test_missing_content_length_returns_zero(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200)
        backend = _make_backend(_transport(_handler))
        assert backend.get_size("https://example.com/file") == 0


class TestRegistration:
    def test_http_provider_registered(self):
        import mountainash_utils_files.storage_backends  # noqa: F401
        from mountainash_utils_files.storage_registry import get_registered_backends
        backends = get_registered_backends()
        assert CONST_STORAGE_PROVIDER_TYPE.HTTP in backends


# ---------------------------------------------------------------------------
# Auth + profile integration
# ---------------------------------------------------------------------------

from unittest.mock import patch, MagicMock

from mountainash_auth_client import NoAuth, TokenAuth, PasswordAuth
from pydantic import SecretStr

from mountainash_utils_files.storage_backends.http import HTTPStorageBackend


class TestHTTPBackendClientCreation:
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
        profile = MagicMock()
        profile.to_handler_kwargs.return_value = {}
        backend = HTTPStorageBackend(profile)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            c1 = backend._get_client()
            c2 = backend._get_client()
            assert c1 is c2
            mock_client.assert_called_once()


class TestHTTPBackendAuthPrecedence:
    def test_auth_flows_through_profile_adapter(self):
        profile = MagicMock()
        auth_profile = TokenAuth(TOKEN=SecretStr("new"))
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
            profile.to_handler_kwargs.assert_called_once_with(auth_profile=auth_profile)
            call_kwargs = mock_client.call_args[1]
            assert call_kwargs["headers"]["Authorization"] == "Bearer new"
            assert call_kwargs["headers"]["X-Custom"] == "keep"

    def test_noauth_flows_through_profile_adapter(self):
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


class TestRegistryAuthForwarding:
    def test_auth_forwarded_to_http_backend(self):
        from mountainash_utils_files.storage_registry.registry import get_storage_backend
        auth_profile = TokenAuth(TOKEN=SecretStr("tok"))
        backend = get_storage_backend(
            CONST_STORAGE_PROVIDER_TYPE.HTTP, None, auth_profile=auth_profile,
        )
        assert backend.auth_profile is auth_profile

    def test_auth_stored_on_all_backends(self):
        from mountainash_utils_files.storage_registry.registry import get_storage_backend
        auth_profile = TokenAuth(TOKEN=SecretStr("tok"))
        backend = get_storage_backend(
            CONST_STORAGE_PROVIDER_TYPE.S3, None, auth_profile=auth_profile,
        )
        assert backend.auth_profile is auth_profile


class TestFacadeAuthParam:
    def test_from_path_passes_auth_to_backend(self):
        from mountainash_utils_files.storage_facade.facade import StorageFacade
        auth_profile = TokenAuth(TOKEN=SecretStr("facadetok"))
        facade = StorageFacade.from_path("https://example.com/file.txt", auth_profile=auth_profile)
        assert facade._backend.auth_profile is auth_profile

    def test_from_path_without_auth(self):
        from mountainash_utils_files.storage_facade.facade import StorageFacade
        facade = StorageFacade.from_path("https://example.com/file.txt")
        assert facade._backend.auth_profile is None
