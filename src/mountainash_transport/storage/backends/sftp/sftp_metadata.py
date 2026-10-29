"""SFTPMetadataMixin — metadata operations for SFTP storage backend."""
from __future__ import annotations

import stat as stat_module
from datetime import datetime, timezone

from mountainash_transport._core.dataclasses.storage_entry import EntryType, StorageEntry
from mountainash_transport._core.exceptions import PathNotFoundError

from ._helpers import _mapped, _remote_path


class SFTPMetadataMixin:
    """Metadata mixin for SFTP storage backend."""

    def path_exists(self, path: str) -> bool:
        path = _remote_path(self.storage_profile, path)  # type: ignore[attr-defined]
        sftp = self._get_client()  # type: ignore[attr-defined]
        try:
            with _mapped(path):
                sftp.stat(path)
            return True
        except PathNotFoundError:
            return False

    def get_metadata(self, path: str) -> StorageEntry:
        path = _remote_path(self.storage_profile, path)  # type: ignore[attr-defined]
        sftp = self._get_client()  # type: ignore[attr-defined]
        with _mapped(path):
            stat = sftp.stat(path)

        name = path.rsplit("/", 1)[-1] if "/" in path else path
        last_modified = None
        mtime = getattr(stat, "st_mtime", None)
        if mtime is not None:
            try:
                last_modified = datetime.fromtimestamp(mtime, tz=timezone.utc)
            except (ValueError, OSError):
                pass

        mode = getattr(stat, "st_mode", None)
        is_dir = mode is not None and stat_module.S_ISDIR(mode)
        return StorageEntry(
            path=path,
            name=name,
            size=getattr(stat, "st_size", None),
            last_modified=last_modified,
            entry_type=EntryType.DIRECTORY if is_dir else EntryType.FILE,
            source="sftp",
        )

    def get_size(self, path: str) -> int | None:
        path = _remote_path(self.storage_profile, path)  # type: ignore[attr-defined]
        sftp = self._get_client()  # type: ignore[attr-defined]
        with _mapped(path):
            stat = sftp.stat(path)
            return getattr(stat, "st_size", None)
