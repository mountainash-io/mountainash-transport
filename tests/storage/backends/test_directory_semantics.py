"""Shared filesystem contracts, with SFTP SDK calls backed by temporary files."""
from __future__ import annotations

import errno
import gzip
import io
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
from mountainash_transport import Gzip, StorageFacade


class _FilesystemSFTP:
    """Only the SDK boundary is substituted; filesystem effects remain real."""

    def stat(self, path: str) -> SFTPAttributes:
        try:
            return SFTPAttributes.from_stat(os.stat(path))
        except NotADirectoryError:
            # SFTP v3 reports both ENOENT and ENOTDIR as NO_SUCH_FILE.
            raise FileNotFoundError(errno.ENOENT, "No such file") from None

    def lstat(self, path: str) -> SFTPAttributes:
        return SFTPAttributes.from_stat(os.lstat(path))

    def mkdir(self, path: str) -> None:
        os.mkdir(path)

    def open(self, path: str, mode: str) -> t.BinaryIO:
        return t.cast(t.BinaryIO, open(path, mode))

    def listdir_attr(self, path: str) -> list[SFTPAttributes]:
        return [SFTPAttributes.from_stat(os.lstat(os.path.join(path, name)), name) for name in os.listdir(path)]


@pytest.fixture(params=["local", "sftp"])
def backend(request: pytest.FixtureRequest) -> LocalStorageBackend | SFTPStorageBackend:
    if request.param == "local":
        return LocalStorageBackend()
    return SFTPStorageBackend(connection=SimpleNamespace(client=_FilesystemSFTP()))


@pytest.mark.parametrize("mode", ["bytes", "stream", "gzip"])
@pytest.mark.parametrize("create_parents", [None, True, False])
@pytest.mark.parametrize("parent_exists", [False, True])
def test_write_parent_policy(
    backend: t.Any, tmp_path: Path, mode: str,
    create_parents: bool | None, parent_exists: bool,
) -> None:
    """A disabled policy must not recreate missing parents on any write route."""
    path = tmp_path / "missing/nested/payload"
    if parent_exists:
        path.parent.mkdir(parents=True)
    options: dict[str, t.Any] = {}
    if create_parents is not None:
        options["create_parents"] = create_parents
    with StorageFacade.for_local() as facade:
        facade._backend = backend

        def write() -> None:
            if mode == "stream":
                facade.write_stream(str(path), io.BytesIO(b"payload"), **options)
            else:
                facade.write(str(path), b"payload", pipeline=Gzip() if mode == "gzip" else None, **options)

        if create_parents is False and not parent_exists:
            with pytest.raises(PathNotFoundError):
                write()
            assert not (tmp_path / "missing").exists()
        else:
            write()
            stored = path.read_bytes()
            assert (gzip.decompress(stored) if mode == "gzip" else stored) == b"payload"


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


@pytest.fixture
def enumeration_tree(tmp_path: Path) -> Path:
    root = tmp_path / "reports"
    (root / "sub").mkdir(parents=True)
    (root / "empty").mkdir()
    (root / "a.csv").write_bytes(b"abc")
    (root / "a.csv.bak").write_bytes(b"backup")
    (root / "sub/b.csv").write_bytes(b"nested")
    (tmp_path / "reports-old").mkdir()
    (tmp_path / "reports-old/c.csv").write_bytes(b"sibling")
    os.utime(root / "a.csv", (1700000000, 1700000000))
    return root


