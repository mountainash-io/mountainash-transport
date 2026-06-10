"""SFTPMetadataMixin — metadata operations for SFTP storage backend."""
from __future__ import annotations

from datetime import datetime

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry

from ._helpers import _wrap_sftp_error


class SFTPMetadataMixin:
    """Metadata mixin for SFTP storage backend."""

    def path_exists(self, path: str) -> bool:
        sftp = self._get_client()  # type: ignore[attr-defined]
        try:
            sftp.stat(path)
            return True
        except (FileNotFoundError, IOError):
            return False

    def get_metadata(self, path: str) -> StorageEntry:
        sftp = self._get_client()  # type: ignore[attr-defined]
        try:
            stat = sftp.stat(path)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

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
        try:
            stat = sftp.stat(path)
            return getattr(stat, "st_size", None)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc
