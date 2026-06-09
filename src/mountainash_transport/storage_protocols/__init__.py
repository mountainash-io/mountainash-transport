from __future__ import annotations

from mountainash_transport.storage_protocols.prtcl_connection import StorageConnectionProtocol
from mountainash_transport.storage_protocols.prtcl_copy import StorageCopyProtocol
from mountainash_transport.storage_protocols.prtcl_delete import StorageDeleteProtocol
from mountainash_transport.storage_protocols.prtcl_directory import StorageDirectoryProtocol
from mountainash_transport.storage_protocols.prtcl_list import StorageListProtocol
from mountainash_transport.storage_protocols.prtcl_metadata import StorageMetadataProtocol
from mountainash_transport.storage_protocols.prtcl_read import StorageReadProtocol
from mountainash_transport.storage_protocols.prtcl_write import StorageWriteProtocol

__all__ = [
    "StorageConnectionProtocol",
    "StorageCopyProtocol",
    "StorageDeleteProtocol",
    "StorageDirectoryProtocol",
    "StorageListProtocol",
    "StorageMetadataProtocol",
    "StorageReadProtocol",
    "StorageWriteProtocol",
]
