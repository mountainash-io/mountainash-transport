# storage_facade/cross_backend.py

"""Cross-backend file transfer utilities."""

from __future__ import annotations

import typing

from mountainash_utils_files.storage_protocols import StorageCopyProtocol

if typing.TYPE_CHECKING:
    from mountainash_utils_files.storage_facade.facade import StorageFacade


def copy_between(
    source_path: str,
    destination_path: str,
    source_facade: StorageFacade,
    destination_facade: StorageFacade,
) -> None:
    """Copy a file between two facades, using native copy when possible.

    If both facades share the same backend type and the backend supports the
    :class:`~mountainash_utils_files.storage_protocols.StorageCopyProtocol`,
    the native copy method is used.  Otherwise the file is streamed from the
    source facade and written to the destination facade.

    Args:
        source_path: Path of the file on the source facade.
        destination_path: Path to write the file on the destination facade.
        source_facade: Facade wrapping the source backend.
        destination_facade: Facade wrapping the destination backend.
    """
    if (
        isinstance(source_facade._backend, type(destination_facade._backend))
        and source_facade.supports(StorageCopyProtocol)
    ):
        source_facade.copy(source_path, destination_path)
        return

    stream = source_facade.read_stream(source_path)
    try:
        destination_facade.write_stream(destination_path, stream)
    finally:
        stream.close()
