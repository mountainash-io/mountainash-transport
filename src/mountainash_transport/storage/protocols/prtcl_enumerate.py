from __future__ import annotations

from typing import Protocol, runtime_checkable

from mountainash_transport._core.dataclasses.storage_entry import EnumerateResult


@runtime_checkable
class StorageEnumerateProtocol(Protocol):
    """Protocol for object-store-style enumeration with prefix/delimiter semantics."""

    def list_objects(
        self,
        prefix: str,
        *,
        delimiter: str | None = None,
        max_results: int | None = None,
    ) -> EnumerateResult:
        """List objects under a prefix, optionally scoped by a delimiter."""
        ...
