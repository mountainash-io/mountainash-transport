"""SFTPMoveMixin — rename for the SFTP storage backend."""
from __future__ import annotations

import posixpath

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry

from ._helpers import _mapped, _remote_path
from .sftp_metadata import entry_from_attrs


class SFTPMoveMixin:
    """Move mixin for SFTP storage backend."""

    def move(self, source: str, destination: str, *, create_parents: bool = True) -> StorageEntry:
        """Rename with ``posix-rename@openssh.com``, replacing an existing destination.

        A server without that OpenSSH extension raises ``StorageError``: plain
        SFTP rename refuses an existing destination, so it is not used as a
        silent substitute. The rename returns nothing, so one ``lstat`` of the
        destination supplies the returned entry; a moved symlink is described
        as the link.
        """
        source = _remote_path(self.storage_profile, source)  # type: ignore[attr-defined]
        destination = _remote_path(self.storage_profile, destination)  # type: ignore[attr-defined]
        parent = posixpath.dirname(destination)
        if parent:
            if create_parents:
                self.mkdir(parent, parents=True)  # type: ignore[attr-defined]
            else:
                with _mapped(parent):
                    self._get_client().stat(parent)  # type: ignore[attr-defined]  # missing parent reported as itself
        sftp = self._get_client()  # type: ignore[attr-defined]  # after mkdir, which may have reconnected
        with _mapped(source):
            sftp.posix_rename(source, destination)
        with _mapped(destination):
            return entry_from_attrs(destination, sftp.lstat(destination))
