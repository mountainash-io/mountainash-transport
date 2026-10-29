"""LocalMetadataMixin — file metadata operations for local filesystem."""
from __future__ import annotations

import os
import stat as stat_module
from datetime import datetime, timezone

from mountainash_transport._core.dataclasses.storage_entry import EntryType, StorageEntry

from ._helpers import _mapped


class LocalMetadataMixin:
    """Metadata mixin for local filesystem."""

    def get_metadata(self, path: str) -> StorageEntry:
        with _mapped(path):
            stat = os.stat(path)
        last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        return StorageEntry(
            path=os.path.abspath(path),
            name=os.path.basename(path),
            size=stat.st_size,
            last_modified=last_modified,
            entry_type=EntryType.DIRECTORY if stat_module.S_ISDIR(stat.st_mode) else EntryType.FILE,
            storage_class="local",
            source="local",
        )

    def path_exists(self, path: str) -> bool:
        with _mapped(path):
            try:
                os.stat(path)
            except (FileNotFoundError, NotADirectoryError):
                return False
        return True

    def get_size(self, path: str) -> int | None:
        with _mapped(path):
            return os.stat(path).st_size
