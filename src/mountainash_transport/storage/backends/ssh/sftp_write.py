"""SFTPWriteMixin — write operations for SFTP storage backend."""
from __future__ import annotations

import typing as t

from ._helpers import _wrap_sftp_error


class SFTPWriteMixin:
    """Write mixin for SFTP storage backend."""

    def write_from_bytes(self, path: str, data: bytes) -> None:
        sftp = self._get_client()  # type: ignore[attr-defined]
        try:
            with sftp.open(path, "wb") as f:
                f.write(data)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

    def write_from_stream(self, path: str, stream: t.BinaryIO) -> None:
        self.write_from_bytes(path, stream.read())
