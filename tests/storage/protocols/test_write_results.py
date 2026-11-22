"""Write-like operations return the destination's StorageEntry (#10 §3).

``WRITE_RESULT_FIELDS`` names the fields each backend fills for each operation.
The tests assert it against real results, and the file-operations chapter's
"What a write returns" table is checked against it, so neither can drift.
"""
from __future__ import annotations

import gzip
import io
import os
import threading
import typing as t
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from mountainash_auth_client import PasswordAuthProfile

from mountainash_transport import StorageEntry, StorageFacade, copy_between
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as P
from mountainash_transport._core.transforms import Gzip
from mountainash_transport.settings.storage.profiles import SFTPStorageProfile

# (backend, operation) -> fields that are always filled. Optional fields
# (etag/version_id where the store reports them) are asserted per backend.
WRITE_RESULT_FIELDS: dict[tuple[str, str], frozenset[str]] = {
    ("local", "write"): frozenset({"path", "name", "size", "last_modified"}),
    ("local", "copy"): frozenset({"path", "name", "size", "last_modified"}),
    ("local", "move"): frozenset({"path", "name", "size", "last_modified"}),
    ("sftp", "write"): frozenset({"path", "name", "size", "last_modified"}),
    ("sftp", "move"): frozenset({"path", "name", "size", "last_modified"}),
    ("s3", "write"): frozenset({"path", "name", "size", "etag"}),
    ("s3", "copy"): frozenset({"path", "name", "etag"}),
    ("http", "write"): frozenset({"path", "name", "size"}),
}
_FIELDS = ("path", "name", "size", "last_modified", "etag", "version_id")


def filled(entry: StorageEntry) -> frozenset[str]:
    return frozenset(f for f in _FIELDS if getattr(entry, f) not in (None, ""))


def assert_result(entry: StorageEntry, backend: str, op: str, metadata: StorageEntry) -> None:
    assert isinstance(entry, StorageEntry)
    assert WRITE_RESULT_FIELDS[(backend, op)] <= filled(entry)
    for field in WRITE_RESULT_FIELDS[(backend, op)] - {"last_modified"}:
        assert getattr(entry, field) == getattr(metadata, field), field
    if "last_modified" in WRITE_RESULT_FIELDS[(backend, op)]:
        assert entry.last_modified is not None and metadata.last_modified is not None
        assert abs((entry.last_modified - metadata.last_modified).total_seconds()) < 1


