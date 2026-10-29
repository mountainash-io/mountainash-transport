"""Profile infrastructure — protocols, specs, registry, and the storage resolver."""
from __future__ import annotations

import importlib
import typing as t

from .profile_protocol import ProfileProtocol, StorageProfileProtocol

if t.TYPE_CHECKING:
    from .profile_spec import ParameterSpec, StorageProfileSpec
    from .storage.loader import AuthBlock, StorageProfileBlock, StorageProfilesSettings, resolve_storage

_LAZY: dict[str, str] = {
    "ParameterSpec": ".profile_spec",
    "StorageProfileSpec": ".profile_spec",
    "AuthBlock": ".storage.loader",
    "StorageProfileBlock": ".storage.loader",
    "StorageProfilesSettings": ".storage.loader",
    "resolve_storage": ".storage.loader",
}


def __getattr__(name: str) -> t.Any:
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        return getattr(importlib.import_module(module, __name__), name)
    except ImportError as exc:
        from mountainash_transport._core.extras import raise_for_missing_extra
        raise_for_missing_extra("storage profiles", "http", exc)


__all__ = [
    "ProfileProtocol", "StorageProfileProtocol", "ParameterSpec", "StorageProfileSpec",
    "AuthBlock", "StorageProfileBlock", "StorageProfilesSettings", "resolve_storage",
]
