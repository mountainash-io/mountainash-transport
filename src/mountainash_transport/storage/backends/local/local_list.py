"""LocalListMixin — directory listing operations for local filesystem."""

from __future__ import annotations

import os

from mountainash_transport._core.dataclasses.file_metadata import FileMetadata


class LocalListMixin:
    """List mixin for local filesystem."""

    def list_files(self, prefix: str) -> list[FileMetadata]:
        """Return FileMetadata for every regular file directly under *prefix*.

        Only the immediate contents of the directory are returned (non-recursive).
        """
        results: list[FileMetadata] = []
        if not os.path.isdir(prefix):
            return results

        for entry in os.scandir(prefix):
            if entry.is_file(follow_symlinks=False):
                stat = entry.stat()
                results.append(
                    FileMetadata(
                        filename=entry.name,
                        directory=prefix,
                        full_path=entry.path,
                        size=stat.st_size,
                        source="local",
                    )
                )
        return results

    def list_directories(self, prefix: str) -> list[str]:
        """Return absolute paths of all sub-directories directly under *prefix*."""
        results: list[str] = []
        if not os.path.isdir(prefix):
            return results

        for entry in os.scandir(prefix):
            if entry.is_dir(follow_symlinks=False):
                results.append(entry.path)
        return results
