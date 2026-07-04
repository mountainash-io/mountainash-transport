"""Profile infrastructure — protocols, specs, registry, and the storage resolver."""

from .profile_protocol import ProfileProtocol, StorageProfileProtocol
from .profile_spec import ParameterSpec, StorageProfileSpec
from .storage.loader import (
    AuthBlock,
    StorageProfileBlock,
    StorageProfilesSettings,
    resolve_storage,
)

__all__ = [
    "ProfileProtocol",
    "StorageProfileProtocol",
    "ParameterSpec",
    "StorageProfileSpec",
    "AuthBlock",
    "StorageProfileBlock",
    "StorageProfilesSettings",
    "resolve_storage",
]
