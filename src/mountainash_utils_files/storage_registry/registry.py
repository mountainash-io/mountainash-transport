# storage_registry/registry.py

import inspect
import typing as t

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE

_backend_registry: dict[CONST_STORAGE_PROVIDER_TYPE, type] = {}


def register_storage_backend(provider_type: CONST_STORAGE_PROVIDER_TYPE) -> t.Callable[[type], type]:
    """Decorator that registers a backend class for a provider type."""
    def decorator(cls: type) -> type:
        _backend_registry[provider_type] = cls
        return cls
    return decorator


def _accepts_auth(cls: type) -> bool:
    """Check if a backend class's __init__ accepts an 'auth' parameter."""
    try:
        sig = inspect.signature(cls.__init__)
        return "auth" in sig.parameters
    except (ValueError, TypeError):
        return False


def get_storage_backend(
    provider_type: CONST_STORAGE_PROVIDER_TYPE,
    auth_params: t.Any,
    *,
    auth: t.Any = None,
) -> t.Any:
    """Instantiate and return a backend for the given provider type."""
    cls = _backend_registry.get(provider_type)
    if cls is None:
        raise ValueError(f"No backend registered for {provider_type!r}")
    if auth is not None and _accepts_auth(cls):
        return cls(auth_params, auth=auth)
    return cls(auth_params)


def get_registered_backends() -> dict[CONST_STORAGE_PROVIDER_TYPE, type]:
    """Return a copy of all registered backends."""
    return dict(_backend_registry)


def clear_registry() -> None:
    """Clear all registered backends. For testing only."""
    _backend_registry.clear()
