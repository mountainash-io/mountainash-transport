"""Tests for the SFTPStorageBackend."""
from __future__ import annotations

import errno
import io
import typing as t

import pytest
from unittest.mock import MagicMock

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.dataclasses.storage_entry import EntryType, StorageEntry
from mountainash_transport._core.exceptions import (
    PathNotFoundError,
    StorageConnectionError,
    StorageError,
)


class _FakeConnection:
    def __init__(self, sftp_client):
        self._client = sftp_client

    @property
    def client(self):
        return self._client

    @property
    def is_connected(self):
        return self._client is not None


def _make_backend(sftp_client=None):
    if sftp_client is None:
        sftp_client = MagicMock()
    import mountainash_transport.storage.backends  # noqa: F401
    from mountainash_transport.storage.backends.sftp import SFTPStorageBackend
    conn = _FakeConnection(sftp_client)
    return SFTPStorageBackend(None, connection=conn), sftp_client


class TestReadToBytes:
    def test_reads_file_content(self):
        mock_sftp = MagicMock()
        mock_file = MagicMock()
        mock_file.read.return_value = b"hello"
        mock_sftp.open.return_value.__enter__ = MagicMock(return_value=mock_file)
        mock_sftp.open.return_value.__exit__ = MagicMock(return_value=False)
        backend, _ = _make_backend(mock_sftp)
        result = backend.read_to_bytes("/remote/file.txt")
        assert result == b"hello"
        mock_sftp.open.assert_called_once_with("/remote/file.txt", "rb")

    def test_file_not_found_raises_path_not_found(self):
        mock_sftp = MagicMock()
        mock_sftp.open.side_effect = FileNotFoundError("no such file")
        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(PathNotFoundError):
            backend.read_to_bytes("/remote/missing.txt")

    def test_ioerror_enoent_raises_path_not_found(self):
        mock_sftp = MagicMock()
        exc = IOError("no such file")
        exc.errno = errno.ENOENT
        mock_sftp.open.side_effect = exc
        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(PathNotFoundError):
            backend.read_to_bytes("/remote/missing.txt")

    def test_permission_error_raises_storage_error(self):
        mock_sftp = MagicMock()
        original = PermissionError("denied")
        mock_sftp.open.side_effect = original
        backend, _ = _make_backend(mock_sftp)
        from mountainash_transport import PermissionDeniedError
        with pytest.raises(PermissionDeniedError) as caught:
            backend.read_to_bytes("/remote/secret.txt")
        assert caught.value.__cause__ is original


class TestWriteFromBytes:
    def test_writes_data(self):
        mock_sftp = MagicMock()
        mock_file = MagicMock()
        mock_sftp.open.return_value.__enter__ = MagicMock(return_value=mock_file)
        mock_sftp.open.return_value.__exit__ = MagicMock(return_value=False)
        backend, _ = _make_backend(mock_sftp)
        backend.write_from_bytes("/remote/out.bin", b"payload")
        mock_sftp.open.assert_called_once_with("/remote/out.bin", "wb")
        mock_file.write.assert_called_once_with(b"payload")


class TestWriteFromStream:
    def test_writes_stream_content(self):
        mock_sftp = MagicMock()
        mock_file = MagicMock()
        mock_sftp.open.return_value.__enter__ = MagicMock(return_value=mock_file)
        mock_sftp.open.return_value.__exit__ = MagicMock(return_value=False)
        backend, _ = _make_backend(mock_sftp)
        backend.write_from_stream("/remote/out.bin", io.BytesIO(b"streamed"))
        mock_file.write.assert_called_once_with(b"streamed")


class TestPathExists:
    def test_returns_true_when_stat_succeeds(self):
        mock_sftp = MagicMock()
        mock_sftp.stat.return_value = MagicMock()
        backend, _ = _make_backend(mock_sftp)
        assert backend.path_exists("/remote/file.txt") is True

    def test_returns_false_on_file_not_found(self):
        mock_sftp = MagicMock()
        mock_sftp.stat.side_effect = FileNotFoundError("no such file")
        backend, _ = _make_backend(mock_sftp)
        assert backend.path_exists("/remote/missing.txt") is False

    def test_returns_false_on_ioerror_enoent(self):
        mock_sftp = MagicMock()
        exc = IOError("no such file")
        exc.errno = errno.ENOENT
        mock_sftp.stat.side_effect = exc
        backend, _ = _make_backend(mock_sftp)
        assert backend.path_exists("/remote/missing.txt") is False