@pytest.fixture(params=["local", "sftp"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> t.Iterator[tuple[str, StorageFacade, Path, str]]:
    """Backend name, a facade, the real directory behind it, and the facade's path prefix for it."""
    root = tmp_path / "root"
    root.mkdir()
    if request.param == "local":
        with StorageFacade.for_local() as facade:
            yield "local", facade, root, str(root)
        return
    from connections.tunnel_rig import DirectorySFTPTarget

    server = DirectorySFTPTarget(root)
    known = tmp_path / "known_hosts"
    known.write_text(server.known_hosts_line("127.0.0.1"))
    profile = SFTPStorageProfile(HOST="127.0.0.1", PORT=server.port, USERNAME="u", KNOWN_HOSTS_FILE=str(known),
                                 LOOK_FOR_KEYS=False, ALLOW_AGENT=False)
    try:
        with StorageFacade(P.SFTP, profile, auth_profile=PasswordAuthProfile(USERNAME="u", PASSWORD="p")) as facade:
            yield "sftp", facade, root, ""
    finally:
        server.close()


def test_write_returns_the_written_file(store: tuple[str, StorageFacade, Path, str]) -> None:
    backend, facade, _root, prefix = store
    entry = facade.write(f"{prefix}/a.csv", b"region,total\n")
    assert entry.size == 13
    assert_result(entry, backend, "write", facade.metadata(f"{prefix}/a.csv"))


def test_write_stream_counts_only_bytes_after_the_start_offset(store: tuple[str, StorageFacade, Path, str]) -> None:
    backend, facade, root, prefix = store
    source = io.BytesIO(b"h" * 100 + b"payload")
    source.seek(100)
    entry = facade.write_stream(f"{prefix}/a.bin", source)
    assert entry.size == 7 == (root / "a.bin").stat().st_size
    assert_result(entry, backend, "write", facade.metadata(f"{prefix}/a.bin"))


def test_pipeline_write_over_a_pipe_reports_the_stored_encoded_size(
    store: tuple[str, StorageFacade, Path, str],
) -> None:
    backend, facade, root, prefix = store
    read_fd, write_fd = os.pipe()

    def feed() -> None:
        with os.fdopen(write_fd, "wb") as w:
            w.write(b"x" * 200_000)

    feeder = threading.Thread(target=feed)
    feeder.start()
    with os.fdopen(read_fd, "rb") as pipe:
        entry = facade.write_stream(f"{prefix}/a.gz", t.cast(t.BinaryIO, pipe), pipeline=Gzip())
    feeder.join()
    stored = (root / "a.gz").read_bytes()
    assert gzip.decompress(stored) == b"x" * 200_000
    assert entry.size == len(stored)
    assert_result(entry, backend, "write", facade.metadata(f"{prefix}/a.gz"))


def test_move_returns_the_destination(store: tuple[str, StorageFacade, Path, str]) -> None:
    backend, facade, root, prefix = store
    (root / "a.csv").write_bytes(b"abc")
    entry = facade.move(f"{prefix}/a.csv", f"{prefix}/b.csv")
    assert entry.size == 3
    assert_result(entry, backend, "move", facade.metadata(f"{prefix}/b.csv"))


def test_moving_a_dangling_relative_symlink_describes_the_link(store: tuple[str, StorageFacade, Path, str]) -> None:
    _backend, facade, root, prefix = store
    (root / "sub").mkdir()
    os.symlink("target-that-does-not-exist", root / "link")
    entry = facade.move(f"{prefix}/link", f"{prefix}/sub/link")
    assert os.path.islink(root / "sub" / "link")
    assert entry.name == "link"
    assert entry.size == len("target-that-does-not-exist")


def test_local_copy_returns_the_copy(tmp_path: Path) -> None:
    (tmp_path / "a.csv").write_bytes(b"abc")
    with StorageFacade.for_local() as facade:
        entry = facade.copy(str(tmp_path / "a.csv"), str(tmp_path / "b.csv"))
        assert_result(entry, "local", "copy", facade.metadata(str(tmp_path / "b.csv")))


def test_local_copy_into_a_directory_describes_the_file_inside_it(tmp_path: Path) -> None:
    (tmp_path / "a.csv").write_bytes(b"abc")
    (tmp_path / "out").mkdir()
    with StorageFacade.for_local() as facade:
        entry = facade.copy(str(tmp_path / "a.csv"), str(tmp_path / "out"))
        assert entry.path == str(tmp_path / "out" / "a.csv")
        assert entry.size == 3


@pytest.mark.parametrize("separate_roots", [False, True], ids=["native", "streamed"])
def test_copy_between_returns_the_destination(tmp_path: Path, separate_roots: bool) -> None:
    from mountainash_transport.settings.storage.profiles import LocalStorageProfile

    (tmp_path / "a.csv").write_bytes(b"abc")
    other = LocalStorageProfile(ROOT_PATH=str(tmp_path)) if separate_roots else LocalStorageProfile()
    with StorageFacade(P.LOCAL, LocalStorageProfile()) as source, StorageFacade(P.LOCAL, other) as destination:
        assert source.same_store(destination) is not separate_roots
        entry = copy_between(str(tmp_path / "a.csv"), str(tmp_path / "b.csv"), source, destination)
        assert_result(entry, "local", "copy", destination.metadata(str(tmp_path / "b.csv")))


class _HTTPStore(BaseHTTPRequestHandler):
    """PUT stores the body; paths containing "tagged" answer with ETag and Last-Modified.

    The first PUT to a path containing "flaky" gets a 503, so the engine resends the body.
    """

    protocol_version = "HTTP/1.1"
    bodies: t.ClassVar[dict[str, bytes]] = {}
    flaked: t.ClassVar[set[str]] = set()

    def _headers(self) -> None:
        if "tagged" in self.path:
            self.send_header("ETag", f'"v{len(self.bodies[self.path])}"')
            self.send_header("Last-Modified", "Sun, 22 Nov 2026 10:00:00 GMT")

    def do_PUT(self) -> None:
        if self.headers.get("Transfer-Encoding") == "chunked":
            body = b""
            while size := int(self.rfile.readline().strip(), 16):
                body += self.rfile.read(size)
                self.rfile.readline()
            self.rfile.readline()
        else:
            body = self.rfile.read(int(self.headers["Content-Length"]))
        if "flaky" in self.path and self.path not in self.flaked:
            self.flaked.add(self.path)
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.bodies[self.path] = body
        self.send_response(201)
        self._headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self) -> None:
        self.send_response(200)
        self._headers()
        self.send_header("Content-Length", str(len(self.bodies[self.path])))
        self.end_headers()

    def log_message(self, *args: t.Any) -> None:
        pass


@pytest.fixture
def http_store() -> t.Iterator[tuple[t.Any, str]]:
    import httpx

    from mountainash_transport._core.http.engine import HttpRequestEngine
    from mountainash_transport.storage.backends.http import HTTPStorageBackend

    _HTTPStore.bodies.clear()
    _HTTPStore.flaked.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _HTTPStore)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with httpx.Client() as client:
            yield HTTPStorageBackend(engine=HttpRequestEngine(client)), f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


