"""Ranged-read conformance across S3, HTTP and SFTP using range-honouring fakes (Local uses the native file)."""
from __future__ import annotations

import io
import re
import typing as t
from unittest.mock import MagicMock

import httpx
import pytest
from botocore.exceptions import ClientError

from mountainash_transport._core.exceptions import ObjectChangedError, PathNotFoundError
from mountainash_transport._core.http.engine import HttpRequestEngine
from mountainash_transport._core.ranged_io import RangedReader, RangePolicy

DATA = bytes(range(256)) * 400  # 102_400 bytes


class _Store:
    """Mutable object store shared by the fakes: data + version tag."""

    def __init__(self) -> None:
        self.data = DATA
        self.etag = '"v1"'
        self.fetched = 0

    def change(self) -> None:
        self.data = DATA[::-1]
        self.etag = '"v2"'


def _client_error(code: str, status: int) -> ClientError:
    return ClientError({"Error": {"Code": code}, "ResponseMetadata": {
        "HTTPStatusCode": status, "RequestId": "", "HostId": "",
        "HTTPHeaders": {}, "RetryAttempts": 0,
    }}, "GetObject")


def _s3_backend(store: _Store, tmp_path) -> t.Any:
    from mountainash_transport.storage.backends.s3 import S3StorageBackend

    client = MagicMock()

    def head_object(Bucket: str, Key: str) -> dict:
        if Key == "missing":
            raise _client_error("404", 404)
        return {"ContentLength": len(store.data), "ETag": store.etag}

    def get_object(Bucket: str, Key: str, Range: str | None = None, IfMatch: str | None = None) -> dict:
        if Range is None:
            return {"Body": io.BytesIO(store.data)}
        if IfMatch is not None and IfMatch != store.etag:
            raise _client_error("PreconditionFailed", 412)
        m = re.fullmatch(r"bytes=(\d+)-(\d+)", Range or "")
        assert m, "ranged path must send Range"
        s, e = int(m[1]), int(m[2]) + 1
        store.fetched += e - s
        return {"Body": io.BytesIO(store.data[s:e]), "ContentRange": f"bytes {s}-{e-1}/{len(store.data)}"}

    client.head_object.side_effect = head_object
    client.get_object.side_effect = get_object
    backend = S3StorageBackend(None)
    backend._client = client
    return backend, "s3://b/k", "s3://b/missing"


def _http_backend(store: _Store, tmp_path) -> t.Any:
    from mountainash_transport.storage.backends.http import HTTPStorageBackend

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/missing":
            return httpx.Response(404)
        if "range" not in request.headers:
            return httpx.Response(200, content=store.data)
        assert request.headers.get("accept-encoding") == "identity"
        if "if-match" in request.headers and request.headers["if-match"] != store.etag:
            return httpx.Response(412)
        m = re.fullmatch(r"bytes=(\d+)-(\d+)", request.headers.get("range", ""))
        assert m
        s, e = int(m[1]), min(int(m[2]), len(store.data) - 1) + 1
        store.fetched += e - s
        return httpx.Response(
            206, content=store.data[s:e],
            headers={"Content-Range": f"bytes {s}-{e-1}/{len(store.data)}", "ETag": store.etag},
        )

    engine = HttpRequestEngine(httpx.Client(transport=httpx.MockTransport(handler)))
    return HTTPStorageBackend(None, engine=engine), "https://h/obj", "https://h/missing"


def _sftp_backend(store: _Store, tmp_path) -> t.Any:
    from mountainash_transport.storage.backends.sftp import SFTPStorageBackend

    class _File:
        def __init__(self) -> None:
            self.pos = 0
        def stat(self):  # noqa: ANN202
            return MagicMock(st_size=len(store.data))
        def seek(self, p: int) -> None:
            self.pos = p
        def read(self, n: int) -> bytes:
            out = store.data[self.pos:self.pos + n]
            store.fetched += len(out)
            self.pos += len(out)
            return out
        def close(self) -> None:
            pass

    client = MagicMock()

    def open_(path: str, mode: str = "rb") -> _File:
        if path == "/missing":
            raise FileNotFoundError(path)
        return _File()

    client.open.side_effect = open_
    backend = SFTPStorageBackend(None)
    backend._get_client = lambda: client  # type: ignore[method-assign]
    return backend, "/obj", "/missing"


BACKENDS = {"s3": _s3_backend, "http": _http_backend, "sftp": _sftp_backend}


@pytest.fixture(params=sorted(BACKENDS))
def case(request, tmp_path):
    store = _Store()
    backend, path, missing = BACKENDS[request.param](store, tmp_path)
    return request.param, store, backend, path, missing


def _open(backend, path) -> RangedReader:
    return RangedReader(backend.open_ranged(path), RangePolicy(cache="none"))


def test_tail_and_interior_bytes(case) -> None:
    _, store, backend, path, _ = case
    with _open(backend, path) as h:
        h.seek(-8, io.SEEK_END)
        assert h.read(8) == DATA[-8:]
        h.seek(50_000)
        assert h.read(1000) == DATA[50_000:51_000]


def test_bytes_fetched_are_bounded(case) -> None:
    _, store, backend, path, _ = case
    with _open(backend, path) as h:
        h.seek(-8, io.SEEK_END)
        h.read(8)
    assert store.fetched <= 8 + 1  # HTTP probe fetches 1 byte


def test_missing_object_raises_path_not_found(case) -> None:
    _, _, backend, _, missing = case
    with pytest.raises(PathNotFoundError):
        backend.open_ranged(missing)


def test_object_change_detected(case) -> None:
    name, store, backend, path, _ = case
    if name == "sftp":
        pytest.skip("no version token on SFTP (documented limitation)")
    h = _open(backend, path)
    store.change()
    with pytest.raises(ObjectChangedError):
        h.read(10)
    h.close()


@pytest.mark.parametrize("access", ["sequential", "random", "buffered"])
def test_facade_modes_across_backends(case, access: str) -> None:
    from mountainash_transport import StorageFacade
    from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE

    _, _, backend, path, _ = case
    facade = StorageFacade.for_local()
    facade._backend = backend
    facade._provider_type = CONST_STORAGE_PROVIDER_TYPE.HTTP
    with pytest.raises(RuntimeError, match="consumer"):
        with facade.read_stream(path, access=access) as stream:  # type: ignore[arg-type]
            assert stream.seekable() is (access != "sequential")
            assert stream.read(3) == DATA[:3]
            if access != "sequential":
                stream.seek(-8, io.SEEK_END)
                assert stream.read() == DATA[-8:]
            raise RuntimeError("consumer")
    assert stream.closed