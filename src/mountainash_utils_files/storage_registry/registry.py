# storage_registry/registry.py

import typing as t

from mountainash_auth_client import AuthMode
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE

if t.TYPE_CHECKING:
    from mountainash_utils_files.settings.profile import StorageProfile

_backend_registry: dict[CONST_STORAGE_PROVIDER_TYPE, type] = {}


def register_storage_backend(provider_type: CONST_STORAGE_PROVIDER_TYPE) -> t.Callable[[type], type]:
    """Decorator that registers a backend class for a provider type."""
    def decorator(cls: type) -> type:
        _backend_registry[provider_type] = cls
        return cls
    return decorator


def get_storage_backend(
    provider_type: CONST_STORAGE_PROVIDER_TYPE,
    profile: "StorageProfile | None",
    *,
    auth: AuthMode | None = None,
) -> t.Any:
    """Instantiate and return a backend for the given provider type."""
    cls = _backend_registry.get(provider_type)
    if cls is None:
        raise ValueError(f"No backend registered for {provider_type!r}")
    return cls(profile, auth=auth)


def get_registered_backends() -> dict[CONST_STORAGE_PROVIDER_TYPE, type]:
    """Return a copy of all registered backends."""
    return dict(_backend_registry)


def clear_registry() -> None:
    """Clear all registered backends. For testing only."""
    _backend_registry.clear()
