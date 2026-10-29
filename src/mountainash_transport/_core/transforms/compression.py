"""Gzip compression / decompression transform."""

from __future__ import annotations

import gzip
import io
from typing import BinaryIO, cast

from ._stream_encoder import GzipCompressingReader
from .base import StreamTransform
from mountainash_transport._core.exceptions import TransformError
from mountainash_transport._core.sequential_io import ForwardOnlyReader

DEFAULT_MAX_DECOMPRESSED_BYTES = 1024**3  # 1 GiB
_CHUNK = 64 * 1024


class _BoundedGzipFile(gzip.GzipFile):
    """GzipFile that raises once the decoded position passes *limit*.

    Every read path is capped at ``limit + 1`` bytes past the current position,
    so a hostile payload never allocates more than the limit before failing.
    """

    def __init__(self, *, fileobj: BinaryIO, limit: int) -> None:
        super().__init__(fileobj=fileobj, mode="rb")
        self._limit = limit

    def _pos(self) -> int:
        # GzipFile.tell() delegates to self.seek(0, SEEK_CUR); bypass our override.
        return super().seek(0, io.SEEK_CUR)

    def _cap(self, size: int | None) -> int:
        room = self._limit - self._pos() + 1
        return room if size is None or size < 0 else min(size, room)

    def _check(self) -> None:
        if self._pos() > self._limit:
            raise TransformError(
                f"gzip: decompressed size exceeds max_decompressed_bytes={self._limit}; "
                "pass Gzip(max_decompressed_bytes=...) to raise it for trusted data"
            )

    def read(self, size: int | None = -1) -> bytes:
        if size is not None and size >= 0:
            data = super().read(self._cap(size))
            self._check()
            return data
        out = bytearray()
        while chunk := super().read(min(_CHUNK, self._cap(-1))):
            out += chunk
            self._check()
        return bytes(out)

    def read1(self, size: int = -1) -> bytes:
        data = super().read1(self._cap(size))
        self._check()
        return data

    def readline(self, size: int | None = -1) -> bytes:
        data = super().readline(self._cap(size))
        self._check()
        return data

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        pos = super().seek(offset, whence)
        self._check()
        return pos


class Gzip(StreamTransform):
    """Gzip transform — compresses on wrap, decompresses on unwrap.

    Uses Python stdlib — no external dependency required.

    Args:
        level: Compression level 1-9. Default 6 (stdlib default).
        mtime: Fixed mtime in the gzip header. Default 0 (reproducible output).
            Pass None to use the current time (stdlib default behaviour).
        max_decompressed_bytes: Upper bound on decoded bytes when unwrapping
            (default 1 GiB). Reading or seeking past it raises
            ``TransformError`` before the excess is allocated, guarding against
            decompression bombs. ``None`` disables the bound for trusted data.
    """

    def __init__(
        self,
        level: int = 6,
        mtime: int | None = 0,
        max_decompressed_bytes: int | None = DEFAULT_MAX_DECOMPRESSED_BYTES,
    ) -> None:
        self.level = level
        self.mtime = mtime
        self.max_decompressed_bytes = max_decompressed_bytes

    def wrap(self, stream: BinaryIO) -> BinaryIO:
        """Wrap *stream* so reads yield gzip-encoded bytes."""
        # RawIOBase reader exposing the binary-stream interface; typeshed's
        # BinaryIO is nominal, so the adapter is not a declared subclass.
        return cast(BinaryIO, GzipCompressingReader(stream, level=self.level, mtime=self.mtime))

    def unwrap(self, stream: BinaryIO) -> BinaryIO:
        """Unwrap *stream* so reads yield gzip-decoded (plaintext) bytes."""
        if self.max_decompressed_bytes is None:
            decoded = gzip.GzipFile(fileobj=stream, mode="rb")
        else:
            decoded = _BoundedGzipFile(fileobj=stream, limit=self.max_decompressed_bytes)
        if stream.seekable():
            return cast(BinaryIO, decoded)
        return cast(BinaryIO, io.BufferedReader(ForwardOnlyReader(decoded.read, decoded.close)))