class _OneShot(io.RawIOBase):
    """A non-seekable source."""

    def __init__(self, data: bytes) -> None:
        self._data = io.BytesIO(data)

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: t.Any) -> int:
        return self._data.readinto(buffer)


def test_http_write_reports_the_servers_etag_and_last_modified(http_store: tuple[t.Any, str]) -> None:
    backend, base = http_store
    entry = backend.write_from_bytes(f"{base}/tagged/a.csv", b"abc")
    assert entry.etag == '"v3"' and entry.last_modified is not None
    assert_result(entry, "http", "write", backend.get_metadata(f"{base}/tagged/a.csv"))
    assert entry.etag == backend.get_metadata(f"{base}/tagged/a.csv").etag


def test_http_write_without_validators_leaves_them_empty(http_store: tuple[t.Any, str]) -> None:
    backend, base = http_store
    entry = backend.write_from_bytes(f"{base}/plain/a.csv", b"abc")
    assert (entry.etag, entry.last_modified, entry.size) == ("", None, 3)
    assert_result(entry, "http", "write", backend.get_metadata(f"{base}/plain/a.csv"))


def test_http_resent_seekable_stream_counts_bytes_after_the_start_once(http_store: tuple[t.Any, str]) -> None:
    backend, base = http_store
    source = io.BytesIO(b"h" * 100 + b"payload")
    source.seek(100)
    entry = backend.write_from_stream(f"{base}/flaky/a.bin", source)
    assert _HTTPStore.bodies["/flaky/a.bin"] == b"payload"  # sent twice; stored once
    assert entry.size == 7


def test_http_non_seekable_stream_counts_the_bytes_sent(http_store: tuple[t.Any, str]) -> None:
    backend, base = http_store
    entry = backend.write_from_stream(f"{base}/plain/b.bin", t.cast(t.BinaryIO, _OneShot(b"x" * 70_000)))
    assert entry.size == 70_000 == len(_HTTPStore.bodies["/plain/b.bin"])


# --- S3 ---------------------------------------------------------------------


def _aws_chunked(raw: bytes) -> bytes:
    """Decode an aws-chunked body (botocore's trailing-checksum framing)."""
    out, rest = b"", raw
    while True:
        line, rest = rest.split(b"\r\n", 1)
        size = int(line.split(b";")[0], 16)
        if size == 0:
            return out
        out, rest = out + rest[:size], rest[size + 2:]


