# storage_facade/cross_backend.py

"""Cross-backend file transfer utilities."""

from __future__ import annotations

import typing

from mountainash_transport.storage.protocols import StorageCopyProtocol
from mountainash_transport._core.transforms import Pipeline, StreamTransform

if typing.TYPE_CHECKING:
    from mountainash_transport.storage.facade.facade import StorageFacade


def copy_between(
    source_path: str,
    destination_path: str,
    source_facade: StorageFacade,
    destination_facade: StorageFacade,
    *,
    source_pipeline: Pipeline | StreamTransform | None = None,
    destination_pipeline: Pipeline | StreamTransform | None = None,
) -> None:
    """Copy a file between two facades, optionally applying transforms on each side.

    Uses the store's native copy when no pipeline is given, the facades address
    the same store (:meth:`StorageFacade.same_store`) and the store can copy;
    otherwise streams from the source into the destination.
    """
    # Fail before any I/O when either side is closed (facade-internal check).
    source_facade._ensure_open()
    destination_facade._ensure_open()
    if (
        source_pipeline is None
        and destination_pipeline is None
        and source_facade.same_store(destination_facade)
        and source_facade.supports(StorageCopyProtocol)
    ):
        source_facade.copy(source_path, destination_path)
        return

    stream = source_facade.read_stream(source_path, pipeline=source_pipeline)
    try:
        destination_facade.write_stream(
            destination_path, stream, pipeline=destination_pipeline
        )
    finally:
        stream.close()
