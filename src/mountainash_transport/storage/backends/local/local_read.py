"""LocalReadMixin — read operations for local filesystem."""

from __future__ import annotations

import typing as t

from ._helpers import _mapped
from ._io import _LocalReader


class LocalReadMixin:
    """Read mixin for local filesystem."""

    def read_to_bytes(self, path: str) -> bytes:
        """Read the contents of a local file and return as bytes."""
        with _mapped(path), open(path, "rb") as fh:
            return fh.read()

    def read_to_stream(self, path: str) -> t.BinaryIO:
        """Open a native-backed seekable binary reader with deferred mapping."""
        with _mapped(path):
            source = open(path, "rb")  # noqa: SIM115 — transferred to the reader
        return t.cast(t.BinaryIO, _LocalReader(source, path))
