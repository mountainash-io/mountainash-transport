"""SFTPDeleteMixin — delete operations for SFTP storage backend."""
from __future__ import annotations

import typing as t

from .._delete_many import delete_each
from ._helpers import _mapped, _remote_path


class SFTPDeleteMixin:
    """Delete mixin for SFTP storage backend."""

    def delete_file(self, path: str) -> None:
        path = _remote_path(self.storage_profile, path)  # type: ignore[attr-defined]
        sftp = self._get_client()  # type: ignore[attr-defined]
        with _mapped(path):
            sftp.remove(path)

    def delete_many(self, paths: t.Iterable[str]) -> None:
        """Delete every path, one SFTP remove each (SFTP has no batch delete); missing paths count as deleted.

        Each remove goes through ``delete_file``, so it keeps the backend's per-call retry.
        """
        delete_each(self.delete_file, paths)
