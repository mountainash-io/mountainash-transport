"""LocalMetadataMixin — file metadata operations for local filesystem."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from mountainash_transport._core.dataclasses.file_metadata import FileMetadata


class LocalMetadataMixin:
    """Metadata mixin for local filesystem."""

    def get_metadata(self, path: str) -> FileMetadata:
        """Return FileMetadata for the file at *path*."""
        stat = os.stat(path)
        filename = os.path.basename(path)
        directory = os.path.dirname(os.path.abspath(path))
        last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        return FileMetadata(
            filename=filename,
            directory=directory,
            full_path=os.path.abspath(path),
            size=stat.st_size,
            last_modified=last_modified,
            source="local",
        )

    def path_exists(self, path: str) -> bool:
        """Return True if *path* exists on the local filesystem."""
        return os.path.exists(path)

    def get_size(self, path: str) -> int:
        """Return the size in bytes of the file at *path*."""
        return os.path.getsize(path)
