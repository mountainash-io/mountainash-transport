from __future__ import annotations

from typing import BinaryIO, Protocol, runtime_checkable

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry


@runtime_checkable
class StorageWriteProtocol(Protocol):
    """Write data, translating destination I/O into StorageError subclasses.

    Directory backends create missing parents by default. With create_parents=False,
    the native write reports missing parents without an existence pre-check.
    Backends without directories accept the option as a no-op.

    Both methods return the written object's ``StorageEntry``: path, name and the
    stored size, plus whatever else the store reported for the write. A write
    never spends a request to fill fields, so unreported fields stay empty.
    """

    def write_from_bytes(self, path: str, data: bytes, *, create_parents: bool = True) -> StorageEntry:
        """Write bytes data to a file at the given path."""
        ...

    def write_from_stream(self, path: str, stream: BinaryIO, *, create_parents: bool = True) -> StorageEntry:
        """Write a stream, preserving caller input errors and partial-write semantics."""
        ...
