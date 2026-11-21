"""write_from_stream reads the caller's stream in bounded chunks on every backend (#4)."""
from __future__ import annotations

import hashlib
import io
import threading
import typing as t
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import mountainash_transport.storage.backends  # noqa: F401
from mountainash_transport._core.constants import DEFAULT_CHUNK_SIZE
from mountainash_transport.storage.backends.local import LocalStorageBackend
from mountainash_transport.storage.backends.s3 import S3StorageBackend

PAYLOAD = bytes(range(256)) * (64 * DEFAULT_CHUNK_SIZE // 256)  # 4 MiB
S3_PART = 8 * 1024 * 1024  # boto3's default multipart chunk: its read bound


class GuardedSource(io.RawIOBase):
    """Serves PAYLOAD; refuses unbounded reads while data remains; records the largest single read."""

    def __init__(self, seekable: bool) -> None:
        self._data = io.BytesIO(PAYLOAD)
        self._seekable = seekable
        self.largest = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return self._seekable

    def read(self, size: int | None = -1) -> bytes:
        if size is None or size < 0:
            if self._data.tell() < len(PAYLOAD):
                raise AssertionError("unbounded read() of the caller's stream")
            return b""  # draining an exhausted stream holds nothing
        self.largest = max(self.largest, size)
        return self._data.read(size)

    def readinto(self, buffer: t.Any) -> int:
        chunk = self.read(len(buffer))
        buffer[: len(chunk)] = chunk
        return len(chunk)

    def seek(self, offset: int, whence: int = 0) -> int:
        if not self._seekable:
            raise io.UnsupportedOperation("seek")
        return self._data.seek(offset, whence)

    def tell(self) -> int:
        if not self._seekable:
            raise io.UnsupportedOperation("tell")
        return self._data.tell()


@pytest.fixture(scope="module")
def http_sink() -> t.Iterator[tuple[str, list[str]]]:
    digests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_PUT(self) -> None:
            digest = hashlib.sha256()
            if self.headers.get("Transfer-Encoding") == "chunked":
                while size := int(self.rfile.readline().strip(), 16):
                    digest.update(self.rfile.read(size))
                    self.rfile.readline()
                self.rfile.readline()
            else:
                remaining = int(self.headers["Content-Length"])
                while remaining:
                    chunk = self.rfile.read(min(remaining, DEFAULT_CHUNK_SIZE))
                    digest.update(chunk)
                    remaining -= len(chunk)
            digests.append(digest.hexdigest())
            self.send_response(201)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args: t.Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/upload.bin", digests
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="module")
def sftp_connection(tmp_path_factory: pytest.TempPathFactory) -> t.Iterator[t.Any]:
    from connections.tunnel_rig import DirectorySFTPTarget
    from mountainash_auth_client import PasswordAuthProfile
    from mountainash_transport import create_connection
    from mountainash_transport.settings.storage.profiles import SFTPStorageProfile

    server = DirectorySFTPTarget()
    known = tmp_path_factory.mktemp("sftp") / "known_hosts"
    known.write_text(server.known_hosts_line("127.0.0.1"))
    profile = SFTPStorageProfile(HOST="127.0.0.1", PORT=server.port, USERNAME="u",
                                 KNOWN_HOSTS_FILE=str(known), LOOK_FOR_KEYS=False, ALLOW_AGENT=False)
    connection = create_connection(profile, PasswordAuthProfile(USERNAME="u", PASSWORD="p")).connect()
    yield connection
    connection.disconnect()
    server.close()


def _s3_backend() -> tuple[S3StorageBackend, t.Any, list[bytes]]:
    import boto3
    from botocore.stub import Stubber

    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="k", aws_secret_access_key="s")
    received: list[bytes] = []
    client.meta.events.register(
        "before-parameter-build.s3.PutObject",
        lambda params, **_: received.append(params["Body"].read()),
    )
    stub = Stubber(client)
    stub.add_response("put_object", {}, None)
    stub.activate()
    backend = S3StorageBackend(None)
    backend._client = client
    return backend, stub, received


@pytest.mark.parametrize("seekable", [True, False], ids=["seekable", "non_seekable"])
@pytest.mark.parametrize("backend_name", ["local", "sftp", "http", "s3"])
def test_write_stream_reads_in_bounded_chunks(
    backend_name: str, seekable: bool, tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    source = GuardedSource(seekable)
    if backend_name == "local":
        target = tmp_path / "upload.bin"
        LocalStorageBackend().write_from_stream(str(target), t.cast(t.BinaryIO, source))
        assert target.read_bytes() == PAYLOAD
        bound = DEFAULT_CHUNK_SIZE
    elif backend_name == "sftp":
        from mountainash_transport.storage.backends.sftp import SFTPStorageBackend

        target = tmp_path / "upload.bin"
        backend = SFTPStorageBackend(connection=request.getfixturevalue("sftp_connection"))
        backend.write_from_stream(str(target), t.cast(t.BinaryIO, source))
        assert target.read_bytes() == PAYLOAD
        bound = DEFAULT_CHUNK_SIZE
    elif backend_name == "http":
        import httpx
        from mountainash_transport._core.http.engine import HttpRequestEngine
        from mountainash_transport.storage.backends.http import HTTPStorageBackend

        url, digests = request.getfixturevalue("http_sink")
        digests.clear()
        with httpx.Client() as client:
            HTTPStorageBackend(engine=HttpRequestEngine(client)).write_from_stream(url, t.cast(t.BinaryIO, source))
        assert digests == [hashlib.sha256(PAYLOAD).hexdigest()]
        bound = DEFAULT_CHUNK_SIZE
    else:
        backend, stub, received = _s3_backend()
        backend.write_from_stream("s3://b/k", t.cast(t.BinaryIO, source))
        stub.assert_no_pending_responses()
        assert received == [PAYLOAD]
        bound = S3_PART
    assert 0 < source.largest <= bound
