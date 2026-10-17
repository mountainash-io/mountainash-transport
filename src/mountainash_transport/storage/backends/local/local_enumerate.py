"""Exact-path enumeration using native filesystem metadata and traversal."""
from __future__ import annotations

import os
import stat
from datetime import datetime, timezone

from mountainash_transport._core.dataclasses.storage_entry import EnumerateResult, EntryType, StorageEntry

from ._helpers import _mapped


def _entry(path: str, attrs: os.stat_result, kind: EntryType) -> StorageEntry:
    return StorageEntry(
        path=path,
        name=os.path.basename(path),
        entry_type=kind,
        size=attrs.st_size if kind == EntryType.FILE else None,
        last_modified=datetime.fromtimestamp(attrs.st_mtime, tz=timezone.utc),
        source="local",
    )


class LocalEnumerateMixin:
    """Enumerate a selected file or the files beneath a selected directory."""

    def list_objects(
        self, prefix: str, *, delimiter: str | None = None, max_results: int | None = None,
    ) -> EnumerateResult:
        """Select an exact path; group immediate directories with delimiter `/`."""
        if delimiter not in (None, "/"):
            raise ValueError("Local enumeration supports only None or '/' as delimiter")
        if max_results is not None and max_results < 0:
            raise ValueError("max_results must be nonnegative")
        objects: list[StorageEntry] = []
        prefixes: list[StorageEntry] = []

        def full() -> bool:
            return max_results is not None and len(objects) + len(prefixes) >= max_results

        if full():
            return EnumerateResult((), ())
        with _mapped(prefix):
            try:
                attrs = os.stat(prefix)
            except FileNotFoundError:
                return EnumerateResult((), ())
            # Anchor relative paths without collapsing native symlink/.. traversal.
            drive, tail = os.path.splitdrive(prefix)
            root = os.path.join(os.path.abspath(drive or os.curdir), tail)
            if stat.S_ISREG(attrs.st_mode):
                return EnumerateResult((_entry(root, attrs, EntryType.FILE),), ())
            pending = [root] if stat.S_ISDIR(attrs.st_mode) else []
            while pending and not full():
                with os.scandir(pending.pop()) as entries:
                    for child in entries:
                        linked = child.is_symlink()
                        try:
                            attrs = child.stat()
                        except FileNotFoundError:
                            if linked:
                                continue
                            raise
                        if stat.S_ISREG(attrs.st_mode):
                            objects.append(_entry(child.path, attrs, EntryType.FILE))
                        elif stat.S_ISDIR(attrs.st_mode):
                            if delimiter == "/":
                                prefixes.append(_entry(child.path, attrs, EntryType.PREFIX))
                            elif not linked and not os.path.isjunction(child.path):
                                pending.append(child.path)
                        if full():
                            break
        return EnumerateResult(tuple(objects), tuple(prefixes))
