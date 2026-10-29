"""StreamTransform protocol — reversible encoder/decoder over binary streams."""

from __future__ import annotations

from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class StreamTransform(Protocol):
    """A reversible encoder/decoder operating on binary streams.

    Both methods take a readable binary stream and return a new readable
    binary stream. wrap() encodes (adds a layer); unwrap() decodes (removes
    a layer). Both must stream lazily — no eager draining of the input.
    """

    def wrap(self, stream: BinaryIO) -> BinaryIO:
        """Encode: plaintext → encoded (add a layer, for writing outward)."""
        ...

    def unwrap(self, stream: BinaryIO) -> BinaryIO:
        """Decode: encoded → plaintext (strip a layer, for reading inward)."""
        ...
