"""`write_stream` never closes a caller-supplied stream, on any backend or payload size (#55)."""
from __future__ import annotations

import io
import tempfile
import typing as t

import httpx
import pytest

import mountainash_transport.storage.backends  # noqa: F401
from mountainash_transport.storage.backends.s3 import S3StorageBackend

SMALL = b"x" * 100
LARGE = b"y" * (20 * 1024 * 1024)  # above boto3's default 8 MiB multipart threshold


def _stubbed_s3(payload: bytes):
    """A real boto3 client with stubbed responses, so boto3's transfer manager runs for real."""
    import boto3
    from boto3.s3.transfer import TransferConfig
    from botocore.stub import Stubber

    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="k", aws_secret_access_key="s")
    stub = Stubber(client)
    threshold = TransferConfig().multipart_threshold
    if len(payload) < threshold:
        stub.add_response("put_object", {}, None)
    else:
        stub.add_response("create_multipart_upload", {"UploadId": "u"}, None)
        parts = -(-len(payload) // TransferConfig().multipart_chunksize)
        for _ in range(parts):
            stub.add_response("upload_part", {"ETag": '"e"'}, None)
        stub.add_response("complete_multipart_upload", {}, None)
    stub.activate()
    backend = S3StorageBackend(None)
    backend._client = client
    return backend, stub


@pytest.mark.parametrize("payload", [SMALL, LARGE], ids=["single_request", "multipart"])
@pytest.mark.parametrize("kind", ["bytesio", "file"])
def test_s3_write_stream_leaves_caller_stream_open(payload, kind, tmp_path):
    backend, stub = _stubbed_s3(payload)
    if kind == "file":
        path = tmp_path / "src.bin"
        path.write_bytes(payload)
        source: t.BinaryIO = open(path, "rb")
    else:
        source = io.BytesIO(payload)
    try:
        backend.write_from_stream("s3://b/k", source)
        stub.assert_no_pending_responses()
        assert not source.closed, "the caller's stream is borrowed"
        source.seek(0)
        assert source.read(3) == payload[:3]
    finally:
        source.close()


def test_http_write_stream_leaves_caller_stream_open():
    from mountainash_transport._core.http.engine import HttpRequestEngine
    from mountainash_transport.storage.backends.http import HTTPStorageBackend

    seen: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.read())
        return httpx.Response(201)

    backend = HTTPStorageBackend(None, engine=HttpRequestEngine(httpx.Client(transport=httpx.MockTransport(handler))))
    source = io.BytesIO(SMALL)
    backend.write_from_stream("https://h.example/k", source)
    assert seen == [SMALL]
    assert not source.closed


@pytest.mark.parametrize("payload", [SMALL, LARGE], ids=["small", "large"])
def test_local_write_stream_leaves_caller_stream_open(payload):
    from mountainash_transport import StorageFacade

    source = io.BytesIO(payload)
    with tempfile.TemporaryDirectory() as root, StorageFacade.for_local() as storage:
        storage.write_stream(f"{root}/out.bin", source)
        assert not source.closed
