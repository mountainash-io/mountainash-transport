"""Module-level registry of storage provider descriptors.

Backed by :class:`mountainash_settings.profiles.Registry`.
"""

from __future__ import annotations

import typing as t

from mountainash_settings.profiles import Registry

if t.TYPE_CHECKING:
    from mountainash_settings.profiles import ProfileDescriptor

    from .profile import StorageProfile

__all__ = [
    "STORAGE_REGISTRY",
    "get_descriptor",
    "get_settings_class",
    "register",
]

STORAGE_REGISTRY = Registry("storage")

register = STORAGE_REGISTRY.decorator()


def get_descriptor(name: str) -> "ProfileDescriptor":
    return STORAGE_REGISTRY.get_descriptor(name)


def get_settings_class(name: str) -> type["StorageProfile"]:
    return STORAGE_REGISTRY.get_settings_class(name)  # type: ignore[return-value]
