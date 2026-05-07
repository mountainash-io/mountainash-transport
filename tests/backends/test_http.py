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
from mountainash_utils_files.storage_protocols import (
    StorageConnectionProtocol,
    StorageCopyProtocol,
    StorageDeleteProtocol,
    StorageDirectoryProtocol,
    StorageListProtocol,
    StorageMetadataProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
)


def _transport(handler):
    return httpx.MockTransport(handler)


def _make_backend(transport: httpx.MockTransport):
    import mountainash_utils_files.storage_backends  # noqa: F401
    from mountainash_utils_files.storage_backends.http import HTTPStorageBackend
    backend = HTTPStorageBackend(auth_params=None)
    backend._client = httpx.Client(transport=transport)
    return backend


class TestProtocolConformance:
    @pytest.fixture()
    def backend(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"ok")
        return _make_backend(_transport(_handler))

    def test_implements_read_protocol(self, backend):
        assert isinstance(backend, StorageReadProtocol)

    def test_implements_write_protocol(self, backend):
        assert isinstance(backend, StorageWriteProtocol)

    def test_implements_metadata_protocol(self, backend):
        assert isinstance(backend, StorageMetadataProtocol)

    def test_does_not_implement_list(self, backend):
        assert not isinstance(backend, StorageListProtocol)

    def test_does_not_implement_delete(self, backend):
        assert not isinstance(backend, StorageDeleteProtocol)

    def test_does_not_implement_copy(self, backend):
        assert not isinstance(backend, StorageCopyProtocol)

    def test_does_not_implement_directory(self, backend):
        assert not isinstance(backend, StorageDirectoryProtocol)

    def test_does_not_implement_connection(self, backend):
        assert not isinstance(backend, StorageConnectionProtocol)


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
