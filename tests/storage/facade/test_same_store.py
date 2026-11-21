"""Store equivalence decides when copy_between uses the store's native copy (#43)."""
from __future__ import annotations

import os
import threading
import typing as t
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from mountainash_auth_client import IAMAuthProfile

from mountainash_transport import StorageFacade, copy_between
from mountainash_transport.location import LocationPolicy
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as P
from mountainash_transport.settings.storage.profiles import LocalStorageProfile, S3StorageProfile

OLD = 1_000_000_000  # an mtime only a metadata-preserving (native) copy keeps


def _local(root: Path | None = None, policy: LocationPolicy | None = None) -> StorageFacade:
    profile = LocalStorageProfile(ROOT_PATH=str(root)) if root else LocalStorageProfile()
    return StorageFacade(P.LOCAL, profile, policy=policy)


def _source_file(tmp_path: Path) -> Path:
    source = tmp_path / "src.csv"
    source.write_bytes(b"region,total\n")
    os.utime(source, (OLD, OLD))
    return source


def test_equal_but_separate_local_profiles_copy_natively(tmp_path: Path) -> None:
    source = _source_file(tmp_path)
    with _local() as a, _local() as b:
        assert a.same_store(b)
        copy_between(str(source), str(tmp_path / "dst.csv"), a, b)
    assert os.stat(tmp_path / "dst.csv").st_mtime == OLD


@pytest.mark.parametrize("difference", ["root", "policy"])
def test_different_local_store_streams(tmp_path: Path, difference: str) -> None:
    source = _source_file(tmp_path)
    a = _local(tmp_path) if difference == "root" else _local()
    b = _local(tmp_path / "..") if difference == "root" else _local(policy=LocationPolicy(root=str(tmp_path)))
    with a, b:
        assert not a.same_store(b)
        copy_between(str(source), str(tmp_path / "dst.csv"), a, b)
    assert (tmp_path / "dst.csv").read_bytes() == b"region,total\n"
    assert os.stat(tmp_path / "dst.csv").st_mtime != OLD


def test_closed_facade_is_not_the_same_store() -> None:
    a, b = _local(), _local()
    b.close()
    with a:
        assert not a.same_store(b)


def test_different_provider_is_not_the_same_store(tmp_path: Path) -> None:
    with _local() as a, StorageFacade(P.HTTP) as b:
        assert not a.same_store(b)


@pytest.fixture(scope="module")
def s3_endpoint() -> t.Iterator[tuple[str, list[str]]]:
    """A loopback S3 endpoint holding one object; records the operations it serves."""
    ops: list[str] = []
    objects: dict[str, bytes] = {"/b/src.csv": b"region,total\n"}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _reply(self, status: int, body: bytes = b"", content_type: str = "application/xml") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("ETag", '"e"')
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_HEAD(self) -> None:
            ops.append("head")
            body = objects.get(self.path.split("?")[0])
            self.send_response(200 if body is not None else 404)
            self.send_header("Content-Length", str(len(body or b"")))
            self.send_header("ETag", '"e"')
            self.end_headers()

        def do_GET(self) -> None:
            ops.append("get")
            self._reply(200, objects[self.path.split("?")[0]], "application/octet-stream")

        def do_PUT(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length)
            source = self.headers.get("x-amz-copy-source")
            if source:
                ops.append("copy")
                objects[self.path.split("?")[0]] = objects["/" + source.lstrip("/").split("?")[0]]
                self._reply(200, b'<CopyObjectResult><ETag>"e"</ETag></CopyObjectResult>')
            else:
                ops.append("put")
                objects[self.path.split("?")[0]] = body
                self._reply(200)

        def log_message(self, *args: t.Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", ops
    server.shutdown()
    server.server_close()


def _s3(endpoint: str, secret: str = "s") -> StorageFacade:
    profile = S3StorageProfile(FLAVOR="minio", ENDPOINT_URL=endpoint, BUCKET="b")
    return StorageFacade(P.MINIO, profile, auth_profile=IAMAuthProfile(ACCESS_KEY_ID="k", SECRET_ACCESS_KEY=secret))


def test_equal_s3_profiles_copy_server_side(s3_endpoint: tuple[str, list[str]]) -> None:
    endpoint, ops = s3_endpoint
    ops.clear()
    with _s3(endpoint) as a, _s3(endpoint) as b:
        assert a.same_store(b)
        copy_between("minio://b/src.csv", "minio://b/dst.csv", a, b)
    assert "copy" in ops and "get" not in ops and "put" not in ops


def test_different_s3_credentials_stream_through(s3_endpoint: tuple[str, list[str]]) -> None:
    endpoint, ops = s3_endpoint
    ops.clear()
    with _s3(endpoint) as a, _s3(endpoint, secret="other") as b:
        assert not a.same_store(b)
        copy_between("minio://b/src.csv", "minio://b/dst2.csv", a, b)
    assert "copy" not in ops and "get" in ops and "put" in ops
