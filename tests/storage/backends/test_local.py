"""Tests for the LocalStorageBackend."""

from __future__ import annotations

import io
import os
import shutil
import tempfile

import pytest

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.dataclasses.storage_entry import EntryType, StorageEntry
from mountainash_transport._core.exceptions import PathNotFoundError
from mountainash_transport.storage.registry import get_registered_backends

# Trigger backend registration
import mountainash_transport.storage.backends  # noqa: F401
from mountainash_transport.storage.backends.local import LocalStorageBackend


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_dir():
    """Provide a temporary directory and clean up after the test."""
    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture()
def backend():
    """Return a LocalStorageBackend instance with no auth params."""
    return LocalStorageBackend(None)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_registered_in_registry(self):
        backends = get_registered_backends()
        assert CONST_STORAGE_PROVIDER_TYPE.LOCAL in backends
        assert backends[CONST_STORAGE_PROVIDER_TYPE.LOCAL] is LocalStorageBackend


# ---------------------------------------------------------------------------
# Connection (no-op)
# ---------------------------------------------------------------------------

class TestConnection:
    def test_connect_is_noop(self, backend):
        backend.connect()  # should not raise

    def test_disconnect_is_noop(self, backend):
        backend.disconnect()  # should not raise

    def test_is_connected_always_true(self, backend):
        assert backend.is_connected() is True


# ---------------------------------------------------------------------------
# Read / Write roundtrip
# ---------------------------------------------------------------------------

class TestReadWriteRoundtrip:
    def test_bytes_roundtrip(self, backend, tmp_dir):
        path = os.path.join(tmp_dir, "hello.bin")
        data = b"Hello, world!"
        backend.write_from_bytes(path, data)
        assert backend.read_to_bytes(path) == data

    def test_stream_write_then_bytes_read(self, backend, tmp_dir):
        path = os.path.join(tmp_dir, "stream.bin")
        data = b"streamed content"
        stream = io.BytesIO(data)
        backend.write_from_stream(path, stream)
        assert backend.read_to_bytes(path) == data

    def test_stream_read_roundtrip(self, backend, tmp_dir):
        path = os.path.join(tmp_dir, "read_stream.bin")
        data = b"read via stream"
        backend.write_from_bytes(path, data)
        with backend.read_to_stream(path) as fh:
            assert fh.read() == data

    def test_write_creates_parent_dirs(self, backend, tmp_dir):
        path = os.path.join(tmp_dir, "a", "b", "c", "nested.txt")
        backend.write_from_bytes(path, b"nested")
        assert os.path.isfile(path)

    def test_stream_write_creates_parent_dirs(self, backend, tmp_dir):
        path = os.path.join(tmp_dir, "x", "y", "nested_stream.bin")
        backend.write_from_stream(path, io.BytesIO(b"data"))
        assert os.path.isfile(path)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class TestListDir:
    def test_list_dir_returns_storage_entries(self, backend, tmp_dir):
        with open(os.path.join(tmp_dir, "a.txt"), "w") as f:
            f.write("hello")
        os.makedirs(os.path.join(tmp_dir, "subdir"))
        results = backend.list_dir(tmp_dir)
        assert len(results) == 2
        names = {e.name for e in results}
        assert names == {"a.txt", "subdir"}

    def test_list_dir_entry_types(self, backend, tmp_dir):
        with open(os.path.join(tmp_dir, "a.txt"), "w") as f:
            f.write("hello")
        os.makedirs(os.path.join(tmp_dir, "subdir"))
        results = backend.list_dir(tmp_dir)
        by_name = {e.name: e for e in results}
        assert by_name["a.txt"].entry_type == EntryType.FILE
        assert by_name["subdir"].entry_type == EntryType.DIRECTORY

    def test_list_dir_empty(self, backend, tmp_dir):
        results = backend.list_dir(tmp_dir)
        assert results == []

    def test_list_dir_file_has_size(self, backend, tmp_dir):
        with open(os.path.join(tmp_dir, "a.txt"), "w") as f:
            f.write("12345")
        results = backend.list_dir(tmp_dir)
        assert results[0].size == 5

    def test_list_dir_directory_has_none_size(self, backend, tmp_dir):
        os.makedirs(os.path.join(tmp_dir, "subdir"))
        results = backend.list_dir(tmp_dir)
        assert results[0].size is None

    def test_list_dir_symlink_to_file(self, backend, tmp_dir):
        target = os.path.join(tmp_dir, "real.txt")
        link = os.path.join(tmp_dir, "link.txt")
        with open(target, "w") as f:
            f.write("data")
        os.symlink(target, link)
        results = backend.list_dir(tmp_dir)
        by_name = {e.name: e for e in results}
        assert by_name["link.txt"].entry_type == EntryType.FILE

    def test_list_dir_symlink_to_dir(self, backend, tmp_dir):
        target = os.path.join(tmp_dir, "realdir")
        link = os.path.join(tmp_dir, "linkdir")
        os.makedirs(target)
        os.symlink(target, link)
        results = backend.list_dir(tmp_dir)
        by_name = {e.name: e for e in results}
        assert by_name["linkdir"].entry_type == EntryType.DIRECTORY

    def test_list_dir_broken_symlink_skipped(self, backend, tmp_dir):
        link = os.path.join(tmp_dir, "broken")
        os.symlink("/nonexistent/target", link)
        results = backend.list_dir(tmp_dir)
        assert len(results) == 0

    def test_list_dir_source_is_local(self, backend, tmp_dir):
        with open(os.path.join(tmp_dir, "a.txt"), "w") as f:
            f.write("x")
        results = backend.list_dir(tmp_dir)
        assert results[0].source == "local"

    def test_list_dir_path_is_absolute(self, backend, tmp_dir):
        with open(os.path.join(tmp_dir, "a.txt"), "w") as f:
            f.write("x")
        results = backend.list_dir(tmp_dir)
        assert os.path.isabs(results[0].path)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class TestMetadata:
    def test_path_exists_true(self, backend, tmp_dir):
        path = os.path.join(tmp_dir, "exists.txt")
        backend.write_from_bytes(path, b"data")
        assert backend.path_exists(path) is True

    def test_path_exists_false(self, backend, tmp_dir):
        assert backend.path_exists(os.path.join(tmp_dir, "missing.txt")) is False

    def test_get_size(self, backend, tmp_dir):
        path = os.path.join(tmp_dir, "sized.txt")
        data = b"12345"
        backend.write_from_bytes(path, data)
        assert backend.get_size(path) == len(data)

    def test_get_metadata_returns_storage_entry(self, backend, tmp_dir):
        path = os.path.join(tmp_dir, "meta.txt")
        backend.write_from_bytes(path, b"metadata content")
        meta = backend.get_metadata(path)
        assert isinstance(meta, StorageEntry)
        assert meta.name == "meta.txt"
        assert meta.size == len(b"metadata content")
        assert meta.source == "local"
        assert meta.last_modified is not None


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDelete:
    def test_delete_file_removes_file(self, backend, tmp_dir):
        path = os.path.join(tmp_dir, "todelete.txt")
        backend.write_from_bytes(path, b"bye")
        backend.delete_file(path)
        assert not os.path.exists(path)

    def test_delete_missing_raises_path_not_found(self, backend, tmp_dir):
        path = os.path.join(tmp_dir, "ghost.txt")
        with pytest.raises(PathNotFoundError):
            backend.delete_file(path)


