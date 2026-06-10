"""SFTPReadMixin — read operations for SFTP storage backend."""
from __future__ import annotations

import io
import typing as t

from ._helpers import _wrap_sftp_error


class SFTPReadMixin:
    """Read mixin for SFTP storage backend."""

    def read_to_bytes(self, path: str) -> bytes:
        sftp = self._get_client()  # type: ignore[attr-defined]
        try:
            with sftp.open(path, "rb") as f:
                return f.read()
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

    def read_to_stream(self, path: str) -> t.BinaryIO:
        data = self.read_to_bytes(path)
        return io.BytesIO(data)
