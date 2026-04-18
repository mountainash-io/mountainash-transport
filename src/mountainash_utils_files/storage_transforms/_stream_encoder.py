"""Internal helpers: BinaryIO-compatible reader adapters for streaming codecs."""

from __future__ import annotations

import io
import struct
import time
import zlib
from typing import BinaryIO

_DEFAULT_CHUNK = 64 * 1024


class GzipCompressingReader(io.RawIOBase):
    """Read-side adapter that gzips source bytes on demand.

    Produces a gzip member (header + deflate stream + trailer) compliant with
    RFC 1952. Uses a fixed mtime when provided (default 0) so identical input
    yields byte-identical output.
    """

    def __init__(
        self,
        source: BinaryIO,
        level: int = 6,
        mtime: int | None = 0,
        chunk_size: int = _DEFAULT_CHUNK,
    ) -> None:
        self._source = source
        self._chunk_size = chunk_size
        self._buffer = bytearray()
        self._source_exhausted = False
        self._trailer_emitted = False
        self._header_emitted = False
        self._crc = 0
        self._size = 0
        self._mtime = int(time.time()) if mtime is None else mtime
        # zlib.compressobj with wbits=-zlib.MAX_WBITS produces raw deflate
        # (no zlib header / trailer), which is what gzip wraps.
        self._compressor = zlib.compressobj(
            level, zlib.DEFLATED, -zlib.MAX_WBITS, zlib.DEF_MEM_LEVEL, 0,
        )

    def readable(self) -> bool:
        return True

    def readinto(self, b) -> int:  # type: ignore[override]
        while len(self._buffer) < len(b) and not self._trailer_emitted:
            self._fill()
        n = min(len(b), len(self._buffer))
        b[:n] = self._buffer[:n]
        del self._buffer[:n]
        return n

    def close(self) -> None:
        try:
            self._source.close()
        finally:
            super().close()

    def _fill(self) -> None:
        if not self._header_emitted:
            self._buffer.extend(_gzip_header(self._mtime))
            self._header_emitted = True
            # Fall through to read the first source chunk immediately — without this,
            # a small readinto(N) (N <= header size) would return entirely from the
            # buffered header without ever touching the source, breaking the laziness
            # contract asserted by test_gzip_wrap_is_lazy.
        if not self._source_exhausted:
            chunk = self._source.read(self._chunk_size)
            if chunk:
                self._crc = zlib.crc32(chunk, self._crc) & 0xFFFFFFFF
                self._size = (self._size + len(chunk)) & 0xFFFFFFFF
                self._buffer.extend(self._compressor.compress(chunk))
                return
            self._source_exhausted = True
        if not self._trailer_emitted:
            self._buffer.extend(self._compressor.flush(zlib.Z_FINISH))
            self._buffer.extend(struct.pack("<II", self._crc, self._size))
            self._trailer_emitted = True


def _gzip_header(mtime: int) -> bytes:
    """RFC 1952 minimal gzip header."""
    return struct.pack(
        "<BBBBIBB",
        0x1F, 0x8B,       # magic
        0x08,             # compression method (deflate)
        0x00,             # flags
        mtime & 0xFFFFFFFF,
        0x00,             # extra flags
        0xFF,             # OS: unknown
    )
