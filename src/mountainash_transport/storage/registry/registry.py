# storage_registry/registry.py

import typing as t

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.exceptions import BackendNotImplementedError
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol


_backend_registry: dict[CONST_STORAGE_PROVIDER_TYPE, type] = {}


def register_storage_backend(provider_type: CONST_STORAGE_PROVIDER_TYPE) -> t.Callable[[type], type]:
    """Decorator that registers a backend class for a provider type."""
    def decorator(cls: type) -> type:
        _backend_registry[provider_type] = cls
        return cls
    return decorator


def get_storage_backend(
    provider_type: CONST_STORAGE_PROVIDER_TYPE,
    storage_profile: StorageProfileProtocol | None,
    *,
    connection: t.Any = None,
    auth_strategy: t.Any = None,
) -> t.Any:
    """Instantiate and return a backend for the given provider type.

    Uses a three-step lookup to give clear error messages:

    1. If a backend is registered, instantiate and return it.
    2. If the provider has a profile with ``implemented=False``, raise
       :class:`BackendNotImplementedError` with a helpful message listing
       implemented providers.
    3. If the value is a valid :class:`CONST_STORAGE_PROVIDER_TYPE` enum
       member (but has no profile), raise :class:`BackendNotImplementedError`.
    4. Otherwise raise :class:`ValueError` for truly unknown providers.

    Args:
        provider_type: The storage provider to look up.
        storage_profile: Optional profile forwarded to the backend constructor.
        connection: Optional pre-built connection object forwarded to the backend.
        auth_strategy: Optional auth strategy forwarded to the backend constructor (HTTP backends only).

    Returns:
        An instantiated backend object.

    Raises:
        BackendNotImplementedError: If the provider exists but has no backend.
        ValueError: If the provider_type is not a recognised enum member.
    """
    # Step 1 — registered backend found
    cls = _backend_registry.get(provider_type)
    if cls is not None:
        kwargs: dict[str, t.Any] = {"connection": connection}
        if auth_strategy is not None:
            kwargs["auth_strategy"] = auth_strategy
        return cls(storage_profile, **kwargs)

    # Build the implemented-providers list for error messages
    implemented = sorted(str(k) for k in _backend_registry)

    # Step 2 — provider has a profile but backend is not implemented
    from mountainash_transport.settings.storage.registry import STORAGE_REGISTRY  # avoid circular import

    for spec in STORAGE_REGISTRY.descriptors.values():
        if spec.provider_type == provider_type:
            raise BackendNotImplementedError(
                f"The '{provider_type}' storage provider is not yet implemented. "
                f"Implemented providers: {implemented}"
            )

    # Step 3 — valid enum member but no profile registered
    if isinstance(provider_type, CONST_STORAGE_PROVIDER_TYPE):
        raise BackendNotImplementedError(
            f"The '{provider_type}' storage provider is not yet implemented. "
            f"Implemented providers: {implemented}"
        )

    # Step 4 — truly unknown
    raise ValueError(f"Unknown provider type: {provider_type!r}")


def get_registered_backends() -> dict[CONST_STORAGE_PROVIDER_TYPE, type]:
    """Return a copy of all registered backends."""
    return dict(_backend_registry)


def clear_registry() -> None:
    """Clear all registered backends. For testing only."""
    _backend_registry.clear()
