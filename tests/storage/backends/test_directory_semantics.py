"""Shared filesystem contracts, with SFTP SDK calls backed by temporary files."""
from __future__ import annotations

import errno
import os
import typing as t
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from paramiko import SFTPAttributes

from mountainash_transport import PathNotFoundError, PermissionDeniedError, StorageConnectionError, StorageError
from mountainash_transport._core.dataclasses.storage_entry import EntryType
from mountainash_transport.storage.backends.local import LocalStorageBackend
from mountainash_transport.storage.backends.sftp import SFTPStorageBackend


class _FilesystemSFTP:
    """Only the SDK boundary is substituted; filesystem effects remain real."""

    def stat(self, path: str) -> SFTPAttributes:
        return SFTPAttributes.from_stat(os.stat(path))

    def mkdir(self, path: str) -> None:
        os.mkdir(path)

    def listdir_attr(self, path: str) -> list[SFTPAttributes]:
        return [SFTPAttributes.from_stat(os.stat(os.path.join(path, name)), name) for name in os.listdir(path)]


@pytest.fixture(params=["local", "sftp"])
def backend(request: pytest.FixtureRequest) -> LocalStorageBackend | SFTPStorageBackend:
    if request.param == "local":
        return LocalStorageBackend()
    return SFTPStorageBackend(connection=SimpleNamespace(client=_FilesystemSFTP()))


@pytest.mark.parametrize("relative", [False, True])
def test_recursive_mkdir_creates_missing_ancestors(
    backend: t.Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: bool,
) -> None:
    monkeypatch.chdir(tmp_path)
    path = "a/b/c" if relative else str(tmp_path / "a/b/c")
    backend.mkdir(path, parents=True)
    assert (tmp_path / "a/b/c").is_dir()


def test_recursive_mkdir_accepts_existing_directory(backend: t.Any, tmp_path: Path) -> None:
    backend.mkdir(str(tmp_path), parents=True)
    assert tmp_path.is_dir()


def test_single_level_mkdir_does_not_create_parents(backend: t.Any, tmp_path: Path) -> None:
    with pytest.raises(PathNotFoundError):
        backend.mkdir(str(tmp_path / "missing/child"), parents=False)
    assert not (tmp_path / "missing").exists()


@pytest.mark.parametrize("parents", [False, True])
def test_mkdir_cannot_replace_file(backend: t.Any, tmp_path: Path, parents: bool) -> None:
    path = tmp_path / "file"
    path.write_bytes(b"preserve")
    with pytest.raises(StorageError):
        backend.mkdir(str(path), parents=parents)
    assert path.read_bytes() == b"preserve"


def test_recursive_mkdir_does_not_collapse_symlink_parent(backend: t.Any, tmp_path: Path) -> None:
    (tmp_path / "target/inner").mkdir(parents=True)
    (tmp_path / "link").symlink_to(tmp_path / "target/inner", target_is_directory=True)
    backend.mkdir(str(tmp_path / "link") + "/../created/leaf", parents=True)
    assert (tmp_path / "target/created/leaf").is_dir()
    assert not (tmp_path / "created").exists()


@pytest.mark.parametrize("kind", ["file", "directory", "directory-link"])
def test_metadata_classifies_files_and_directories(backend: t.Any, tmp_path: Path, kind: str) -> None:
    path = tmp_path / "entry"
    if kind == "file":
        path.write_bytes(b"payload")
    elif kind == "directory":
        path.mkdir()
    else:
        target = tmp_path / "target"
        target.mkdir()
        path.symlink_to(target, target_is_directory=True)
    expected = EntryType.FILE if kind == "file" else EntryType.DIRECTORY
    assert backend.get_metadata(str(path)).entry_type == expected


def test_metadata_and_listing_timestamps_are_utc(backend: t.Any, tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_bytes(b"payload")
    os.utime(path, (1700000000, 1700000000))
    expected = datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)
    assert backend.get_metadata(str(path)).last_modified == expected
    assert backend.list_dir(str(tmp_path))[0].last_modified == expected


