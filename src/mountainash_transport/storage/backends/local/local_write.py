"""LocalWriteMixin — write operations for local filesystem."""

from __future__ import annotations

import os
from typing import BinaryIO

_CHUNK_SIZE = 65_536  # 64 KiB


class LocalWriteMixin:
    """Write mixin for local filesystem."""

    def write_from_bytes(self, path: str, data: bytes) -> None:
        """Write bytes to a local file, creating parent directories as needed."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)

    def write_from_stream(self, path: str, stream: BinaryIO) -> None:
        """Write data from a binary stream to a local file in chunks.

        Parent directories are created as needed.
        """
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "wb") as fh:
            while True:
                chunk = stream.read(_CHUNK_SIZE)
                if not chunk:
                    break
                fh.write(chunk)
