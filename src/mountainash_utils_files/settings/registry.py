"""Module-level registry of storage provider specs.

Backed by :class:`mountainash_settings.profiles.Registry`.
"""

from __future__ import annotations

import typing as t
import warnings

from mountainash_settings.profiles import Registry

from .descriptor import StorageDescriptor
from .profile import StorageProfile

if t.TYPE_CHECKING:
    from mountainash_settings.profiles import ProfileSpec

__all__ = [
    "STORAGE_REGISTRY",
    "get_descriptor",
    "get_spec",
    "get_settings_class",
    "register",
]

STORAGE_REGISTRY = Registry(
    "storage",
    spec_type=StorageDescriptor,
    profile_type=StorageProfile,
)

register = STORAGE_REGISTRY.decorator()


def get_spec(name: str) -> "ProfileSpec":
    return STORAGE_REGISTRY.get_descriptor(name)


def get_descriptor(name: str) -> "ProfileSpec":
    warnings.warn(
        "'get_descriptor' is renamed to 'get_spec'. "
        "Update calls before mountainash-utils-files 26.6.0.",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_spec(name)


def get_settings_class(name: str) -> type["StorageProfile"]:
    return STORAGE_REGISTRY.get_settings_class(name)  # type: ignore[return-value]