# ---------------------------------------------------------------------------
# Copy
# ---------------------------------------------------------------------------

class TestCopy:
    def test_copy_creates_destination(self, backend, tmp_dir):
        src = os.path.join(tmp_dir, "src.txt")
        dst = os.path.join(tmp_dir, "dst.txt")
        backend.write_from_bytes(src, b"copy me")
        backend.copy(src, dst)
        assert backend.read_to_bytes(dst) == b"copy me"

    def test_copy_creates_parent_dirs(self, backend, tmp_dir):
        src = os.path.join(tmp_dir, "src.txt")
        dst = os.path.join(tmp_dir, "deep", "nested", "dst.txt")
        backend.write_from_bytes(src, b"nested copy")
        backend.copy(src, dst)
        assert os.path.isfile(dst)


# ---------------------------------------------------------------------------
# Directory operations
# ---------------------------------------------------------------------------

class TestDirectory:
    def test_mkdir_creates_directory(self, backend, tmp_dir):
        new_dir = os.path.join(tmp_dir, "new_dir")
        backend.mkdir(new_dir)
        assert os.path.isdir(new_dir)

    def test_mkdir_with_parents(self, backend, tmp_dir):
        deep = os.path.join(tmp_dir, "a", "b", "c")
        backend.mkdir(deep, parents=True)
        assert os.path.isdir(deep)

    def test_rmdir_removes_directory_and_contents(self, backend, tmp_dir):
        target = os.path.join(tmp_dir, "to_remove")
        os.makedirs(target)
        backend.write_from_bytes(os.path.join(target, "file.txt"), b"data")
        backend.rmdir(target)
        assert not os.path.exists(target)
