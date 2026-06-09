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

    def apply_read(self, stream: BinaryIO) -> BinaryIO:
        """Strip layers outermost → innermost."""
        for t in self._outer_to_inner:
            stream = t.unwrap(stream)
        return stream

    def apply_write(self, stream: BinaryIO) -> BinaryIO:
        """Add layers innermost → outermost (reverse of list)."""
        for t in reversed(self._outer_to_inner):
            stream = t.wrap(stream)
        return stream
