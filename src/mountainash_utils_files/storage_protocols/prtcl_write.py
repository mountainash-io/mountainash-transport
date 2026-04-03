from __future__ import annotations

import typing
from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class StorageWriteProtocol(Protocol):
    """Protocol for writing data to storage."""

    def write_from_bytes(self, path: str, data: bytes) -> None:
        """Write bytes data to a file at the given path."""
        ...

    def write_from_stream(self, path: str, stream: BinaryIO) -> None:
        """Write data from a binary stream to a file at the given path."""
        ...
