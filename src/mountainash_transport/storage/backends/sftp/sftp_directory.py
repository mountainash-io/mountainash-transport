"""SFTPDirectoryMixin — directory operations for SFTP storage backend."""
from __future__ import annotations

import errno
import posixpath
import stat as stat_module
from datetime import datetime, timezone

from mountainash_transport._core.dataclasses.storage_entry import EntryType, StorageEntry

from ._helpers import _is_not_found, _mapped


class SFTPDirectoryMixin:
    """Directory mixin for SFTP storage backend."""

    def list_dir(self, path: str) -> list[StorageEntry]:
        sftp = self._get_client()  # type: ignore[attr-defined]
        with _mapped(path):
            entries = sftp.listdir_attr(path)

        results: list[StorageEntry] = []
        for attr in entries:
            is_dir = stat_module.S_ISDIR(attr.st_mode) if attr.st_mode is not None else False
            mtime = getattr(attr, "st_mtime", None)
            last_modified = None
            if mtime is not None:
                try:
                    last_modified = datetime.fromtimestamp(mtime, tz=timezone.utc)
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
        with _mapped(path):
            if not parents or not path:
                sftp.mkdir(path)
                return

            # Keep remote spelling, especially symlink/.. traversal. Do not chdir.
            paths = [path]
            parent = posixpath.dirname(path.rstrip("/"))
            while parent and parent != paths[-1]:
                paths.append(parent)
                parent = posixpath.dirname(parent)
            for directory in reversed(paths):
                try:
                    attrs = sftp.stat(directory)
                except OSError as error:
                    if not _is_not_found(error):
                        raise
                else:
                    if attrs.st_mode is None:
                        # Missing ancestor modes must not prevent native creation.
                        if directory != path:
                            continue
                    elif stat_module.S_ISDIR(attrs.st_mode):
                        continue
                    else:
                        raise NotADirectoryError(errno.ENOTDIR, "Not a directory", directory)

                try:
                    sftp.mkdir(directory)
                except OSError as error:
                    # SFTP v3 may return generic FAILURE rather than EEXIST.
                    # Typed transport/auth failures are never race evidence.
                    if type(error) is not OSError and not isinstance(error, FileExistsError):
                        raise
                    if error.errno not in (None, errno.EEXIST):
                        raise
                    try:
                        attrs = sftp.stat(directory)
                    except OSError:
                        raise error
                    if attrs.st_mode is None or not stat_module.S_ISDIR(attrs.st_mode):
                        raise

    def rmdir(self, path: str) -> None:
        sftp = self._get_client()  # type: ignore[attr-defined]
        with _mapped(path):
            sftp.rmdir(path)
