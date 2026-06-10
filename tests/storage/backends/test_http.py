"""Tests for the HTTPStorageBackend."""
from __future__ import annotations

import io

import httpx
import pytest

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.exceptions import (
    AuthenticationError,
    PathNotFoundError,
    StorageConnectionError,
    StorageError,
)
from mountainash_transport._core.http.engine import HttpRequestEngine
from mountainash_transport._core.http.policy import RequestPolicy, RetryPolicy


def _transport(handler):
    return httpx.MockTransport(handler)


class _FakeConnection:
    """Minimal connection stub that wraps an httpx.Client with a mock transport."""
    def __init__(self, transport: httpx.MockTransport):
        self._client = httpx.Client(transport=transport)

    @property
    def client(self) -> httpx.Client:
        return self._client

    def connect(self):
        return self

    def disconnect(self):
        if self._client is not None:
            self._client.close()
        self._client = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None


def _make_backend(transport: httpx.MockTransport):
    import mountainash_transport.storage.backends  # noqa: F401
    from mountainash_transport.storage.backends.http import HTTPStorageBackend
    conn = _FakeConnection(transport)
    policy = RequestPolicy(retry=RetryPolicy(max_attempts=1, retry_on_transport=False))
    backend = HTTPStorageBackend(None, connection=conn, policy=policy)
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
    def test_get_metadata_returns_storage_entry(self):
        from mountainash_transport._core.dataclasses.storage_entry import StorageEntry

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
        assert isinstance(meta, StorageEntry)
        assert meta.name == "data.txt"
        assert meta.path == "https://example.com/data.txt"
        assert meta.size == 1234
        assert meta.etag == '"abc123"'
        assert meta.source == "http"
        assert meta.content_type == "text/plain"

    def test_get_metadata_with_content_md5(self):
        from mountainash_transport._core.dataclasses.storage_entry import StorageEntry

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={
                    "Content-Length": "512",
                    "Content-MD5": "abc123==",
                },
            )
        backend = _make_backend(_transport(_handler))
        meta = backend.get_metadata("https://example.com/file.txt")
        assert isinstance(meta, StorageEntry)
        assert meta.checksum == "abc123=="
        assert meta.checksum_algorithm == "MD5"

    def test_get_metadata_size_none_without_content_length(self):
        from mountainash_transport._core.dataclasses.storage_entry import StorageEntry

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200)
        backend = _make_backend(_transport(_handler))
        meta = backend.get_metadata("https://example.com/file.txt")
        assert isinstance(meta, StorageEntry)
        assert meta.size is None


class TestGetSize:
    def test_returns_content_length(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"Content-Length": "5678"})
        backend = _make_backend(_transport(_handler))
        assert backend.get_size("https://example.com/file") == 5678

    def test_missing_content_length_returns_none(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200)
        backend = _make_backend(_transport(_handler))
        assert backend.get_size("https://example.com/file") is None


class TestRegistration:
    def test_http_provider_registered(self):
        import mountainash_transport.storage.backends  # noqa: F401
        from mountainash_transport.storage.registry import get_registered_backends
        backends = get_registered_backends()
        assert CONST_STORAGE_PROVIDER_TYPE.HTTP in backends


# ---------------------------------------------------------------------------
# Auth + profile integration
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock

from mountainash_transport.storage.backends.http import HTTPStorageBackend


class TestHTTPBackendEngineCreation:
    def test_engine_created_from_connection(self):
        """_engine is an HttpRequestEngine when connection is provided."""
        mock_client = MagicMock()
        conn = MagicMock()
        conn.client = mock_client
        backend = HTTPStorageBackend(None, connection=conn)
        assert isinstance(backend._engine, HttpRequestEngine)

    def test_no_connection_raises(self):
        """_get_engine raises StorageConnectionError when no connection is provided."""
        backend = HTTPStorageBackend(None)
        with pytest.raises(StorageConnectionError, match="requires a connection"):
            backend._get_engine()

    def test_engine_injected_directly(self):
        """An engine passed directly is used as-is."""
        mock_engine = MagicMock(spec=HttpRequestEngine)
        backend = HTTPStorageBackend(None, engine=mock_engine)
        assert backend._get_engine() is mock_engine


class TestHTTPBackendProfileKwargs:
    def test_engine_comes_from_connection(self):
        """Backend creates engine from the injected connection's client."""
        mock_client = MagicMock()
        conn = MagicMock()
        conn.client = mock_client
        profile = MagicMock()
        backend = HTTPStorageBackend(profile, connection=conn)
        assert isinstance(backend._engine, HttpRequestEngine)
