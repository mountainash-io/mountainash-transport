"""Exact-path enumeration over the borrowed SFTP client."""
from __future__ import annotations

import posixpath
import stat
import typing as t
from datetime import datetime, timezone

from mountainash_transport._core.dataclasses.storage_entry import EnumerateResult, EntryType, StorageEntry

from ._helpers import _check_not_directory, _is_not_found, _mapped, _require_file_type

if t.TYPE_CHECKING:
    from paramiko import SFTPAttributes


def _entry(path: str, attrs: SFTPAttributes, kind: EntryType) -> StorageEntry:
    return StorageEntry(
        path=path,
        name=posixpath.basename(path),
        entry_type=kind,
        size=attrs.st_size if kind == EntryType.FILE else None,
        last_modified=(
            datetime.fromtimestamp(attrs.st_mtime, tz=timezone.utc) if attrs.st_mtime is not None else None
        ),
        source="sftp",
    )


class SFTPEnumerateMixin:
    """Enumerate files without following discovered directory links."""

    def list_objects(
        self, prefix: str, *, delimiter: str | None = None, max_results: int | None = None,
    ) -> EnumerateResult:
        """Select an exact remote path, preserving its relative/absolute form."""
        if delimiter not in (None, "/"):
            raise ValueError("SFTP enumeration supports only None or '/' as delimiter")
        if max_results is not None and max_results < 0:
            raise ValueError("max_results must be nonnegative")
        objects: list[StorageEntry] = []
        prefixes: list[StorageEntry] = []

        def full() -> bool:
            return max_results is not None and len(objects) + len(prefixes) >= max_results

        if full():
            return EnumerateResult((), ())
        client = self._get_client()  # type: ignore[attr-defined]
        with _mapped(prefix):
            try:
                attrs = client.stat(prefix)
            except OSError as error:
                if not _is_not_found(error):
                    raise
                _check_not_directory(client, prefix)
                return EnumerateResult((), ())
            kind = _require_file_type(attrs.st_mode, prefix)
            if kind == stat.S_IFREG:
                return EnumerateResult((_entry(prefix, attrs, EntryType.FILE),), ())
            pending = [prefix] if kind == stat.S_IFDIR else []
            while pending and not full():
                directory = pending.pop()
                for attrs in client.listdir_attr(directory):
                    path = posixpath.join(directory, attrs.filename)
                    if attrs.st_mode is None or not stat.S_IFMT(attrs.st_mode):
                        attrs = client.lstat(path)
                    kind = _require_file_type(attrs.st_mode, path)
                    linked = kind == stat.S_IFLNK
                    if linked:
                        try:
                            attrs = client.stat(path)
                        except OSError as error:
                            if _is_not_found(error):
                                continue
                            raise
                        kind = _require_file_type(attrs.st_mode, path)
                    if kind == stat.S_IFREG:
                        objects.append(_entry(path, attrs, EntryType.FILE))
                    elif kind == stat.S_IFDIR:
                        if delimiter == "/":
                            prefixes.append(_entry(path, attrs, EntryType.PREFIX))
                        elif not linked:
                            pending.append(path)
                    if full():
                        break
        return EnumerateResult(tuple(objects), tuple(prefixes))
