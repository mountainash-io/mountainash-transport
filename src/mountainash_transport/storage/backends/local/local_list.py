"""LocalListMixin — directory listing for local filesystem using StorageEntry."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from mountainash_transport._core.dataclasses.storage_entry import (
    EntryType,
    StorageEntry,
)


class LocalListMixin:
    """List mixin for local filesystem — implements list_dir."""

    def list_dir(self, path: str) -> list[StorageEntry]:
        """Return StorageEntry for every immediate child of *path*.

        Symlinks are resolved via stat(). Broken symlinks are skipped.
        """
        results: list[StorageEntry] = []
        if not os.path.isdir(path):
            return results

        for entry in os.scandir(path):
            try:
                is_dir = entry.is_dir(follow_symlinks=True)
                is_file = entry.is_file(follow_symlinks=True)
            except OSError:
                continue

            if not is_dir and not is_file:
                continue

            stat = entry.stat(follow_symlinks=True)
            results.append(
                StorageEntry(
                    path=os.path.abspath(entry.path),
                    name=entry.name,
                    size=stat.st_size if is_file else None,
                    last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                    entry_type=EntryType.DIRECTORY if is_dir else EntryType.FILE,
                    source="local",
                )
            )
        return results
