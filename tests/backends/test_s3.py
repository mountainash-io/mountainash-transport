"""Tests for the S3StorageBackend."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.dataclasses.file_metadata import FileMetadata
from mountainash_utils_files.exceptions import StorageConnectionError
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
from mountainash_utils_files.storage_registry import get_registered_backends

# Trigger backend registration
import mountainash_utils_files.storage_backends  # noqa: F401
from mountainash_utils_files.storage_backends.s3 import S3StorageBackend
from mountainash_utils_files.storage_backends.s3.s3_path import parse_s3_path


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
        assert key == "prefix/"


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

class TestProtocolConformance:
    """S3StorageBackend must satisfy 7 storage protocols (NOT StorageDirectoryProtocol)."""

    @pytest.fixture()
    def backend(self):
        return _make_backend()

    def test_connection_protocol(self, backend):
        assert isinstance(backend, StorageConnectionProtocol)

    def test_read_protocol(self, backend):
        assert isinstance(backend, StorageReadProtocol)

    def test_write_protocol(self, backend):
        assert isinstance(backend, StorageWriteProtocol)

    def test_list_protocol(self, backend):
        assert isinstance(backend, StorageListProtocol)

    def test_delete_protocol(self, backend):
        assert isinstance(backend, StorageDeleteProtocol)

    def test_metadata_protocol(self, backend):
        assert isinstance(backend, StorageMetadataProtocol)

    def test_copy_protocol(self, backend):
        assert isinstance(backend, StorageCopyProtocol)

    def test_NOT_directory_protocol(self, backend):
        """S3 has no real directories — must NOT implement StorageDirectoryProtocol."""
        assert not isinstance(backend, StorageDirectoryProtocol)


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
    def test_connect_creates_boto3_client(self):
        mock_settings = MagicMock()
        mock_settings.SECRET_ACCESS_KEY = "secret"
        mock_settings.ENDPOINT_URL = None
        mock_settings.ACCESS_KEY_ID = "access"
        mock_settings.REGION = "us-east-1"

        mock_auth = MagicMock()
        mock_auth.settings = mock_settings

        backend = S3StorageBackend(mock_auth)
        assert not backend.is_connected()

        with patch("boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = MagicMock()
            backend.connect()

        mock_boto3_client.assert_called_once_with(
            "s3",
            endpoint_url=None,
            aws_access_key_id="access",
            aws_secret_access_key="secret",
            region_name="us-east-1",
        )
        assert backend.is_connected()

    def test_connect_with_secret_str(self):
        """SecretStr values are unwrapped via get_secret_value()."""
        mock_secret = MagicMock()
        mock_secret.get_secret_value.return_value = "mysecret"

        mock_settings = MagicMock()
        mock_settings.SECRET_ACCESS_KEY = mock_secret
        mock_settings.ENDPOINT_URL = None
        mock_settings.ACCESS_KEY_ID = "key"
        mock_settings.REGION = "eu-west-1"

        mock_auth = MagicMock()
        mock_auth.settings = mock_settings

        backend = S3StorageBackend(mock_auth)
        with patch("boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = MagicMock()
            backend.connect()

        _, kwargs = mock_boto3_client.call_args
        assert kwargs["aws_secret_access_key"] == "mysecret"

    def test_connect_raises_storage_connection_error_on_failure(self):
        mock_auth = MagicMock()
        mock_auth.settings = MagicMock(
            SECRET_ACCESS_KEY="s",
            ENDPOINT_URL=None,
            ACCESS_KEY_ID="a",
            REGION="us-east-1",
        )
        backend = S3StorageBackend(mock_auth)
        with patch("boto3.client", side_effect=RuntimeError("boom")):
            with pytest.raises(StorageConnectionError, match="boom"):
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
# List
# ---------------------------------------------------------------------------

class TestList:
    def test_list_files_returns_file_metadata(self):
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

        results = backend.list_files("s3://my-bucket/prefix/")

        assert len(results) == 1
        meta = results[0]
        assert isinstance(meta, FileMetadata)
        assert meta.filename == "file1.txt"
        assert meta.size == 100
        assert meta.last_modified == ts
        assert meta.etag == "abc123"
        assert meta.source == "s3"
        assert meta.full_path == "s3://my-bucket/prefix/file1.txt"

    def test_list_files_empty(self):
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = _paginator_for([{"Contents": []}])
        backend = _make_backend(mock_client)

        results = backend.list_files("s3://bucket/empty/")
        assert results == []

    def test_list_files_no_contents_key(self):
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = _paginator_for([{}])
        backend = _make_backend(mock_client)

        results = backend.list_files("s3://bucket/prefix/")
        assert results == []

    def test_list_directories(self):
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

        results = backend.list_directories("s3://bucket/top/")

        assert "s3://bucket/top/subdir1/" in results
        assert "s3://bucket/top/subdir2/" in results

    def test_list_directories_uses_delimiter(self):
        mock_client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = iter([{"CommonPrefixes": []}])
        mock_client.get_paginator.return_value = paginator
        backend = _make_backend(mock_client)

        backend.list_directories("s3://bucket/prefix/")

        paginator.paginate.assert_called_once_with(
            Bucket="bucket", Prefix="prefix/", Delimiter="/"
        )


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestMetadata:
    def test_get_metadata(self):
        ts = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 512,
            "LastModified": ts,
            "ETag": '"deadbeef"',
            "StorageClass": "STANDARD",
        }
        backend = _make_backend(mock_client)

        meta = backend.get_metadata("s3://bucket/folder/file.csv")

        mock_client.head_object.assert_called_once_with(Bucket="bucket", Key="folder/file.csv")
        assert isinstance(meta, FileMetadata)
        assert meta.filename == "file.csv"
        assert meta.size == 512
        assert meta.last_modified == ts
        assert meta.etag == "deadbeef"
        assert meta.source == "s3"
        assert meta.full_path == "s3://bucket/folder/file.csv"

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
