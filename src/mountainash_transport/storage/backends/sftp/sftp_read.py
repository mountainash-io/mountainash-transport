"""SFTPReadMixin — read operations for SFTP storage backend."""
from __future__ import annotations

import io
import typing as t

from ._helpers import _mapped, _remote_path, _wrap_sftp_error
from mountainash_transport._core.ranged_io import RangedSource
from mountainash_transport._core.sequential_io import ForwardOnlyReader


class SFTPReadMixin:
    """Read mixin for SFTP storage backend."""

    def read_to_bytes(self, path: str) -> bytes:
        path = _remote_path(self.storage_profile, path)  # type: ignore[attr-defined]
        sftp = self._get_client()  # type: ignore[attr-defined]
        with _mapped(path), sftp.open(path, "rb") as f:
            return f.read()

    def read_to_stream(self, path: str) -> t.BinaryIO:
        """Return demand-driven forward-only reads; no unbounded prefetch."""
        path = _remote_path(self.storage_profile, path)  # type: ignore[attr-defined]
        sftp = self._get_client()  # type: ignore[attr-defined]
        with _mapped(path):
            handle = sftp.open(path, "rb")
        return t.cast(t.BinaryIO, io.BufferedReader(ForwardOnlyReader(
            handle.read, handle.close,
            lambda exc: _wrap_sftp_error(exc, path),
        )))

    def open_ranged(self, path: str) -> RangedSource:
        """Open a native remote file without prefetch or version pinning."""
        path = _remote_path(self.storage_profile, path)  # type: ignore[attr-defined]
        sftp = self._get_client()  # type: ignore[attr-defined]
        with _mapped(path):
            handle = sftp.open(path, "rb")

        def close() -> None:
            with _mapped(path):
                handle.close()

        try:
            with _mapped(path):
                size = int(handle.stat().st_size)
        except BaseException:
            close()
            raise

        def fetch(start: int, end: int) -> bytes:
            with _mapped(path):
                handle.seek(start)
                return handle.read(end - start)

        return RangedSource(size, fetch, close)