class _S3Store(BaseHTTPRequestHandler):
    """Path-style S3 PUT/copy/HEAD; every write makes a new version.

    Keys containing "flaky" fail their first PUT with 500, so botocore resends the body.
    """

    protocol_version = "HTTP/1.1"
    objects: t.ClassVar[dict[str, tuple[bytes, str]]] = {}
    flaked: t.ClassVar[set[str]] = set()
    lock = threading.Lock()
    counter = 0

    def _store(self, body: bytes) -> str:
        with self.lock:
            type(self).counter += 1
            version = f"v{type(self).counter}"
            self.objects[self.path] = (body, version)
        return version

    def _send(self, status: int, headers: dict[str, str], body: bytes = b"") -> None:
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self) -> None:
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        if "flaky" in self.path and self.path not in self.flaked:
            self.flaked.add(self.path)
            self._send(500, {}, b"<Error><Code>InternalError</Code></Error>")
            return
        if source := self.headers.get("x-amz-copy-source"):
            body = self.objects["/" + source.lstrip("/")][0]
            version = self._store(body)
            result = (f'<CopyObjectResult><ETag>"e-{version}"</ETag>'
                      f"<LastModified>2026-11-22T10:00:00.000Z</LastModified></CopyObjectResult>")
            self._send(200, {"x-amz-version-id": version}, result.encode())
            return
        body = _aws_chunked(raw) if "aws-chunked" in self.headers.get("Content-Encoding", "") else raw
        version = self._store(body)
        self._send(200, {"ETag": f'"e-{version}"', "x-amz-version-id": version})

    def do_HEAD(self) -> None:
        body, version = self.objects[self.path]
        self.send_response(200)
        self.send_header("ETag", f'"e-{version}"')
        self.send_header("x-amz-version-id", version)
        self.send_header("Last-Modified", "Sun, 22 Nov 2026 10:00:00 GMT")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

    def log_message(self, *args: t.Any) -> None:
        pass


@pytest.fixture
def s3_store() -> t.Iterator[StorageFacade]:
    """A real S3 (MinIO-flavor) facade talking to a local path-style S3 server."""
    from mountainash_auth_client import IAMAuthProfile

    from mountainash_transport.settings.storage.profiles import S3StorageProfile

    _S3Store.objects.clear()
    _S3Store.flaked.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _S3Store)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    profile = S3StorageProfile(FLAVOR="minio", ENDPOINT_URL=f"http://127.0.0.1:{server.server_address[1]}",
                               BUCKET="b", RETRY_MAX_ATTEMPTS=3)
    try:
        with StorageFacade(P.MINIO, profile,
                           auth_profile=IAMAuthProfile(ACCESS_KEY_ID="k", SECRET_ACCESS_KEY="s")) as facade:
            yield facade
    finally:
        server.shutdown()
        server.server_close()


def test_s3_write_returns_the_put_response(s3_store: StorageFacade) -> None:
    entry = s3_store.write("s3://b/a.csv", b"abc")
    assert entry.size == 3 and entry.version_id
    assert_result(entry, "s3", "write", s3_store.metadata("s3://b/a.csv"))
    assert entry.version_id == s3_store.metadata("s3://b/a.csv").version_id


def test_s3_seekable_stream_resent_after_an_error_counts_its_bytes_once(s3_store: StorageFacade) -> None:
    source = io.BytesIO(b"h" * 100 + b"payload")
    source.seek(100)
    entry = s3_store.write_stream("s3://b/flaky.bin", source)
    assert "/b/flaky.bin" in _S3Store.flaked  # the body really was sent twice
    assert _S3Store.objects["/b/flaky.bin"][0] == b"payload"
    assert entry.size == 7
    assert_result(entry, "s3", "write", s3_store.metadata("s3://b/flaky.bin"))


