# storage_registry/__init__.py

from mountainash_utils_files.storage_registry.registry import (
    register_storage_backend,
    get_storage_backend,
    get_registered_backends,
    clear_registry,
)
from mountainash_utils_files.storage_registry.backend_detection import detect_provider_from_path

__all__ = [
    "register_storage_backend",
    "get_storage_backend",
    "get_registered_backends",
    "clear_registry",
    "detect_provider_from_path",
]
