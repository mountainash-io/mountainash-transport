"""Gzip compression / decompression transform."""

from __future__ import annotations

import gzip
from typing import BinaryIO

from ._stream_encoder import GzipCompressingReader


class Gzip:
    """Gzip transform — compresses on wrap, decompresses on unwrap.

    Uses Python stdlib — no external dependency required.

    Args:
        level: Compression level 1-9. Default 6 (stdlib default).
        mtime: Fixed mtime in the gzip header. Default 0 (reproducible output).
            Pass None to use the current time (stdlib default behaviour).
    """

    def __init__(self, level: int = 6, mtime: int | None = 0) -> None:
        self.level = level
        self.mtime = mtime

    def wrap(self, stream: BinaryIO) -> BinaryIO:
        """Wrap *stream* so reads yield gzip-encoded bytes."""
        return GzipCompressingReader(stream, level=self.level, mtime=self.mtime)

    def unwrap(self, stream: BinaryIO) -> BinaryIO:
        """Wrap *stream* so reads yield gzip-decoded (plaintext) bytes."""
        # gzip.GzipFile in rb mode consumes the source lazily on .read().
        return gzip.GzipFile(fileobj=stream, mode="rb")  # type: ignore[return-value]
