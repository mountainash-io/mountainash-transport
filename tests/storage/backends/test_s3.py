"""Tests for the S3StorageBackend."""

from __future__ import annotations

import io
from contextlib import closing
import typing as t
from botocore.exceptions import ClientError
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.dataclasses.storage_entry import (
    EntryType,
    EnumerateResult,
    StorageEntry,
)
from mountainash_transport._core.exceptions import StorageConnectionError
from mountainash_transport.storage.registry import get_registered_backends

# Trigger backend registration
import mountainash_transport.storage.backends  # noqa: F401
from mountainash_transport.storage.backends.s3 import S3StorageBackend
from mountainash_transport.storage.backends.s3.s3_path import parse_s3_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_backend(mock_client: MagicMock | None = None) -> S3StorageBackend:
    """Return an S3StorageBackend with a pre-injected mock boto3 client."""
    backend = S3StorageBackend(None)
    backend._client = mock_client or MagicMock()
    return backend


def _paginator_for(pages: list[dict]) -> MagicMock:
    """Return a mock paginator whose ``paginate`` yields *pages*."""
    paginator = MagicMock()
    paginator.paginate.return_value = iter(pages)
    return paginator


# ---------------------------------------------------------------------------
# parse_s3_path utility
# ---------------------------------------------------------------------------

class TestParseS3Path:
    def test_with_s3_scheme(self):
        assert parse_s3_path("s3://my-bucket/path/to/key.txt") == ("my-bucket", "path/to/key.txt")

    def test_without_scheme(self):
        assert parse_s3_path("my-bucket/some/key") == ("my-bucket", "some/key")

    def test_bucket_only_with_scheme(self):
        assert parse_s3_path("s3://my-bucket") == ("my-bucket", "")

    def test_bucket_only_no_scheme(self):
        assert parse_s3_path("my-bucket") == ("my-bucket", "")

    def test_bucket_with_trailing_slash(self):
        bucket, key = parse_s3_path("s3://my-bucket/prefix/")
        assert bucket == "my-bucket"
        assert key == "prefix"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_registered_in_registry(self):
        backends = get_registered_backends()
        assert CONST_STORAGE_PROVIDER_TYPE.S3 in backends
        assert backends[CONST_STORAGE_PROVIDER_TYPE.S3] is S3StorageBackend


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

class TestConnection:
    def test_connect_raises_storage_connection_error_on_failure(self):
        backend = S3StorageBackend(None)
        with pytest.raises(StorageConnectionError, match="requires a connection"):
            backend.connect()

    def test_disconnect_clears_client(self):
        backend = _make_backend()
        assert backend.is_connected()
        backend.disconnect()
        assert not backend.is_connected()

    def test_is_connected_false_initially(self):
        backend = S3StorageBackend(None)
        assert not backend.is_connected()


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

class TestRead:
    def test_read_to_bytes(self):
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"hello s3")}
        backend = _make_backend(mock_client)

        result = backend.read_to_bytes("s3://my-bucket/data/file.txt")

        mock_client.get_object.assert_called_once_with(Bucket="my-bucket", Key="data/file.txt")
        assert result == b"hello s3"

    def test_read_without_scheme(self):
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"no scheme")}
        backend = _make_backend(mock_client)

        result = backend.read_to_bytes("my-bucket/key.txt")
        mock_client.get_object.assert_called_once_with(Bucket="my-bucket", Key="key.txt")
        assert result == b"no scheme"


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

class TestWrite:
    def test_write_from_bytes(self):
        mock_client = MagicMock()
        backend = _make_backend(mock_client)

        backend.write_from_bytes("s3://bucket/path/file.txt", b"write me")

        mock_client.put_object.assert_called_once_with(
            Bucket="bucket", Key="path/file.txt", Body=b"write me"
        )

    def test_write_without_scheme(self):
        mock_client = MagicMock()
        backend = _make_backend(mock_client)

        backend.write_from_bytes("bucket/key.txt", b"data")
        mock_client.put_object.assert_called_once_with(Bucket="bucket", Key="key.txt", Body=b"data")


