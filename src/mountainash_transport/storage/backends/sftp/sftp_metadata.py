"""SFTPMetadataMixin — metadata operations for SFTP storage backend."""
from __future__ import annotations

from datetime import datetime

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry
from mountainash_transport._core.exceptions import PathNotFoundError

from ._helpers import _mapped


class SFTPMetadataMixin:
    """Metadata mixin for SFTP storage backend."""

    def path_exists(self, path: str) -> bool:
        sftp = self._get_client()  # type: ignore[attr-defined]
        try:
            with _mapped(path):
                sftp.stat(path)
            return True
        except PathNotFoundError:
            return False

    def get_metadata(self, path: str) -> StorageEntry:
        sftp = self._get_client()  # type: ignore[attr-defined]
        with _mapped(path):
            stat = sftp.stat(path)

        name = path.rsplit("/", 1)[-1] if "/" in path else path
        last_modified = None
        mtime = getattr(stat, "st_mtime", None)
        if mtime is not None:
            try:
                last_modified = datetime.fromtimestamp(mtime)
            except (ValueError, OSError):
                pass

        return StorageEntry(
            path=path,
            name=name,
            size=getattr(stat, "st_size", None),
            last_modified=last_modified,
            source="sftp",
        )

    def get_size(self, path: str) -> int | None:
        sftp = self._get_client()  # type: ignore[attr-defined]
        with _mapped(path):
            stat = sftp.stat(path)
            return getattr(stat, "st_size", None)
