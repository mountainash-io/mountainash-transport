from __future__ import annotations

import typing
from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class StorageReadProtocol(Protocol):
    """Protocol for reading data from storage."""

    def read_to_bytes(self, path: str) -> bytes:
        """Read the contents of a file and return as bytes."""
        ...

    def read_to_stream(self, path: str) -> BinaryIO:
        """Read the contents of a file and return as a binary stream."""
        ...
