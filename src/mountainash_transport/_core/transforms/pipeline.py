"""Pipeline — ordered stack of stream transforms."""

from __future__ import annotations

from typing import BinaryIO

from .base import StreamTransform


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

        If a layer fails to construct, layers already built here are closed
        (innermost first) before the error propagates. The input *stream* is
        not closed; it remains owned by the caller.
        """
        built: list[BinaryIO] = []
        try:
            for t in self._outer_to_inner:
                stream = t.unwrap(stream)
                built.append(stream)
        except BaseException:
            for layer in reversed(built):
                try:
                    layer.close()
                except Exception:
                    pass
            raise
        return stream

    def apply_write(self, stream: BinaryIO) -> BinaryIO:
        """Add layers innermost → outermost (reverse of list)."""
        for t in reversed(self._outer_to_inner):
            stream = t.wrap(stream)
        return stream
