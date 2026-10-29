"""Pipeline — ordered stack of stream transforms."""

from __future__ import annotations

import contextlib
import io
import typing as t
from typing import BinaryIO

from .base import StreamTransform


def _close_if_open(stream: BinaryIO) -> None:
    """Avoid re-closing layers already closed by another transform."""
    if not stream.closed:
        stream.close()


class _ReadStream(io.RawIOBase):
    """Delegate decoded reads while owning a LIFO stack of close callbacks."""

    def __init__(self, wrapped: BinaryIO, cleanup: contextlib.ExitStack) -> None:
        self._wrapped = wrapped
        self._cleanup = cleanup

    def readable(self) -> bool:
        return True

    def readinto(self, b: t.Any) -> int:
        chunk = self.read(len(b))
        b[:len(chunk)] = chunk
        return len(chunk)

    def read(self, size: int = -1) -> bytes:
        if self.closed:
            raise ValueError("I/O operation on closed file")
        return self._wrapped.read(size)

    def seekable(self) -> bool:
        return self._wrapped.seekable()

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if not self._wrapped.seekable():
            raise io.UnsupportedOperation("seek")
        return self._wrapped.seek(offset, whence)

    def tell(self) -> int:
        if not self._wrapped.seekable():
            raise io.UnsupportedOperation("tell")
        return self._wrapped.tell()

    def close(self) -> None:
        if not self.closed:
            try:
                self._cleanup.close()
            finally:
                super().close()


class Pipeline:
    """Ordered stack of transforms representing the layering as stored on disk.

    Transforms are listed OUTERMOST-FIRST — the order a reader would peel them
    off the stored bytes. For a file stored as gzip-of(gpg-of(plaintext)):

        Pipeline(Gzip(), GPG(recipients=["alice"]))

    The same Pipeline is used on both read and write paths. The facade applies
    transforms in the correct direction:
      - read:  outer → inner (unwrap in list order)
      - write: inner → outer (wrap in reverse list order)
    """

    def __init__(self, *transforms: StreamTransform) -> None:
        self._outer_to_inner: tuple[StreamTransform, ...] = transforms

    def is_empty(self) -> bool:
        """Whether this pipeline leaves stored bytes unchanged."""
        return not self._outer_to_inner

    def apply_read(self, stream: BinaryIO) -> BinaryIO:
        """Strip layers outermost → innermost.

        Closing the result closes every distinct layer built here, in reverse
        construction order. The input stream remains caller-owned; transforms
        must not close borrowed inputs. Empty/identity pipelines return it as-is.
        Construction failures unwind built layers without masking the failure.
        """
        cleanup = contextlib.ExitStack()
        seen = {id(stream)}
        try:
            for transform in self._outer_to_inner:
                stream = transform.unwrap(stream)
                if id(stream) not in seen:
                    seen.add(id(stream))
                    cleanup.callback(_close_if_open, stream)
            if len(seen) == 1:
                return stream
            return t.cast(BinaryIO, _ReadStream(stream, cleanup))
        except BaseException:
            try:
                cleanup.close()
            except Exception:
                pass
            raise

    def apply_write(self, stream: BinaryIO) -> BinaryIO:
        """Add layers innermost → outermost (reverse of list)."""
        for transform in reversed(self._outer_to_inner):
            stream = transform.wrap(stream)
        return stream