class TestFilesystemEnumeration:
    @pytest.mark.parametrize("selection, delimiter, files, prefixes", [
        ("", None, {"a.csv", "a.csv.bak", "sub/b.csv"}, set()),
        ("/", "/", {"a.csv", "a.csv.bak"}, {"sub", "empty"}),
        ("/sub", None, {"sub/b.csv"}, set()),
        ("/a.csv", None, {"a.csv"}, set()),
        ("/a.csv", "/", {"a.csv"}, set()),
        ("/absent/deep", None, set(), set()),
        ("/empty", None, set(), set()),
    ])
    def test_enumeration_selects_exact_path(
        self, backend: t.Any, enumeration_tree: Path, selection: str,
        delimiter: str | None, files: set[str], prefixes: set[str],
    ) -> None:
        root = enumeration_tree
        result = backend.list_objects(str(root) + selection, delimiter=delimiter)
        assert {entry.path for entry in result.objects} == {str(root / name) for name in files}
        assert {entry.path for entry in result.common_prefixes} == {str(root / name) for name in prefixes}
        assert all(entry.entry_type == EntryType.FILE for entry in result.objects)
        assert all(entry.entry_type == EntryType.PREFIX for entry in result.common_prefixes)
        if "a.csv" in files:
            entry = next(entry for entry in result.objects if entry.name == "a.csv")
            assert entry.size == 3
            assert entry.last_modified == datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)
            assert entry.source == ("local" if isinstance(backend, LocalStorageBackend) else "sftp")

    @pytest.mark.parametrize("suffix", ["/", "/child"])
    def test_enumeration_file_component_is_not_absence(
        self, backend: t.Any, enumeration_tree: Path, suffix: str,
    ) -> None:
        with pytest.raises(StorageError) as caught:
            backend.list_objects(str(enumeration_tree / "a.csv") + suffix)
        assert not isinstance(caught.value, PathNotFoundError)
        assert isinstance(caught.value.__cause__, NotADirectoryError)

    @pytest.mark.parametrize("selection, expected", [
        ("a.csv", StorageError), ("absent", PathNotFoundError),
    ])
    def test_list_dir_requires_existing_directory(
        self, backend: t.Any, enumeration_tree: Path, selection: str, expected: type[StorageError],
    ) -> None:
        with pytest.raises(expected) as caught:
            backend.list_dir(str(enumeration_tree / selection))
        if selection == "a.csv":
            assert not isinstance(caught.value, PathNotFoundError)
            assert isinstance(caught.value.__cause__, NotADirectoryError)

    @pytest.mark.parametrize("delimiter", [None, "/"])
    @pytest.mark.parametrize("limit", [1, 2, 3, 8])
    def test_enumeration_caps_both_collections(
        self, backend: t.Any, enumeration_tree: Path, delimiter: str | None, limit: int,
    ) -> None:
        result = backend.list_objects(str(enumeration_tree), delimiter=delimiter, max_results=limit)
        entries = result.objects + result.common_prefixes
        allowed = {"a.csv", "a.csv.bak", "sub/b.csv"} if delimiter is None else {
            "a.csv", "a.csv.bak", "sub", "empty",
        }
        assert len(entries) == min(limit, len(allowed))
        assert len({entry.path for entry in entries}) == len(entries)
        assert {entry.path for entry in entries} <= {str(enumeration_tree / name) for name in allowed}

    @pytest.mark.parametrize("options", [{"delimiter": ":"}, {"max_results": -1}])
    def test_enumeration_rejects_unsupported_arguments(self, backend: t.Any, options: dict[str, t.Any]) -> None:
        with pytest.raises(ValueError):
            backend.list_objects("missing", **options)

    def test_enumeration_zero_avoids_native_io(
        self, backend: t.Any, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def unexpected(*args: t.Any, **kwargs: t.Any) -> t.NoReturn:
            raise AssertionError("zero-result enumeration performed native I/O")

        with monkeypatch.context() as patch:
            if isinstance(backend, LocalStorageBackend):
                patch.setattr(os, "stat", unexpected)
                patch.setattr(os, "scandir", unexpected)
            else:
                patch.setattr(backend._get_client(), "stat", unexpected)
                patch.setattr(backend._get_client(), "listdir_attr", unexpected)
            result = backend.list_objects("missing", max_results=0)
        assert result.objects == result.common_prefixes == ()

    @pytest.mark.parametrize("limited", [False, True])
    def test_enumeration_does_not_hide_child_failure_or_traverse_after_limit(
        self, backend: t.Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limited: bool,
    ) -> None:
        (tmp_path / "first").write_bytes(b"first")
        denied = tmp_path / "denied"
        denied.mkdir()
        owner, method = (os, "scandir") if isinstance(backend, LocalStorageBackend) else (
            backend._get_client(), "listdir_attr",
        )
        original = getattr(owner, method)
        fault = PermissionError(errno.EACCES, "denied", str(denied))

        def listing(path: str) -> t.Any:
            if path == str(denied):
                raise fault
            return original(path)

        monkeypatch.setattr(owner, method, listing)
        if limited:
            result = backend.list_objects(str(tmp_path), max_results=1)
            assert [entry.path for entry in result.objects] == [str(tmp_path / "first")]
            assert result.common_prefixes == ()
        else:
            with pytest.raises(PermissionDeniedError) as caught:
                backend.list_objects(str(tmp_path))
            assert caught.value.__cause__ is fault

    @pytest.mark.parametrize("delimiter", [None, "/"])
    def test_enumeration_link_policy(
        self, backend: t.Any, tmp_path: Path, delimiter: str | None,
    ) -> None:
        root = tmp_path / "selected"
        root.mkdir()
        target = tmp_path / "target"
        target.mkdir()
        (target / "payload").write_bytes(b"target")
        (root / "directory-link").symlink_to(target, target_is_directory=True)
        (root / "file-link").symlink_to(target / "payload")
        (root / "broken-link").symlink_to(target / "absent")
        (root / "broken-component-link").symlink_to(target / "payload/child")
        if hasattr(os, "mkfifo"):
            os.mkfifo(root / "fifo")
        result = backend.list_objects(str(root), delimiter=delimiter)
        assert [(entry.path, entry.size) for entry in result.objects] == [(str(root / "file-link"), 6)]
        assert [entry.path for entry in result.common_prefixes] == (
            [str(root / "directory-link")] if delimiter == "/" else []
        )
        selected = backend.list_objects(str(root / "directory-link"), delimiter=delimiter)
        assert [entry.path for entry in selected.objects] == [str(root / "directory-link/payload")]
        assert Path(selected.objects[0].path).read_bytes() == b"target"

    def test_enumeration_preserves_native_relative_alias_parent(
        self, backend: t.Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / "target/inner").mkdir(parents=True)
        (tmp_path / "target/payload").write_bytes(b"right")
        (tmp_path / "payload").write_bytes(b"wrong")
        (tmp_path / "link").symlink_to(tmp_path / "target/inner", target_is_directory=True)
        monkeypatch.chdir(tmp_path)
        result = backend.list_objects("link/../payload")
        expected = os.path.join(str(tmp_path), "link/../payload") if isinstance(
            backend, LocalStorageBackend,
        ) else "link/../payload"
        assert [entry.path for entry in result.objects] == [expected]
        assert Path(result.objects[0].path).read_bytes() == b"right"

    @pytest.mark.parametrize("operation", ["list_dir", "list_objects"])
    def test_enumeration_root_denial_is_not_absence(
        self, backend: t.Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str,
    ) -> None:
        if isinstance(backend, LocalStorageBackend):
            owner, method = os, "stat" if operation == "list_objects" else "scandir"
        else:
            owner, method = backend._get_client(), "stat" if operation == "list_objects" else "listdir_attr"
        native = getattr(owner, method)
        fault = PermissionError(errno.EACCES, "denied")

        def denied(path: t.Any, *args: t.Any, **kwargs: t.Any) -> t.Any:
            if path == str(tmp_path):
                raise fault
            return native(path, *args, **kwargs)

        monkeypatch.setattr(owner, method, denied)
        with pytest.raises(PermissionDeniedError) as caught:
            getattr(backend, operation)(str(tmp_path))
        assert caught.value.__cause__ is fault


@pytest.mark.parametrize("operation, suffix", [
    ("list_objects", "/"), ("list_objects", "/child"),
    ("list_dir", ""), ("list_dir", "/"), ("list_dir", "/child"),
])
def test_sftp_enumeration_recovers_not_directory_status(
    tmp_path: Path, operation: str, suffix: str,
) -> None:
    path = tmp_path / "file"
    path.write_bytes(b"payload")
    native = _FilesystemSFTP()
    client = MagicMock(wraps=native)

    def protocol_call(method: str, name: str) -> t.Any:
        try:
            return getattr(native, method)(name)
        except NotADirectoryError:
            # Paramiko SFTPServer.convert_errno conflates these two errno values.
            raise FileNotFoundError(errno.ENOENT, "No such file") from None

    client.stat.side_effect = lambda name: protocol_call("stat", name)
    client.listdir_attr.side_effect = lambda name: protocol_call("listdir_attr", name)
    backend = SFTPStorageBackend(connection=SimpleNamespace(client=client))
    with pytest.raises(StorageError) as caught:
        getattr(backend, operation)(str(path) + suffix)
    assert not isinstance(caught.value, PathNotFoundError)
    assert isinstance(caught.value.__cause__, NotADirectoryError)


@pytest.mark.parametrize("location", ["root", "entry", "link-target", "ancestor"])
@pytest.mark.parametrize("mode", [None, 0o644])
def test_sftp_enumeration_requires_native_file_type(
    tmp_path: Path, location: str, mode: int | None,
) -> None:
    root = tmp_path / "selected"
    root.mkdir()
    (root / "first").write_bytes(b"valid")
    unknown = root / "unknown"
    unknown.write_bytes(b"unknown")
    link = root / "link"
    link.symlink_to(unknown)
    native = _FilesystemSFTP()
    client = MagicMock(wraps=native)
    affected = str(root if location in ("root", "ancestor") else link if location == "link-target" else unknown)

    def attributes(method: str, path: str) -> SFTPAttributes:
        attrs = getattr(native, method)(path)
        if path == affected:
            attrs.st_mode = mode
        return t.cast(SFTPAttributes, attrs)

    def listing(path: str) -> list[SFTPAttributes]:
        entries = native.listdir_attr(path)
        if location == "entry":
            for attrs in entries:
                if attrs.filename == "unknown":
                    attrs.st_mode = mode
        return entries

    client.stat.side_effect = lambda path: attributes("stat", path)
    client.lstat.side_effect = lambda path: attributes("lstat", path)
    client.listdir_attr.side_effect = listing
    backend = SFTPStorageBackend(connection=SimpleNamespace(client=client))
    selection = str(root / "absent") if location == "ancestor" else str(root)
    with pytest.raises(StorageError) as caught:
        backend.list_objects(selection)
    assert type(caught.value) is StorageError
    assert not isinstance(caught.value.__cause__, TypeError)


def test_sftp_enumeration_recovers_listing_type_and_preserves_links(tmp_path: Path) -> None:
    (tmp_path / "real").mkdir()
    (tmp_path / "real/payload").write_bytes(b"nested")
    (tmp_path / "directory-link").symlink_to(tmp_path / "real", target_is_directory=True)
    (tmp_path / "file-link").symlink_to(tmp_path / "real/payload")
    native = _FilesystemSFTP()
    client = MagicMock(wraps=native)

    def missing_modes(path: str) -> list[SFTPAttributes]:
        entries = native.listdir_attr(path)
        for attrs in entries:
            attrs.st_mode = None
        return entries

    client.listdir_attr.side_effect = missing_modes
    backend = SFTPStorageBackend(connection=SimpleNamespace(client=client))
    result = backend.list_objects(str(tmp_path))
    assert {entry.path for entry in result.objects} == {str(tmp_path / "real/payload"), str(tmp_path / "file-link")}
    assert result.common_prefixes == ()


@pytest.mark.parametrize("fault_at", ["root", "listing", "link-target", "ancestor"])
@pytest.mark.parametrize("fault, expected", [
    (PermissionError(errno.EACCES, "denied"), PermissionDeniedError),
    (EOFError("lost connection"), StorageConnectionError),
    (OSError("Failure"), StorageError),
])
def test_sftp_enumeration_propagates_native_failures(
    tmp_path: Path, fault_at: str, fault: Exception, expected: type[StorageError],
) -> None:
    (tmp_path / "file").write_bytes(b"payload")
    (tmp_path / "link").symlink_to(tmp_path / "file")
    native = _FilesystemSFTP()
    client = MagicMock(wraps=native)
    affected = str(tmp_path / "link") if fault_at == "link-target" else str(tmp_path)

    def fail(path: str) -> SFTPAttributes:
        if path == affected:
            raise fault
        return native.stat(path)

    if fault_at == "listing":
        client.listdir_attr.side_effect = fault
    else:
        client.stat.side_effect = fail
    backend = SFTPStorageBackend(connection=SimpleNamespace(client=client))
    selection = str(tmp_path / "absent") if fault_at == "ancestor" else str(tmp_path)
    with pytest.raises(expected) as caught:
        backend.list_objects(selection)
    assert caught.value.__cause__ is fault


def test_sftp_enumeration_preserves_optional_file_metadata(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_bytes(b"payload")
    attrs = SFTPAttributes.from_stat(path.stat())
    attrs.st_size = attrs.st_mtime = None
    client = MagicMock()
    client.stat.return_value = attrs
    backend = SFTPStorageBackend(connection=SimpleNamespace(client=client))
    result = backend.list_objects(str(path))
    assert [(entry.path, entry.size, entry.last_modified) for entry in result.objects] == [(str(path), None, None)]


@pytest.mark.parametrize("kind", ["broken-link", "broken-component-link", "fifo"])
def test_enumeration_omits_non_file_roots(backend: t.Any, tmp_path: Path, kind: str) -> None:
    path = tmp_path / "selected"
    if kind == "fifo":
        if not hasattr(os, "mkfifo"):
            pytest.skip("native FIFO creation is unavailable")
        os.mkfifo(path)
    else:
        target = tmp_path / "target"
        target.write_bytes(b"file")
        path.symlink_to(tmp_path / "missing" if kind == "broken-link" else target / "child")
    result = backend.list_objects(str(path))
    assert result.objects == result.common_prefixes == ()
