"""Storage capability protocols.

Retry rule every remote backend follows (configured by the profile's
``RETRY_*`` fields; see ``_core/retry.py``):

- Read, metadata, enumerate, directory, delete and move operations are retried on
  transient failure (lost connection, timeout, retryable status).
- ``read_to_stream`` and ``open_ranged`` retry only the open; bytes already
  returned are not re-fetched.
- ``write_from_bytes`` is retried; ``write_from_stream`` only when the source
  is seekable, re-sent from the position it started at.
- Path, permission and authentication errors are never retried. A delete or move
  whose reply was lost may raise ``PathNotFoundError`` on its retry.
"""
from __future__ import annotations

from mountainash_transport.storage.protocols.prtcl_copy import StorageCopyProtocol
from mountainash_transport.storage.protocols.prtcl_delete import StorageDeleteProtocol
from mountainash_transport.storage.protocols.prtcl_directory import StorageDirectoryProtocol
from mountainash_transport.storage.protocols.prtcl_enumerate import StorageEnumerateProtocol
from mountainash_transport.storage.protocols.prtcl_metadata import StorageMetadataProtocol
from mountainash_transport.storage.protocols.prtcl_move import StorageMoveProtocol
from mountainash_transport.storage.protocols.prtcl_read import StorageReadProtocol
from mountainash_transport.storage.protocols.prtcl_write import StorageWriteProtocol
from mountainash_transport.storage.protocols.prtcl_ranged_read import RangedReadProtocol

__all__ = [
    "RangedReadProtocol",
    "StorageCopyProtocol",
    "StorageDeleteProtocol",
    "StorageDirectoryProtocol",
    "StorageEnumerateProtocol",
    "StorageMetadataProtocol",
    "StorageMoveProtocol",
    "StorageReadProtocol",
    "StorageWriteProtocol",
]
