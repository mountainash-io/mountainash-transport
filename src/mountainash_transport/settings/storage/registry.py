"""Module-level registry of storage provider specs.

Backed by :class:`mountainash_settings.profiles.Registry`.
"""
from __future__ import annotations

from mountainash_settings.profiles import Registry

from ..profile_spec import StorageProfileSpec
from ..profile_protocol import StorageProfileProtocol

__all__ = [
    "STORAGE_REGISTRY",
    "get_spec",
    "get_settings_class",
    "register",
]

STORAGE_REGISTRY = Registry(
    "storage",
    spec_type=StorageProfileSpec,
    profile_type=StorageProfileProtocol,
)

register = STORAGE_REGISTRY.decorator()


def get_spec(name: str) -> StorageProfileSpec:
    return STORAGE_REGISTRY.get_spec(name)


def get_settings_class(name: str) -> type["StorageProfileProtocol"]:
    return STORAGE_REGISTRY.get_settings_class(name)


# Populate the registry on import. Profile modules use ``register`` above, so this
# import must stay at the bottom.
from . import profiles as _profiles  # noqa: E402,F401