class TestGetMetadata:
    def test_get_metadata_returns_storage_entry(self):
        mock_sftp = MagicMock()
        stat = MagicMock()
        stat.st_size = 1024
        stat.st_mtime = 1_700_000_000.0
        stat.st_mode = 0o100644
        mock_sftp.stat.return_value = stat
        backend, _ = _make_backend(mock_sftp)
        meta = backend.get_metadata("/remote/dir/file.txt")
        assert isinstance(meta, StorageEntry)
        assert meta.name == "file.txt"
        assert meta.path == "/remote/dir/file.txt"
        assert meta.size == 1024
        assert meta.source == "sftp"
        assert meta.last_modified is not None

    def test_path_without_slash(self):
        mock_sftp = MagicMock()
        stat = MagicMock()
        stat.st_size = None
        stat.st_mtime = None
        stat.st_mode = None
        mock_sftp.stat.return_value = stat
        backend, _ = _make_backend(mock_sftp)
        meta = backend.get_metadata("file.txt")
        assert meta.name == "file.txt"
        assert meta.path == "file.txt"

    def test_not_found_raises_path_not_found(self):
        mock_sftp = MagicMock()
        mock_sftp.stat.side_effect = FileNotFoundError("no such file")
        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(PathNotFoundError):
            backend.get_metadata("/remote/missing.txt")


class TestGetSize:
    def test_returns_file_size(self):
        mock_sftp = MagicMock()
        stat = MagicMock()
        stat.st_size = 4096
        mock_sftp.stat.return_value = stat
        backend, _ = _make_backend(mock_sftp)
        assert backend.get_size("/remote/file.txt") == 4096

    def test_not_found_raises_path_not_found(self):
        mock_sftp = MagicMock()
        mock_sftp.stat.side_effect = FileNotFoundError("no such file")
        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(PathNotFoundError):
            backend.get_size("/remote/missing.txt")


class TestListDir:
    def test_list_dir_returns_storage_entries(self):
        mock_sftp = MagicMock()
        attr_file = MagicMock()
        attr_file.filename = "file.txt"
        attr_file.st_size = 100
        attr_file.st_mtime = 1700000000.0
        attr_file.st_mode = 0o100644  # regular file

        attr_dir = MagicMock()
        attr_dir.filename = "subdir"
        attr_dir.st_size = 4096
        attr_dir.st_mtime = 1700000000.0
        attr_dir.st_mode = 0o040755  # directory

        mock_sftp.listdir_attr.return_value = [attr_file, attr_dir]
        backend, _ = _make_backend(mock_sftp)
        results = backend.list_dir("/remote/path")
        assert len(results) == 2
        by_name = {e.name: e for e in results}
        assert by_name["file.txt"].entry_type == EntryType.FILE
        assert by_name["file.txt"].size == 100
        assert by_name["subdir"].entry_type == EntryType.DIRECTORY

    def test_list_dir_empty(self):
        mock_sftp = MagicMock()
        mock_sftp.listdir_attr.return_value = []
        backend, _ = _make_backend(mock_sftp)
        results = backend.list_dir("/remote/empty")
        assert results == []

    def test_list_dir_path_not_found(self):
        mock_sftp = MagicMock()
        mock_sftp.listdir_attr.side_effect = FileNotFoundError("no such dir")
        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(PathNotFoundError):
            backend.list_dir("/remote/missing")


class TestDeleteFile:
    def test_removes_file(self):
        mock_sftp = MagicMock()
        backend, _ = _make_backend(mock_sftp)
        backend.delete_file("/remote/file.txt")
        mock_sftp.remove.assert_called_once_with("/remote/file.txt")

    def test_not_found_raises_path_not_found(self):
        mock_sftp = MagicMock()
        mock_sftp.remove.side_effect = FileNotFoundError("no such file")
        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(PathNotFoundError):
            backend.delete_file("/remote/missing.txt")


