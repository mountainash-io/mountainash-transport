"""LocalMetadataMixin — file metadata operations for local filesystem."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry


class LocalMetadataMixin:
    """Metadata mixin for local filesystem."""

    def get_metadata(self, path: str) -> StorageEntry:
        stat = os.stat(path)
        last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        return StorageEntry(
            path=os.path.abspath(path),
            name=os.path.basename(path),
            size=stat.st_size,
            last_modified=last_modified,
            storage_class="local",
            source="local",
        )

    def path_exists(self, path: str) -> bool:
        return os.path.exists(path)

    def get_size(self, path: str) -> int | None:
        try:
            return os.path.getsize(path)
        except OSError:
            return None
