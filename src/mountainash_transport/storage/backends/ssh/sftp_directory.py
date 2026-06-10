"""SFTPDirectoryMixin — directory operations for SFTP storage backend."""
from __future__ import annotations

import stat as stat_module
from datetime import datetime

from mountainash_transport._core.dataclasses.storage_entry import EntryType, StorageEntry

from ._helpers import _wrap_sftp_error


class SFTPDirectoryMixin:
    """Directory mixin for SFTP storage backend."""

    def list_dir(self, path: str) -> list[StorageEntry]:
        sftp = self._get_client()  # type: ignore[attr-defined]
        try:
            entries = sftp.listdir_attr(path)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

        results: list[StorageEntry] = []
        for attr in entries:
            is_dir = stat_module.S_ISDIR(attr.st_mode) if attr.st_mode is not None else False
            mtime = getattr(attr, "st_mtime", None)
            last_modified = None
            if mtime is not None:
                try:
                    last_modified = datetime.fromtimestamp(mtime)
                except (ValueError, OSError):
                    pass
            child_path = f"{path.rstrip('/')}/{attr.filename}"
            results.append(
                StorageEntry(
                    path=child_path,
                    name=attr.filename,
                    size=getattr(attr, "st_size", None) if not is_dir else None,
                    last_modified=last_modified,
                    entry_type=EntryType.DIRECTORY if is_dir else EntryType.FILE,
                    source="sftp",
                )
            )
        return results

    def mkdir(self, path: str, *, parents: bool = True) -> None:
        sftp = self._get_client()  # type: ignore[attr-defined]
        try:
            sftp.mkdir(path)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

    def rmdir(self, path: str) -> None:
        sftp = self._get_client()  # type: ignore[attr-defined]
        try:
            sftp.rmdir(path)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc
