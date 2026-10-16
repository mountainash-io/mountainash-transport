from __future__ import annotations

from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class StorageReadProtocol(Protocol):
    """Read data; backend I/O raises StorageError subclasses with native causes.

    Caller arguments and transforms retain their own errors.
    """

    def read_to_bytes(self, path: str) -> bytes:
        """Read the contents of a file and return as bytes."""
        ...

    def read_to_stream(self, path: str) -> BinaryIO:
        """Return a binary stream; backend failures can occur on read or close."""
        ...