class TestRmdir:
    def test_rmdir_calls_sftp_rmdir(self):
        mock_sftp = MagicMock()
        backend, _ = _make_backend(mock_sftp)
        backend.rmdir("/remote/olddir")
        mock_sftp.rmdir.assert_called_once_with("/remote/olddir")

    def test_rmdir_not_found_raises(self):
        mock_sftp = MagicMock()
        mock_sftp.rmdir.side_effect = FileNotFoundError("no such dir")
        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(PathNotFoundError):
            backend.rmdir("/remote/missing")


class TestNoConnection:
    def test_raises_storage_connection_error_when_no_connection(self):
        import mountainash_transport.storage.backends  # noqa: F401
        from mountainash_transport.storage.backends.sftp import SFTPStorageBackend
        backend = SFTPStorageBackend(None)
        with pytest.raises(StorageConnectionError, match="requires a connection"):
            backend._get_client()

    def test_raises_on_read_without_connection(self):
        import mountainash_transport.storage.backends  # noqa: F401
        from mountainash_transport.storage.backends.sftp import SFTPStorageBackend
        backend = SFTPStorageBackend(None)
        with pytest.raises(StorageConnectionError):
            backend.read_to_bytes("/remote/file.txt")

    def test_raises_when_connection_client_is_none(self):
        import mountainash_transport.storage.backends  # noqa: F401
        from mountainash_transport.storage.backends.sftp import SFTPStorageBackend
        conn = _FakeConnection(None)
        backend = SFTPStorageBackend(None, connection=conn)
        with pytest.raises(StorageConnectionError):
            backend._get_client()


class TestRegistration:
    def test_sftp_provider_registered_in_backends(self):
        import mountainash_transport.storage.backends  # noqa: F401
        from mountainash_transport.storage.registry import get_registered_backends
        backends = get_registered_backends()
        assert CONST_STORAGE_PROVIDER_TYPE.SFTP in backends


@pytest.mark.parametrize("operation", ["path_exists", "get_size", "get_metadata"])
def test_sftp_stat_disconnect_is_not_absence(operation: str) -> None:
    client = MagicMock()
    original = EOFError("session ended")
    client.stat.side_effect = original
    backend, _ = _make_backend(client)
    with pytest.raises(StorageConnectionError) as caught:
        getattr(backend, operation)("/remote/file")
    assert caught.value.__cause__ is original


@pytest.mark.parametrize(
    ("operation", "native", "extra"),
    [("read_to_bytes", "open", ()), ("read_to_stream", "open", ()),
     ("write_from_bytes", "open", (b"x",)), ("list_dir", "listdir_attr", ()),
     ("rmdir", "rmdir", ()), ("delete_file", "remove", ())],
)
def test_sftp_sdk_transport_failure(operation: str, native: str, extra: tuple[t.Any, ...]) -> None:
    from paramiko import SSHException
    client = MagicMock()
    original = SSHException("transport failed")
    getattr(client, native).side_effect = original
    backend, _ = _make_backend(client)
    with pytest.raises(StorageConnectionError) as caught:
        getattr(backend, operation)("/remote/file", *extra)
    assert caught.value.__cause__ is original


@pytest.mark.parametrize("ranged", [False, True])
@pytest.mark.parametrize("fault", ["read", "close"])
def test_sftp_late_failure_is_portable(ranged: bool, fault: str) -> None:
    client = MagicMock()
    handle = client.open.return_value
    handle.stat.return_value.st_size = 3
    handle.read.return_value = b"abc"
    original = EOFError("late disconnect")
    getattr(handle, fault).side_effect = original
    backend, _ = _make_backend(client)
    source = backend.open_ranged("/file") if ranged else backend.read_to_stream("/file")
    with pytest.raises(StorageConnectionError) as caught:
        try:
            if fault == "read":
                source.fetch(0, 3) if ranged else source.read(3)
        finally:
            source.on_close() if ranged else source.close()
    assert caught.value.__cause__ is original


def test_sftp_caller_input_failure_is_unchanged() -> None:
    original = EOFError("caller source ended")
    class Input(io.BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            raise original
    backend, _ = _make_backend()
    with Input(b"x") as source, pytest.raises(EOFError) as caught:
        backend.write_from_stream("/destination", source)
    assert caught.value is original
