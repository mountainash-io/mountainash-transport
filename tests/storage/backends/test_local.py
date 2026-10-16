"""Tests for the LocalStorageBackend."""

from __future__ import annotations

import io
import os
import shutil
import tempfile
import errno
import typing as t
from pathlib import Path
from unittest.mock import Mock

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


@pytest.mark.parametrize("operation", ["read_to_bytes", "read_to_stream", "get_metadata", "get_size"])
def test_missing_operations_preserve_native_cause(
    backend: LocalStorageBackend, tmp_path: Path, operation: str,
) -> None:
    with pytest.raises(PathNotFoundError) as caught:
        getattr(backend, operation)(str(tmp_path / "missing"))
    assert isinstance(caught.value.__cause__, FileNotFoundError)


@pytest.mark.parametrize("operation", ["path_exists", "get_size", "get_metadata", "list_dir"])
def test_denied_stat_is_not_absence(
    backend: LocalStorageBackend, monkeypatch: pytest.MonkeyPatch, operation: str,
) -> None:
    from mountainash_transport import AuthenticationError
    original = PermissionError(errno.EACCES, "denied")
    real_stat = os.stat
    def stat(path: t.Any, *args: t.Any, **kwargs: t.Any) -> os.stat_result:
        if path == "/transport-denied":
            raise original
        return real_stat(path, *args, **kwargs)
    monkeypatch.setattr(os, "stat", stat)
    with pytest.raises(AuthenticationError) as caught:
        getattr(backend, operation)("/transport-denied")
    from mountainash_transport import PermissionDeniedError
    assert type(caught.value) is PermissionDeniedError
    assert caught.value.__cause__ is original


@pytest.mark.parametrize(
    ("operation", "native", "args"),
    [
        ("write_from_bytes", "builtins.open", ("file", b"data")),
        ("write_from_stream", "builtins.open", ("file", io.BytesIO(b"data"))),
        ("copy", "shutil.copy2", ("source", "destination")),
        ("delete_file", "os.remove", ("file",)),
        ("mkdir", "os.mkdir", ("directory",)),
        ("rmdir", "shutil.rmtree", ("directory",)),
        ("list_dir", "os.scandir", (".",)),
    ],
)
def test_native_operation_failures_are_portable(
    backend: LocalStorageBackend, monkeypatch: pytest.MonkeyPatch,
    operation: str, native: str, args: tuple[t.Any, ...],
) -> None:
    from mountainash_transport import StorageError
    original = OSError(errno.EIO, "native I/O failure")
    monkeypatch.setattr(native, Mock(side_effect=original))
    # Existing delete preflight must not conceal the actual remove failure.
    if operation == "delete_file":
        monkeypatch.setattr(os.path, "exists", lambda path: True)
    with pytest.raises(StorageError) as caught:
        getattr(backend, operation)(*args)
    assert caught.value.__cause__ is original


@pytest.mark.parametrize("operation", [
    "read", "read1", "readinto", "readinto1", "readline", "readlines",
    "peek", "tell", "fileno", "flush", "close",
])
def test_native_reader_deferred_failure(
    backend: LocalStorageBackend, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    from mountainash_transport import StorageError
    path = tmp_path / "source"
    path.write_bytes(b"abc\\n")
    original = OSError(errno.EIO, "late native failure")
    with open(path, "rb") as native:
        wrapped = Mock(wraps=native)
        wrapped.closed = False
        def fail(*args: t.Any, **kwargs: t.Any) -> t.NoReturn:
            if operation == "close":
                native.close()
            raise original
        setattr(wrapped, operation, fail)
        with monkeypatch.context() as patch:
            patch.setattr("builtins.open", lambda *a, **kw: wrapped)
            stream = backend.read_to_stream(str(path))
        args = (bytearray(2),) if operation.startswith("readinto") else ()
        with pytest.raises(StorageError) as caught:
            getattr(stream, operation)(*args)
        assert caught.value.__cause__ is original
        if operation == "close":
            assert stream.closed
            stream.close()
        else:
            stream.close()


def test_local_input_error_keeps_identity(backend: LocalStorageBackend, tmp_path: Path) -> None:
    original = PermissionError(errno.EACCES, "caller-owned")
    class Input(io.BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            raise original
    with Input(b"data") as source, pytest.raises(PermissionError) as caught:
        backend.write_from_stream(str(tmp_path / "destination"), source)
    assert caught.value is original


def test_native_reader_capabilities_and_argument_errors(
    backend: LocalStorageBackend, tmp_path: Path,
) -> None:
    path = tmp_path / "source"
    path.write_bytes(b"abc\nsecond\n")
    with backend.read_to_stream(str(path)) as stream:
        assert stream.readable() and stream.seekable() and not stream.writable()
        assert os.fstat(stream.fileno()).st_size == 11
        assert stream.readline() == b"abc\n"
        assert list(stream) == [b"second\n"]
        stream.seek(0)
        buffer = bytearray(3)
        assert t.cast(io.BufferedIOBase, stream).readinto(buffer) == 3 and buffer == b"abc"
        assert stream.tell() == 3
        with pytest.raises(OSError) as caught:
            stream.seek(-1)
        assert caught.value.errno == errno.EINVAL
        with pytest.raises(ValueError):
            stream.seek(0, 99)
    with pytest.raises(ValueError):
        stream.read()


@pytest.mark.parametrize("operation", ["write_from_bytes", "write_from_stream"])
@pytest.mark.parametrize("fault", ["write", "close"])
def test_local_destination_failure_after_open(
    backend: LocalStorageBackend, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    operation: str, fault: str,
) -> None:
    from mountainash_transport import StorageError
    original = OSError(errno.EIO, "destination failed")
    class Destination(io.BytesIO):
        def write(self, data: t.Any) -> int:
            if fault == "write":
                raise original
            return super().write(data)
        def close(self) -> None:
            super().close()
            if fault == "close":
                raise original
    destination = Destination()
    with io.BytesIO(b"payload") as source, monkeypatch.context() as patch:
        patch.setattr("builtins.open", lambda *args, **kwargs: destination)
        with pytest.raises(StorageError) as caught:
            getattr(backend, operation)(
                str(tmp_path / "destination"), b"payload" if operation == "write_from_bytes" else source,
            )
    assert caught.value.__cause__ is original
    assert destination.closed


@pytest.mark.parametrize("hardlink", [False, True])
def test_same_file_copy_retains_native_refusal(
    backend: LocalStorageBackend, tmp_path: Path, hardlink: bool,
) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"unchanged")
    destination = tmp_path / "alias" if hardlink else source
    if hardlink:
        destination.hardlink_to(source)
    with pytest.raises(shutil.SameFileError):
        backend.copy(str(source), str(destination))
    assert source.read_bytes() == b"unchanged"
