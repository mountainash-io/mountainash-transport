"""Tests for StorageFacade and copy_between."""

from __future__ import annotations

import io
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# Trigger backend registrations before importing the facade
import mountainash_utils_files.storage_backends  # noqa: F401

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.dataclasses.file_metadata import FileMetadata
from mountainash_utils_files.exceptions import UnsupportedOperationError
from mountainash_utils_files.storage_facade import StorageFacade, copy_between
from mountainash_utils_files.storage_protocols import (
    StorageCopyProtocol,
    StorageDeleteProtocol,
    StorageDirectoryProtocol,
    StorageListProtocol,
    StorageMetadataProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_dir():
    """Provide a temporary directory, cleaned up after the test."""
    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture()
def local_facade():
    """Return a StorageFacade backed by the local filesystem."""
    return StorageFacade.for_local()


# ---------------------------------------------------------------------------
# Factory / construction
# ---------------------------------------------------------------------------

class TestFactories:
    def test_for_local_returns_storage_facade(self):
        facade = StorageFacade.for_local()
        assert isinstance(facade, StorageFacade)

    def test_explicit_local_construction(self):
        facade = StorageFacade(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
        assert isinstance(facade, StorageFacade)

    def test_backend_is_set(self, local_facade):
        assert local_facade._backend is not None


# ---------------------------------------------------------------------------
# supports()
# ---------------------------------------------------------------------------

class TestSupports:
    def test_supports_read_protocol(self, local_facade):
        assert local_facade.supports(StorageReadProtocol) is True

    def test_supports_write_protocol(self, local_facade):
        assert local_facade.supports(StorageWriteProtocol) is True

    def test_supports_list_protocol(self, local_facade):
        assert local_facade.supports(StorageListProtocol) is True

    def test_supports_delete_protocol(self, local_facade):
        assert local_facade.supports(StorageDeleteProtocol) is True

    def test_supports_metadata_protocol(self, local_facade):
        assert local_facade.supports(StorageMetadataProtocol) is True

    def test_supports_copy_protocol(self, local_facade):
        assert local_facade.supports(StorageCopyProtocol) is True

    def test_supports_directory_protocol(self, local_facade):
        assert local_facade.supports(StorageDirectoryProtocol) is True


# ---------------------------------------------------------------------------
# Read / Write roundtrip
# ---------------------------------------------------------------------------

class TestReadWriteRoundtrip:
    def test_bytes_roundtrip(self, local_facade, tmp_dir):
        path = os.path.join(tmp_dir, "hello.bin")
        data = b"Hello, StorageFacade!"
        local_facade.write(path, data)
        assert local_facade.read(path) == data

    def test_stream_roundtrip(self, local_facade, tmp_dir):
        path = os.path.join(tmp_dir, "stream.bin")
        data = b"streamed content"
        local_facade.write_stream(path, io.BytesIO(data))
        with local_facade.read_stream(path) as fh:
            assert fh.read() == data


# ---------------------------------------------------------------------------
# exists() / delete() / metadata() / list_files() / copy() / mkdir()
# ---------------------------------------------------------------------------

class TestExists:
    def test_exists_true_for_written_file(self, local_facade, tmp_dir):
        path = os.path.join(tmp_dir, "existing.txt")
        local_facade.write(path, b"data")
        assert local_facade.exists(path) is True

    def test_exists_false_for_missing_file(self, local_facade, tmp_dir):
        path = os.path.join(tmp_dir, "missing.txt")
        assert local_facade.exists(path) is False


class TestDelete:
    def test_delete_removes_file(self, local_facade, tmp_dir):
        path = os.path.join(tmp_dir, "to_delete.txt")
        local_facade.write(path, b"bye")
        local_facade.delete(path)
        assert not os.path.exists(path)


class TestMetadata:
    def test_metadata_returns_file_metadata(self, local_facade, tmp_dir):
        path = os.path.join(tmp_dir, "meta.txt")
        data = b"metadata content"
        local_facade.write(path, data)
        meta = local_facade.metadata(path)
        assert isinstance(meta, FileMetadata)
        assert meta.filename == "meta.txt"
        assert meta.size == len(data)

    def test_get_size_returns_byte_count(self, local_facade, tmp_dir):
        path = os.path.join(tmp_dir, "sized.bin")
        data = b"12345"
        local_facade.write(path, data)
        assert local_facade.get_size(path) == len(data)


class TestListFiles:
    def test_list_files_returns_file_metadata_list(self, local_facade, tmp_dir):
        path = os.path.join(tmp_dir, "file.txt")
        local_facade.write(path, b"content")
        results = local_facade.list_files(tmp_dir)
        assert len(results) == 1
        assert isinstance(results[0], FileMetadata)
        assert results[0].filename == "file.txt"

    def test_list_directories_returns_directories(self, local_facade, tmp_dir):
        sub = os.path.join(tmp_dir, "subdir")
        os.mkdir(sub)
        results = local_facade.list_directories(tmp_dir)
        assert sub in results


class TestCopy:
    def test_copy_creates_destination(self, local_facade, tmp_dir):
        src = os.path.join(tmp_dir, "src.txt")
        dst = os.path.join(tmp_dir, "dst.txt")
        local_facade.write(src, b"copy me")
        local_facade.copy(src, dst)
        assert local_facade.read(dst) == b"copy me"


class TestMkdir:
    def test_mkdir_creates_directory(self, local_facade, tmp_dir):
        new_dir = os.path.join(tmp_dir, "new_dir")
        local_facade.mkdir(new_dir)
        assert os.path.isdir(new_dir)

    def test_mkdir_with_parents(self, local_facade, tmp_dir):
        deep = os.path.join(tmp_dir, "a", "b", "c")
        local_facade.mkdir(deep, parents=True)
        assert os.path.isdir(deep)

    def test_rmdir_removes_directory(self, local_facade, tmp_dir):
        target = os.path.join(tmp_dir, "to_remove")
        os.makedirs(target)
        local_facade.rmdir(target)
        assert not os.path.exists(target)


# ---------------------------------------------------------------------------
# UnsupportedOperationError when mkdir is called on S3 backend
# ---------------------------------------------------------------------------

class TestUnsupportedOperation:
    def test_mkdir_raises_on_s3_backend(self, tmp_dir):
        """S3StorageBackend does not implement StorageDirectoryProtocol."""
        from mountainash_utils_files.storage_backends.s3 import S3StorageBackend

        # Patch boto3.client so S3 backend can be instantiated without real AWS creds
        with patch("boto3.client"):
            facade = StorageFacade(CONST_STORAGE_PROVIDER_TYPE.S3, auth_params=None)

        assert not facade.supports(StorageDirectoryProtocol)
        with pytest.raises(UnsupportedOperationError, match="mkdir"):
            facade.mkdir(os.path.join(tmp_dir, "bucket/prefix/"))

    def test_rmdir_raises_on_s3_backend(self):
        """S3StorageBackend does not implement StorageDirectoryProtocol."""
        with patch("boto3.client"):
            facade = StorageFacade(CONST_STORAGE_PROVIDER_TYPE.S3, auth_params=None)

        with pytest.raises(UnsupportedOperationError, match="rmdir"):
            facade.rmdir("s3://bucket/prefix/")


# ---------------------------------------------------------------------------
# copy_between()
# ---------------------------------------------------------------------------

class TestCopyBetween:
    def test_copy_between_two_local_facades(self, tmp_dir):
        """copy_between with two local facades should use native copy."""
        src_path = os.path.join(tmp_dir, "src.bin")
        dst_path = os.path.join(tmp_dir, "dst.bin")
        data = b"cross backend data"

        source = StorageFacade.for_local()
        destination = StorageFacade.for_local()

        source.write(src_path, data)
        copy_between(src_path, dst_path, source, destination)

        assert destination.read(dst_path) == data

    def test_copy_between_uses_native_copy_when_same_backend(self, tmp_dir):
        """Verify that the native copy path is taken when backends match."""
        src_path = os.path.join(tmp_dir, "src.bin")
        dst_path = os.path.join(tmp_dir, "dst_native.bin")

        source = StorageFacade.for_local()
        destination = StorageFacade.for_local()
        source.write(src_path, b"native copy path")

        # Spy on the backend copy method
        original_copy = source._backend.copy
        calls = []

        def spy_copy(s, d):
            calls.append((s, d))
            return original_copy(s, d)

        source._backend.copy = spy_copy

        copy_between(src_path, dst_path, source, destination)

        assert len(calls) == 1
        assert calls[0] == (src_path, dst_path)

    def test_copy_between_streams_when_different_backend_types(self, tmp_dir):
        """When backends differ, data should stream through read_stream/write_stream.

        We verify the streaming path is taken by checking that the native copy
        method on the source backend is NOT invoked.
        """
        src_path = os.path.join(tmp_dir, "src.bin")
        dst_path = os.path.join(tmp_dir, "dst_stream.bin")
        data = b"streamed cross-backend"

        source = StorageFacade.for_local()
        destination = StorageFacade.for_local()
        source.write(src_path, data)

        # Patch the source backend copy to detect whether native copy is used
        native_copy_calls = []
        original_copy = source._backend.copy

        def tracking_copy(s, d):
            native_copy_calls.append((s, d))
            return original_copy(s, d)

        source._backend.copy = tracking_copy

        # Override the backend type check by making source and destination appear
        # to have different backend types via a mock attribute comparison
        original_backend_type = type(destination._backend)

        class _DifferentType(original_backend_type):
            """Subclass so isinstance checks still pass but type() differs."""

        destination._backend.__class__ = _DifferentType

        copy_between(src_path, dst_path, source, destination)

        # Native copy must NOT have been called
        assert native_copy_calls == [], "Expected streaming path, not native copy"
        # Data must have arrived correctly
        result_facade = StorageFacade.for_local()
        assert result_facade.read(dst_path) == data
