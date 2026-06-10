"""SFTPDeleteMixin — delete operations for SFTP storage backend."""
from __future__ import annotations

from ._helpers import _wrap_sftp_error


class SFTPDeleteMixin:
    """Delete mixin for SFTP storage backend."""

    def delete_file(self, path: str) -> None:
        sftp = self._get_client()  # type: ignore[attr-defined]
        try:
            sftp.remove(path)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc
