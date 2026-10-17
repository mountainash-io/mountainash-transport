from __future__ import annotations

from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class StorageWriteProtocol(Protocol):
    """Write data, translating destination I/O into StorageError subclasses.

    Directory backends create missing parents by default. With create_parents=False,
    the native write reports missing parents without an existence pre-check.
    Backends without directories accept the option as a no-op.
    """

    def write_from_bytes(self, path: str, data: bytes, *, create_parents: bool = True) -> None:
        """Write bytes data to a file at the given path."""
        ...

    def write_from_stream(self, path: str, stream: BinaryIO, *, create_parents: bool = True) -> None:
        """Write a stream, preserving caller input errors and partial-write semantics."""
        ...
