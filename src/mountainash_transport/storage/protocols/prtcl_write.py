from __future__ import annotations

from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class StorageWriteProtocol(Protocol):
    """Write data, translating destination I/O into StorageError subclasses."""

    def write_from_bytes(self, path: str, data: bytes) -> None:
        """Write bytes data to a file at the given path."""
        ...

    def write_from_stream(self, path: str, stream: BinaryIO) -> None:
        """Write a stream, preserving caller input errors and partial-write semantics."""
        ...
