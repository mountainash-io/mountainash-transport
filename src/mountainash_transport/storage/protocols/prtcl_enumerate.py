from __future__ import annotations

from typing import Protocol, runtime_checkable

from mountainash_transport._core.dataclasses.storage_entry import EnumerateResult


@runtime_checkable
class StorageEnumerateProtocol(Protocol):
    """Enumerate filesystem paths or object-store prefixes into shared results."""

    def list_objects(
        self,
        prefix: str,
        *,
        delimiter: str | None = None,
        max_results: int | None = None,
    ) -> EnumerateResult:
        """List selected files/objects and common prefixes.

        Local/SFTP select an exact path; S3 selects literal key prefixes.
        None recurses; "/" groups immediate children. Backend/page failures
        raise typed StorageError subclasses rather than partial results.
        """
        ...