# ---------------------------------------------------------------------------
# Enumerate (replaces List)
# ---------------------------------------------------------------------------

class TestEnumerate:
    def test_list_objects_returns_enumerate_result(self):
        ts = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = _paginator_for([
            {
                "Contents": [
                    {
                        "Key": "prefix/file1.txt",
                        "Size": 100,
                        "LastModified": ts,
                        "ETag": '"abc123"',
                        "StorageClass": "STANDARD",
                    }
                ]
            }
        ])
        backend = _make_backend(mock_client)

        result = backend.list_objects("s3://my-bucket/prefix/")

        assert isinstance(result, EnumerateResult)
        assert len(result.objects) == 1
        entry = result.objects[0]
        assert isinstance(entry, StorageEntry)
        assert entry.name == "file1.txt"
        assert entry.size == 100
        assert entry.last_modified == ts
        assert entry.etag == "abc123"
        assert entry.source == "s3"
        assert entry.path == "s3://my-bucket/prefix/file1.txt"
        assert entry.storage_class == "STANDARD"
        assert entry.entry_type == EntryType.FILE
        assert result.common_prefixes == ()

    def test_list_objects_empty_returns_empty_enumerate_result(self):
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = _paginator_for([{"Contents": []}])
        backend = _make_backend(mock_client)

        result = backend.list_objects("s3://bucket/empty/")

        assert isinstance(result, EnumerateResult)
        assert result.objects == ()
        assert result.common_prefixes == ()

    def test_list_objects_no_contents_key(self):
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = _paginator_for([{}])
        backend = _make_backend(mock_client)

        result = backend.list_objects("s3://bucket/prefix/")
        assert result.objects == ()
        assert result.common_prefixes == ()

    def test_list_objects_with_delimiter_returns_common_prefixes(self):
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = _paginator_for([
            {
                "CommonPrefixes": [
                    {"Prefix": "top/subdir1/"},
                    {"Prefix": "top/subdir2/"},
                ]
            }
        ])
        backend = _make_backend(mock_client)

        result = backend.list_objects("s3://bucket/top/", delimiter="/")

        assert isinstance(result, EnumerateResult)
        assert len(result.common_prefixes) == 2
        paths = {e.path for e in result.common_prefixes}
        assert "s3://bucket/top/subdir1/" in paths
        assert "s3://bucket/top/subdir2/" in paths
        for entry in result.common_prefixes:
            assert entry.entry_type == EntryType.PREFIX
            assert entry.source == "s3"

    def test_list_objects_delimiter_passes_to_paginator(self):
        mock_client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = iter([{"CommonPrefixes": []}])
        mock_client.get_paginator.return_value = paginator
        backend = _make_backend(mock_client)

        backend.list_objects("s3://bucket/prefix/", delimiter="/")

        paginator.paginate.assert_called_once_with(
            Bucket="bucket", Prefix="prefix", Delimiter="/"
        )

    def test_list_objects_no_delimiter_omits_param(self):
        mock_client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = iter([{}])
        mock_client.get_paginator.return_value = paginator
        backend = _make_backend(mock_client)

        backend.list_objects("s3://bucket/prefix/")

        call_kwargs = paginator.paginate.call_args[1]
        assert "Delimiter" not in call_kwargs
        call_args = paginator.paginate.call_args[0]
        # Also verify no positional Delimiter
        assert len(call_args) == 0 or "Delimiter" not in str(call_args)

    def test_list_objects_max_results_caps(self):
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = _paginator_for([
            {
                "Contents": [
                    {"Key": f"prefix/file{i}.txt", "Size": i, "ETag": f'"{i}"'}
                    for i in range(5)
                ]
            }
        ])
        backend = _make_backend(mock_client)

        result = backend.list_objects("s3://bucket/prefix/", max_results=3)

        assert len(result.objects) <= 3

    def test_list_objects_common_prefix_entry_type_is_prefix(self):
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = _paginator_for([
            {
                "CommonPrefixes": [{"Prefix": "dir/subdir/"}],
            }
        ])
        backend = _make_backend(mock_client)

        result = backend.list_objects("s3://bucket/dir/", delimiter="/")

        assert len(result.common_prefixes) == 1
        entry = result.common_prefixes[0]
        assert entry.entry_type == EntryType.PREFIX
        assert entry.name == "subdir"


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestMetadata:
    def test_get_metadata_returns_storage_entry(self):
        ts = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 512,
            "LastModified": ts,
            "ETag": '"deadbeef"',
            "StorageClass": "STANDARD",
            "ContentType": "text/csv",
        }
        backend = _make_backend(mock_client)

        meta = backend.get_metadata("s3://bucket/folder/file.csv")

        mock_client.head_object.assert_called_once_with(Bucket="bucket", Key="folder/file.csv")
        assert isinstance(meta, StorageEntry)
        assert meta.name == "file.csv"
        assert meta.size == 512
        assert meta.last_modified == ts
        assert meta.etag == "deadbeef"
        assert meta.source == "s3"
        assert meta.path == "s3://bucket/folder/file.csv"
        assert meta.content_type == "text/csv"
        assert meta.storage_class == "STANDARD"

    def test_get_metadata_version_id_from_head_object(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 100,
            "ETag": '"etag"',
            "VersionId": "v1-abc",
        }
        backend = _make_backend(mock_client)

        meta = backend.get_metadata("s3://bucket/versioned.txt")
        assert meta.version_id == "v1-abc"

    def test_get_metadata_version_id_empty_when_absent(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 50,
            "ETag": '"etag"',
        }
        backend = _make_backend(mock_client)

        meta = backend.get_metadata("s3://bucket/plain.txt")
        assert meta.version_id == ""

    def test_get_metadata_checksum_sha256(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 256,
            "ETag": '"etag"',
            "ChecksumSHA256": "abc123sha",
        }
        backend = _make_backend(mock_client)

        meta = backend.get_metadata("s3://bucket/checksummed.bin")
        assert meta.checksum == "abc123sha"
        assert meta.checksum_algorithm == "SHA256"

    def test_get_metadata_checksum_preference_order(self):
        """SHA256 takes precedence over CRC32C, CRC32, SHA1."""
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 100,
            "ETag": '"etag"',
            "ChecksumSHA1": "sha1val",
            "ChecksumCRC32": "crc32val",
            "ChecksumSHA256": "sha256val",
        }
        backend = _make_backend(mock_client)

        meta = backend.get_metadata("s3://bucket/multi.bin")
        assert meta.checksum == "sha256val"
        assert meta.checksum_algorithm == "SHA256"

    def test_get_metadata_checksum_empty_when_absent(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 10,
            "ETag": '"etag"',
        }
        backend = _make_backend(mock_client)

        meta = backend.get_metadata("s3://bucket/plain.txt")
        assert meta.checksum == ""
        assert meta.checksum_algorithm == ""

    def test_path_exists_true(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {"ContentLength": 10}
        backend = _make_backend(mock_client)

        assert backend.path_exists("s3://bucket/key.txt") is True

    def test_path_exists_false_on_404(self):
        mock_client = MagicMock()
        exc = ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")
        mock_client.head_object.side_effect = exc
        backend = _make_backend(mock_client)

        assert backend.path_exists("s3://bucket/missing.txt") is False

    def test_get_size(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {"ContentLength": 1024}
        backend = _make_backend(mock_client)

        size = backend.get_size("s3://bucket/big-file.bin")
        assert size == 1024

    def test_get_size_returns_int(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {"ContentLength": 42}
        backend = _make_backend(mock_client)

        size = backend.get_size("s3://bucket/file.bin")
        assert isinstance(size, int)
        assert size == 42


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDelete:
    def test_delete_file_calls_delete_object(self):
        mock_client = MagicMock()
        backend = _make_backend(mock_client)

        backend.delete_file("s3://bucket/path/to/file.txt")

        mock_client.delete_object.assert_called_once_with(
            Bucket="bucket", Key="path/to/file.txt"
        )

    def test_delete_without_scheme(self):
        mock_client = MagicMock()
        backend = _make_backend(mock_client)

        backend.delete_file("bucket/key.txt")
        mock_client.delete_object.assert_called_once_with(Bucket="bucket", Key="key.txt")


# ---------------------------------------------------------------------------
# Copy
# ---------------------------------------------------------------------------

class TestCopy:
    def test_copy_calls_copy_object(self):
        mock_client = MagicMock()
        backend = _make_backend(mock_client)

        backend.copy("s3://src-bucket/src/file.txt", "s3://dst-bucket/dst/file.txt")

        mock_client.copy_object.assert_called_once_with(
            Bucket="dst-bucket",
            Key="dst/file.txt",
            CopySource={"Bucket": "src-bucket", "Key": "src/file.txt"},
        )

    def test_copy_same_bucket(self):
        mock_client = MagicMock()
        backend = _make_backend(mock_client)

        backend.copy("s3://bucket/original.txt", "s3://bucket/copy.txt")

        mock_client.copy_object.assert_called_once_with(
            Bucket="bucket",
            Key="copy.txt",
            CopySource={"Bucket": "bucket", "Key": "original.txt"},
        )

    def test_copy_without_scheme(self):
        mock_client = MagicMock()
        backend = _make_backend(mock_client)

        backend.copy("src-bucket/a.txt", "dst-bucket/b.txt")
        mock_client.copy_object.assert_called_once_with(
            Bucket="dst-bucket",
            Key="b.txt",
            CopySource={"Bucket": "src-bucket", "Key": "a.txt"},
        )


@pytest.mark.parametrize(
    ("code", "status", "category"),
    [("InvalidAccessKeyId", 403, "AuthenticationError"),
     ("SignatureDoesNotMatch", 403, "AuthenticationError"),
     ("ExpiredToken", 403, "AuthenticationError"),
     ("AccessDenied", 403, "PermissionDeniedError"),
     ("Unknown", 403, "PermissionDeniedError"),
     ("NoSuchBucket", 404, "PathNotFoundError"),
     ("NoSuchKey", 404, "PathNotFoundError"),
     ("RequestTimeout", 400, "StorageConnectionError"),
     ("InternalError", 500, "StorageError")],
)
def test_s3_structured_failure_categories(code: str, status: int, category: str) -> None:
    import mountainash_transport as transport
    client = MagicMock()
    original = ClientError({"Error": {"Code": code},
                            "ResponseMetadata": {"HTTPStatusCode": status}}, "HeadObject")
    client.head_object.side_effect = original
    with pytest.raises(getattr(transport, category)) as caught:
        _make_backend(client).get_metadata("s3://bucket/key")
    assert type(caught.value) is getattr(transport, category)
    assert caught.value.__cause__ is original


@pytest.mark.parametrize(
    ("operation", "native", "extra"),
    [("read_to_bytes", "get_object", ()), ("read_to_stream", "get_object", ()),
     ("get_size", "head_object", ()), ("path_exists", "head_object", ()),
     ("write_from_bytes", "put_object", (b"data",)),
     ("write_from_stream", "upload_fileobj", (io.BytesIO(b"data"),)),
     ("copy", "copy_object", ("s3://bucket/destination",)),
     ("delete_file", "delete_object", ())],
)
def test_s3_operation_denial(
    operation: str, native: str, extra: tuple[t.Any, ...],
) -> None:
    from mountainash_transport import PermissionDeniedError
    client = MagicMock()
    original = ClientError({"Error": {"Code": "AccessDenied"}}, native)
    getattr(client, native).side_effect = original
    client.list_objects_v2.side_effect = AssertionError("denial must not fall back to LIST")
    with pytest.raises(PermissionDeniedError) as caught:
        getattr(_make_backend(client), operation)("s3://bucket/key", *extra)
    assert caught.value.__cause__ is original


def test_s3_page_failure_does_not_return_partial_listing() -> None:
    from mountainash_transport import PermissionDeniedError
    client = MagicMock()
    original = ClientError({"Error": {"Code": "AccessDenied"}}, "ListObjectsV2")
    def pages() -> t.Iterator[dict[str, t.Any]]:
        yield {"Contents": [{"Key": "first", "Size": 3}]}
        raise original
    client.get_paginator.return_value.paginate.return_value = pages()
    with pytest.raises(PermissionDeniedError) as caught:
        _make_backend(client).list_objects("s3://bucket/prefix")
    assert caught.value.__cause__ is original


@pytest.mark.parametrize("operation", ["read_to_bytes", "read_to_stream"])
@pytest.mark.parametrize("fault", ["read", "close"])
def test_s3_body_failure_is_mapped(operation: str, fault: str) -> None:
    from mountainash_transport import StorageError
    original = OSError("body failure")
    body = MagicMock()
    body.read.return_value = b"abc"
    getattr(body, fault).side_effect = original
    client = MagicMock()
    client.get_object.return_value = {"Body": body}
    with pytest.raises(StorageError) as caught:
        result = getattr(_make_backend(client), operation)("s3://bucket/key")
        if operation == "read_to_stream":
            try:
                if fault == "read":
                    result.read(1)
            finally:
                result.close()
    assert caught.value.__cause__ is original


def test_s3_managed_upload_preserves_colliding_caller_error() -> None:
    import boto3
    from botocore.stub import Stubber
    original = ClientError({"Error": {"Code": "AccessDenied"}}, "caller")
    class Input(io.BytesIO):
        def seekable(self) -> bool:
            return False
        def read(self, size: int | None = -1) -> bytes:
            raise original
    with closing(boto3.client("s3", region_name="us-east-1", aws_access_key_id="dummy",
                              aws_secret_access_key="dummy")) as client:
        backend = _make_backend()
        backend._client = client
        with Stubber(client), Input(b"x") as source, pytest.raises(ClientError) as caught:
            backend.write_from_stream("s3://bucket/key", source)
        assert caught.value is original


def test_s3_wrapped_input_failure_restores_caller_cause() -> None:
    from botocore.exceptions import ConnectionClosedError
    original = OSError("caller read")
    cause = ValueError("caller cause")
    class Input(io.BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            raise original from cause
    def upload(source: t.BinaryIO, bucket: str, key: str) -> None:
        try:
            source.read()
        except OSError as exc:
            raise ConnectionClosedError(endpoint_url="http://localhost") from exc
    client = MagicMock()
    client.upload_fileobj.side_effect = upload
    with Input(b"x") as source, pytest.raises(OSError) as caught:
        _make_backend(client).write_from_stream("s3://bucket/key", source)
    assert caught.value is original
    assert original.__cause__ is cause
    assert not isinstance(original.__context__, ConnectionClosedError)


def test_s3_multipart_worker_denial_is_portable() -> None:
    import boto3
    from boto3.s3.transfer import TransferConfig
    from botocore.stub import Stubber
    from mountainash_transport import AuthenticationError
    with closing(boto3.client("s3", region_name="us-east-1", aws_access_key_id="dummy",
                              aws_secret_access_key="dummy")) as client:
        native_upload = client.upload_fileobj
        def upload(source: t.BinaryIO, bucket: str, key: str) -> None:
            native_upload(source, bucket, key,
                          Config=TransferConfig(multipart_threshold=1, max_concurrency=1))
        client.upload_fileobj = upload
        backend = _make_backend()
        backend._client = client
        with Stubber(client) as stub, io.BytesIO(b"x" * (6 * 1024 * 1024)) as source:
            stub.add_response("create_multipart_upload", {"UploadId": "upload"})
            stub.add_client_error("upload_part", service_error_code="AccessDenied", http_status_code=403)
            stub.add_response("abort_multipart_upload", {})
            with pytest.raises(AuthenticationError) as caught:
                backend.write_from_stream("s3://bucket/key", source)
            from mountainash_transport import PermissionDeniedError
            assert type(caught.value) is PermissionDeniedError
            assert isinstance(caught.value.__cause__, ClientError)
            stub.assert_no_pending_responses()
