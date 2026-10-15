from __future__ import annotations

import warnings

from mountainash_settings.profiles import Registry

from ..profile_spec import StorageProfileSpec
from ..profile_protocol import StorageProfileProtocol

"""Module-level registry of storage provider specs.

Backed by :class:`mountainash_settings.profiles.Registry`.
"""


__all__ = [
    "STORAGE_REGISTRY",
    "get_descriptor",
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


def get_descriptor(name: str) -> StorageProfileSpec:
    warnings.warn(
        "'get_descriptor' is renamed to 'get_spec'. "
        "Update calls before mountainash-transport 26.6.0.",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_spec(name)


def get_settings_class(name: str) -> type["StorageProfileProtocol"]:
    return STORAGE_REGISTRY.get_settings_class(name)
