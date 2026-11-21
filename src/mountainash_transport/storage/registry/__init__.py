# storage_registry/__init__.py

from mountainash_transport.storage.registry.registry import (
    register_storage_backend,
    get_storage_backend,
    get_registered_backends,
)
from mountainash_transport.storage.registry.backend_detection import detect_provider_from_path

__all__ = [
    "register_storage_backend",
    "get_storage_backend",
    "get_registered_backends",
    "detect_provider_from_path",
]
