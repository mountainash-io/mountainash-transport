"""LocalReadMixin — read operations for local filesystem."""

from __future__ import annotations

from typing import BinaryIO


class LocalReadMixin:
    """Read mixin for local filesystem."""

    def read_to_bytes(self, path: str) -> bytes:
        """Read the contents of a local file and return as bytes."""
        with open(path, "rb") as fh:
            return fh.read()

    def read_to_stream(self, path: str) -> BinaryIO:
        """Open a local file and return a binary read stream."""
        return open(path, "rb")  # noqa: SIM115 — caller is responsible for closing
