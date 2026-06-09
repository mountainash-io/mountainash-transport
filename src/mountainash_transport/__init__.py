"""mountainash-transport — unified storage operations across backends."""

from .__version__ import __version__

# Facade — main user API
from .storage_facade import StorageFacade, copy_between, read_bytes

# Registry
from .storage_registry import get_storage_backend, detect_provider_from_path

# Protocols — for isinstance checks and type hints
from .storage_protocols import (
    StorageConnectionProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
    StorageListProtocol,
    StorageDeleteProtocol,
    StorageMetadataProtocol,
    StorageCopyProtocol,
    StorageDirectoryProtocol,
)

# Constants
from .constants import CONST_STORAGE_PROVIDER_TYPE

# Dataclasses
from .dataclasses.file_metadata import FileMetadata

# Exceptions
from .exceptions import (
    StorageError,
    UnsupportedOperationError,
    StorageConnectionError,
    PathNotFoundError,
    AuthenticationError,
    TransformError,
)

# Stream transforms
from .storage_transforms import (
    Pipeline,
    StreamTransform,
    Gzip,
    GPG,
)

# Path utilities
from .path_helpers import StoragePath, infer_pipeline

# Trigger backend registrations
from . import storage_backends  # noqa: F401


def storage(provider_type: CONST_STORAGE_PROVIDER_TYPE = CONST_STORAGE_PROVIDER_TYPE.LOCAL,
            profile=None, *, auth_profile=None) -> StorageFacade:
    """Convenience factory for creating a StorageFacade."""
    return StorageFacade(provider_type, profile, auth_profile=auth_profile)


__all__ = [
    "__version__",
    "StorageFacade", "copy_between", "read_bytes", "storage",
    "get_storage_backend", "detect_provider_from_path",
    "StorageConnectionProtocol", "StorageReadProtocol", "StorageWriteProtocol",
    "StorageListProtocol", "StorageDeleteProtocol", "StorageMetadataProtocol",
    "StorageCopyProtocol", "StorageDirectoryProtocol",
    "CONST_STORAGE_PROVIDER_TYPE", "FileMetadata",
    "StorageError", "UnsupportedOperationError", "StorageConnectionError",
    "PathNotFoundError", "AuthenticationError", "TransformError",
    "StoragePath", "infer_pipeline",
    "Pipeline", "StreamTransform", "Gzip", "GPG",
]
