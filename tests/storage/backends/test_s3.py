"""Tests for the S3StorageBackend."""

from __future__ import annotations

import io
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

    def test_read_to_stream_returns_bytes_io(self):
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"stream data")}
        backend = _make_backend(mock_client)

        stream = backend.read_to_stream("s3://my-bucket/key.bin")
        assert stream.read() == b"stream data"

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

    def test_write_from_stream_uses_upload_fileobj(self):
        """write_from_stream must stream via upload_fileobj, not buffer via put_object."""
        mock_client = MagicMock()
        backend = _make_backend(mock_client)
        stream = io.BytesIO(b"from stream")
        backend.write_from_stream("s3://bucket/path/stream.bin", stream)
        mock_client.upload_fileobj.assert_called_once_with(
            stream, "bucket", "path/stream.bin"
        )
        mock_client.put_object.assert_not_called()

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
        error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
        exc = Exception("Not Found")
        exc.response = error_response  # type: ignore[attr-defined]
        mock_client.head_object.side_effect = exc
        # Fallback list_objects_v2 returns empty
        mock_client.list_objects_v2.return_value = {"Contents": []}
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
