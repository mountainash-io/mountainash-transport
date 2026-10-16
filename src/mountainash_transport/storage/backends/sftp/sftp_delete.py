"""SFTPDeleteMixin — delete operations for SFTP storage backend."""
from __future__ import annotations

from ._helpers import _mapped


class SFTPDeleteMixin:
    """Delete mixin for SFTP storage backend."""

    def delete_file(self, path: str) -> None:
        sftp = self._get_client()  # type: ignore[attr-defined]
        with _mapped(path):
            sftp.remove(path)
