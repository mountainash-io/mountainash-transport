"""SFTPWriteMixin — write operations for SFTP storage backend."""
from __future__ import annotations

import posixpath
import typing as t

from ._helpers import _mapped


class SFTPWriteMixin:
    """Write mixin for SFTP storage backend."""

    def write_from_bytes(self, path: str, data: bytes, *, create_parents: bool = True) -> None:
        """Write bytes, optionally creating remote parent directories."""
        parent = posixpath.dirname(path)
        if create_parents and parent:
            self.mkdir(parent, parents=True)  # type: ignore[attr-defined]
        sftp = self._get_client()  # type: ignore[attr-defined]
        with _mapped(path), sftp.open(path, "wb") as f:
            f.write(data)

    def write_from_stream(self, path: str, stream: t.BinaryIO, *, create_parents: bool = True) -> None:
        """Write a stream with the same parent policy as byte writes."""
        self.write_from_bytes(path, stream.read(), create_parents=create_parents)
