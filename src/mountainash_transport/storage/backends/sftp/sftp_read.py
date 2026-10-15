"""SFTPReadMixin — read operations for SFTP storage backend."""
from __future__ import annotations

import io
import typing as t

from ._helpers import _wrap_sftp_error
from mountainash_transport._core.ranged_io import RangedSource
from mountainash_transport._core.sequential_io import ForwardOnlyReader


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
        """Return demand-driven forward-only reads; no unbounded prefetch."""
        sftp = self._get_client()  # type: ignore[attr-defined]
        try:
            handle = sftp.open(path, "rb")
        except OSError as exc:
            raise _wrap_sftp_error(exc, path) from exc
        return t.cast(t.BinaryIO, io.BufferedReader(ForwardOnlyReader(
            handle.read, handle.close,
            lambda exc: _wrap_sftp_error(exc, path) if isinstance(exc, OSError) else None,
        )))

    def open_ranged(self, path: str) -> RangedSource:
        """Open a native remote file without prefetch or version pinning."""
        sftp = self._get_client()  # type: ignore[attr-defined]
        try:
            handle = sftp.open(path, "rb")
        except OSError as exc:
            raise _wrap_sftp_error(exc, path) from exc
        try:
            size = int(handle.stat().st_size)
        except BaseException as exc:
            handle.close()
            if isinstance(exc, OSError):
                raise _wrap_sftp_error(exc, path) from exc
            raise

        def fetch(start: int, end: int) -> bytes:
            try:
                handle.seek(start)
                return handle.read(end - start)
            except OSError as exc:
                raise _wrap_sftp_error(exc, path) from exc

        return RangedSource(size, fetch, handle.close)
