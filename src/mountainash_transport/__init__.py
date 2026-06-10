"""mountainash-transport — unified storage and messaging operations across backends."""

from .__version__ import __version__

# Facade — main user API
from .storage.facade import StorageFacade, copy_between

# Registry
from .storage.registry import get_storage_backend, detect_provider_from_path

# Protocols — for isinstance checks and type hints
from .storage.protocols import (
    StorageReadProtocol,
    StorageWriteProtocol,
    StorageEnumerateProtocol,
    StorageDeleteProtocol,
    StorageMetadataProtocol,
    StorageCopyProtocol,
    StorageDirectoryProtocol,
)
from ._core.protocols import ConnectionProtocol
from .connections.errors import TransportConnectionError
from .connections import (
    SSHConnection, SFTPConnection, TunnelledConnection,
    create_connection, create_tunnelled_connection,
)

# Constants
from ._core.constants import CONST_STORAGE_PROVIDER_TYPE

# Dataclasses
from ._core.dataclasses.storage_entry import EntryType, EnumerateResult, StorageEntry

# Exceptions
from ._core.exceptions import (
    StorageError,
    UnsupportedOperationError,
    StorageConnectionError,
    PathNotFoundError,
    AuthenticationError,
    TransformError,
)

# Stream transforms
from ._core.transforms import (
    Pipeline,
    StreamTransform,
    Gzip,
    GPG,
)

# Path utilities
from .storage.path_helpers import StoragePath, infer_pipeline

# Trigger backend registrations
from .storage import backends  # noqa: F401


def storage(provider_type: CONST_STORAGE_PROVIDER_TYPE = CONST_STORAGE_PROVIDER_TYPE.LOCAL,
            profile=None, *, auth_profile=None) -> StorageFacade:
    """Convenience factory for creating a StorageFacade."""
    return StorageFacade(provider_type, profile, auth_profile=auth_profile)


__all__ = [
    "__version__",
    "StorageFacade", "copy_between", "storage",
    "get_storage_backend", "detect_provider_from_path",
    "ConnectionProtocol", "TransportConnectionError",
    "SSHConnection", "SFTPConnection", "TunnelledConnection",
    "create_connection", "create_tunnelled_connection",
    "StorageReadProtocol", "StorageWriteProtocol",
    "StorageEnumerateProtocol", "StorageDeleteProtocol", "StorageMetadataProtocol",
    "StorageCopyProtocol", "StorageDirectoryProtocol",
    "CONST_STORAGE_PROVIDER_TYPE", "StorageEntry", "EntryType", "EnumerateResult",
    "StorageError", "UnsupportedOperationError", "StorageConnectionError",
    "PathNotFoundError", "AuthenticationError", "TransformError",
    "StoragePath", "infer_pipeline",
    "Pipeline", "StreamTransform", "Gzip", "GPG",
]