def test_s3_pipeline_write_over_a_pipe_reports_the_stored_encoded_size(s3_store: StorageFacade) -> None:
    read_fd, write_fd = os.pipe()

    def feed() -> None:
        with os.fdopen(write_fd, "wb") as w:
            w.write(b"x" * 200_000)

    feeder = threading.Thread(target=feed)
    feeder.start()
    with os.fdopen(read_fd, "rb") as pipe:
        entry = s3_store.write_stream("s3://b/a.gz", t.cast(t.BinaryIO, pipe), pipeline=Gzip())
    feeder.join()
    stored = _S3Store.objects["/b/a.gz"][0]
    assert gzip.decompress(stored) == b"x" * 200_000
    assert entry.size == len(stored)
    assert_result(entry, "s3", "write", s3_store.metadata("s3://b/a.gz"))


def test_s3_concurrent_writes_to_different_keys_get_their_own_versions(s3_store: StorageFacade) -> None:
    results: dict[str, StorageEntry] = {}

    def write(key: str) -> None:
        results[key] = s3_store.write_stream(f"s3://b/{key}", io.BytesIO(key.encode() * 1000))

    threads = [threading.Thread(target=write, args=(f"k{i}",)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(results) == 8
    for key, entry in results.items():
        assert entry.version_id == _S3Store.objects[f"/b/{key}"][1]


def test_s3_copy_returns_the_copy_object_result(s3_store: StorageFacade) -> None:
    s3_store.write("s3://b/a.csv", b"abc")
    entry = s3_store.copy("s3://b/a.csv", "s3://b/b.csv")
    assert entry.size is None  # CopyObject does not report it, and no HEAD is spent on it
    assert entry.version_id == _S3Store.objects["/b/b.csv"][1]
    assert_result(entry, "s3", "copy", s3_store.metadata("s3://b/b.csv"))


def test_s3_multipart_stream_returns_the_complete_multipart_upload_version() -> None:
    from types import SimpleNamespace

    import boto3
    from botocore.stub import Stubber

    from mountainash_transport.storage.backends.s3 import S3StorageBackend

    mib = 1024 * 1024
    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="k", aws_secret_access_key="s")
    backend = S3StorageBackend(SimpleNamespace(MULTIPART_THRESHOLD=5 * mib, MULTIPART_CHUNKSIZE=5 * mib,
                                               MAX_CONCURRENCY=1))
    backend._client = client
    with Stubber(client) as stub:
        stub.add_response("create_multipart_upload", {"UploadId": "u"})
        stub.add_response("upload_part", {"ETag": '"p1"'})
        stub.add_response("upload_part", {"ETag": '"p2"'})
        stub.add_response("complete_multipart_upload", {"ETag": '"whole-2"', "VersionId": "mp-version"})
        entry = backend.write_from_stream("s3://b/big.bin", io.BytesIO(b"x" * (6 * mib)))
        stub.assert_no_pending_responses()
    assert (entry.size, entry.etag, entry.version_id) == (6 * mib, "whole-2", "mp-version")


def test_s3_stream_upload_always_uses_the_classic_transfer_manager() -> None:
    from unittest.mock import patch

    import boto3
    from boto3.s3.transfer import TransferConfig

    from mountainash_transport.storage.backends.s3 import S3StorageBackend

    if not hasattr(TransferConfig(), "preferred_transfer_client"):
        pytest.skip("this boto3 has no CRT transfer manager to avoid")
    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="k", aws_secret_access_key="s")
    backend = S3StorageBackend(None)  # no profile transfer settings
    backend._client = client
    seen: list[t.Any] = []
    with patch.object(client, "upload_fileobj", lambda *a, **kw: seen.append(kw.get("Config"))):
        backend.write_from_stream("s3://b/k", io.BytesIO(b"x"))
    assert seen[0].preferred_transfer_client == "classic"


def test_the_chapter_table_states_the_fields_each_backend_fills() -> None:
    chapter = Path(__file__).parents[3] / "docs-site/site/docs/chapters/07-file-operations/index.md"
    text = chapter.read_text().split("### What a write returns", 1)[1]
    documented = {}
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0] in {"local", "sftp", "s3", "http"}:
            documented[(cells[0], cells[1])] = frozenset(f.strip() for f in cells[2].split(","))
    assert documented == WRITE_RESULT_FIELDS
