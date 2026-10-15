"""Gzip compression / decompression transform."""

from __future__ import annotations

import gzip
import io
from typing import BinaryIO, cast

from ._stream_encoder import GzipCompressingReader
from .base import StreamTransform
from mountainash_transport._core.sequential_io import ForwardOnlyReader


class Gzip(StreamTransform):
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
        # RawIOBase reader exposing the binary-stream interface; typeshed's
        # BinaryIO is nominal, so the adapter is not a declared subclass.
        return cast(BinaryIO, GzipCompressingReader(stream, level=self.level, mtime=self.mtime))

    def unwrap(self, stream: BinaryIO) -> BinaryIO:
        """Unwrap *stream* so reads yield gzip-decoded (plaintext) bytes."""
        decoded = gzip.GzipFile(fileobj=stream, mode="rb")
        if stream.seekable():
            return cast(BinaryIO, decoded)
        return cast(BinaryIO, io.BufferedReader(ForwardOnlyReader(decoded.read, decoded.close)))