@pytest.mark.parametrize("winner", ["directory", "file", "absent"])
def test_sftp_mkdir_race_requires_a_directory(tmp_path: Path, winner: str) -> None:
    client = _FilesystemSFTP()
    path = tmp_path / "raced"
    original = OSError("Failure")  # SFTP v3 often loses EEXIST in its generic status.

    def race(name: str) -> None:
        if name != str(path):
            os.mkdir(name)
            return
        if winner == "directory":
            path.mkdir()
        elif winner == "file":
            path.write_bytes(b"winner")
        raise original

    mock = MagicMock(wraps=client)
    mock.mkdir.side_effect = race
    backend = SFTPStorageBackend(connection=SimpleNamespace(client=mock))
    if winner == "directory":
        backend.mkdir(str(path))
        assert path.is_dir()
    else:
        with pytest.raises(StorageError) as caught:
            backend.mkdir(str(path))
        assert caught.value.__cause__ is original
        if winner == "file":
            assert path.read_bytes() == b"winner"


@pytest.mark.parametrize("fault", ["stat", "mkdir"])
@pytest.mark.parametrize("original, expected", [
    (PermissionError(errno.EACCES, "denied"), PermissionDeniedError),
    (EOFError("disconnected"), StorageConnectionError),
])
def test_sftp_recursive_mkdir_preserves_failures(
    tmp_path: Path, fault: str, original: Exception, expected: type[StorageError],
) -> None:
    client = MagicMock(wraps=_FilesystemSFTP())
    getattr(client, fault).side_effect = original
    backend = SFTPStorageBackend(connection=SimpleNamespace(client=client))
    with pytest.raises(expected) as caught:
        backend.mkdir(str(tmp_path / "new"))
    assert caught.value.__cause__ is original
    assert not (tmp_path / "new").exists()


def test_sftp_missing_attributes_remain_optional() -> None:
    attrs = SFTPAttributes()
    attrs.filename = "file"
    client = MagicMock()
    client.stat.return_value = attrs
    client.listdir_attr.return_value = [attrs]
    backend = SFTPStorageBackend(connection=SimpleNamespace(client=client))
    for entry in [backend.get_metadata("file"), *backend.list_dir(".")]:
        assert entry.entry_type == EntryType.FILE
        assert entry.last_modified is None


@pytest.mark.parametrize("suffix", ["", "/"])
def test_sftp_mkdir_accepts_ancestors_with_omitted_modes(tmp_path: Path, suffix: str) -> None:
    client = _FilesystemSFTP()
    mock = MagicMock(wraps=client)

    def stat_without_mode(path: str) -> SFTPAttributes:
        attrs = client.stat(path)
        attrs.st_mode = None
        return attrs

    mock.stat.side_effect = stat_without_mode
    backend = SFTPStorageBackend(connection=SimpleNamespace(client=mock))
    backend.mkdir(str(tmp_path / "new/deep") + suffix)
    assert (tmp_path / "new/deep").is_dir()


@pytest.mark.parametrize("original, expected", [
    (TimeoutError(), StorageConnectionError),
    (ConnectionError(), StorageConnectionError),
    (PermissionError(), PermissionDeniedError),
])
def test_sftp_mkdir_does_not_hide_failure_after_server_creation(
    tmp_path: Path, original: OSError, expected: type[StorageError],
) -> None:
    client = MagicMock(wraps=_FilesystemSFTP())
    path = tmp_path / "created"

    def create_then_fail(name: str) -> None:
        os.mkdir(name)
        raise original

    client.mkdir.side_effect = create_then_fail
    backend = SFTPStorageBackend(connection=SimpleNamespace(client=client))
    with pytest.raises(expected) as caught:
        backend.mkdir(str(path))
    assert caught.value.__cause__ is original
    assert path.is_dir()  # Failure does not imply rollback.
