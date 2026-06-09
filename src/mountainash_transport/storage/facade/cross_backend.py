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

    Native same-backend copy is used only when both pipelines are None.
    Any pipeline argument forces a stream-through copy.
    """
    if (
        source_pipeline is None
        and destination_pipeline is None
        and isinstance(source_facade._backend, type(destination_facade._backend))
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
