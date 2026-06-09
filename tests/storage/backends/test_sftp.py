"""Tests for the SFTPStorageBackend."""
from __future__ import annotations

import errno
import io

import pytest
from unittest.mock import MagicMock

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
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
    from mountainash_transport.storage.backends.ssh import SFTPStorageBackend
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
        mock_sftp.open.side_effect = PermissionError("denied")
        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(StorageError):
            backend.read_to_bytes("/remote/secret.txt")


class TestReadToStream:
    def test_returns_bytesio(self):
        mock_sftp = MagicMock()
        mock_file = MagicMock()
        mock_file.read.return_value = b"stream content"
        mock_sftp.open.return_value.__enter__ = MagicMock(return_value=mock_file)
        mock_sftp.open.return_value.__exit__ = MagicMock(return_value=False)
        backend, _ = _make_backend(mock_sftp)
        stream = backend.read_to_stream("/remote/file.txt")
        assert isinstance(stream, io.BytesIO)
        assert stream.read() == b"stream content"


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
    def test_builds_file_metadata(self):
        mock_sftp = MagicMock()
        stat = MagicMock()
        stat.st_size = 1024
        stat.st_mtime = 1_700_000_000.0
        mock_sftp.stat.return_value = stat
        backend, _ = _make_backend(mock_sftp)
        meta = backend.get_metadata("/remote/dir/file.txt")
        assert meta.filename == "file.txt"
        assert meta.directory == "/remote/dir"
        assert meta.full_path == "/remote/dir/file.txt"
        assert meta.size == 1024
        assert meta.source == "sftp"
        assert meta.last_modified is not None

    def test_path_without_slash(self):
        mock_sftp = MagicMock()
        stat = MagicMock()
        stat.st_size = 0
        stat.st_mtime = None
        mock_sftp.stat.return_value = stat
        backend, _ = _make_backend(mock_sftp)
        meta = backend.get_metadata("file.txt")
        assert meta.filename == "file.txt"
        assert meta.directory == "/"

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


class TestListPaths:
    def test_returns_filename_list(self):
        mock_sftp = MagicMock()
        entry_a = MagicMock()
        entry_a.filename = "alpha.txt"
        entry_b = MagicMock()
        entry_b.filename = "beta.txt"
        mock_sftp.listdir_attr.return_value = [entry_a, entry_b]
        backend, _ = _make_backend(mock_sftp)
        result = backend.list_paths("/remote/dir")
        assert result == ["alpha.txt", "beta.txt"]

    def test_not_found_raises_path_not_found(self):
        mock_sftp = MagicMock()
        mock_sftp.listdir_attr.side_effect = FileNotFoundError("no such directory")
        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(PathNotFoundError):
            backend.list_paths("/remote/missing")


class TestDeletePath:
    def test_removes_file(self):
        mock_sftp = MagicMock()
        backend, _ = _make_backend(mock_sftp)
        backend.delete_path("/remote/file.txt")
        mock_sftp.remove.assert_called_once_with("/remote/file.txt")

    def test_not_found_raises_path_not_found(self):
        mock_sftp = MagicMock()
        mock_sftp.remove.side_effect = FileNotFoundError("no such file")
        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(PathNotFoundError):
            backend.delete_path("/remote/missing.txt")


class TestNoConnection:
    def test_raises_storage_connection_error_when_no_connection(self):
        import mountainash_transport.storage.backends  # noqa: F401
        from mountainash_transport.storage.backends.ssh import SFTPStorageBackend
        backend = SFTPStorageBackend(None)
        with pytest.raises(StorageConnectionError, match="requires a connection"):
            backend._get_client()

    def test_raises_on_read_without_connection(self):
        import mountainash_transport.storage.backends  # noqa: F401
        from mountainash_transport.storage.backends.ssh import SFTPStorageBackend
        backend = SFTPStorageBackend(None)
        with pytest.raises(StorageConnectionError):
            backend.read_to_bytes("/remote/file.txt")

    def test_raises_when_connection_client_is_none(self):
        import mountainash_transport.storage.backends  # noqa: F401
        from mountainash_transport.storage.backends.ssh import SFTPStorageBackend
        conn = _FakeConnection(None)
        backend = SFTPStorageBackend(None, connection=conn)
        with pytest.raises(StorageConnectionError):
            backend._get_client()


class TestRegistration:
    def test_ssh_provider_registered_in_backends(self):
        import mountainash_transport.storage.backends  # noqa: F401
        from mountainash_transport.storage.registry import get_registered_backends
        backends = get_registered_backends()
        assert CONST_STORAGE_PROVIDER_TYPE.SSH in backends
