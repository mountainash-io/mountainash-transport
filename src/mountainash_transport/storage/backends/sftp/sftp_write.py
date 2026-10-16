"""SFTPWriteMixin — write operations for SFTP storage backend."""
from __future__ import annotations

import typing as t

from ._helpers import _mapped


class SFTPWriteMixin:
    """Write mixin for SFTP storage backend."""

    def write_from_bytes(self, path: str, data: bytes) -> None:
        sftp = self._get_client()  # type: ignore[attr-defined]
        with _mapped(path), sftp.open(path, "wb") as f:
            f.write(data)

    def write_from_stream(self, path: str, stream: t.BinaryIO) -> None:
        self.write_from_bytes(path, stream.read())
