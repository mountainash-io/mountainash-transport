"""Native streams retain lazy consumption, error mapping and owned closure."""
from __future__ import annotations

import gzip
import io
import typing as t
from unittest.mock import MagicMock

import httpx
import pytest

from mountainash_transport._core.exceptions import StorageError
from mountainash_transport._core.http.engine import HttpRequestEngine
from mountainash_transport._core.transforms import Gzip
from mountainash_transport.storage.backends.http import HTTPStorageBackend
from mountainash_transport.storage.backends.s3 import S3StorageBackend
from mountainash_transport.storage.backends.sftp import SFTPStorageBackend


class Body(io.BytesIO):
    def read(self, size: int | None = -1) -> bytes:
        assert size is not None and size >= 0, "backend must not drain the object"
        return super().read(size)


@pytest.mark.parametrize("provider", ["s3", "sftp"])
def test_native_sequential_lifecycle(provider: str) -> None:
    body = Body(gzip.compress(b"hello world"))
    client = MagicMock()
    if provider == "s3":
        backend: t.Any = S3StorageBackend(None)
        client.get_object.return_value = {"Body": body}
        backend._client = client
    else:
        backend = SFTPStorageBackend(None)
        client.open.return_value = body
        backend._get_client = lambda: client
    with backend.read_to_stream("bucket/key") as source:
        assert not source.seekable()
        with Gzip().unwrap(source) as decoded:
            assert not decoded.seekable()
            assert decoded.read() == b"hello world"
    assert body.closed


def test_http_mid_body_error_is_storage_error() -> None:
    closed = []

    class Dropping(httpx.SyncByteStream):
        def __iter__(self):
            yield b"abc"
            raise httpx.ReadError("dropped")

        def close(self) -> None:
            closed.append(True)

    engine = HttpRequestEngine(httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, stream=Dropping()),
    )))
    backend = HTTPStorageBackend(None, engine=engine)
    with pytest.raises(StorageError, match="dropped"):
        with backend.read_to_stream("https://h/f") as source:
            source.read()
    assert closed
