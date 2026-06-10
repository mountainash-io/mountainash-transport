"""Registry honesty — drift test and scheme conformance.

The implemented flag on StorageProfileSpec is the single source of truth.
These tests pin it against the backend registry and scheme table.
"""

import pytest

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.exceptions import BackendNotImplementedError
from mountainash_transport.settings.storage.registry import STORAGE_REGISTRY
from mountainash_transport.storage.registry import get_registered_backends, get_storage_backend
from mountainash_transport.storage.path_helpers.scheme import SCHEMES
import mountainash_transport.storage.backends  # noqa: F401 — trigger registrations


class TestImplementedFlagDrift:
    """spec.implemented must be True iff a backend is registered."""

    @pytest.mark.parametrize(
        "name",
        list(STORAGE_REGISTRY.descriptors.keys()),
    )
    def test_implemented_matches_backend_registry(self, name):
        spec = STORAGE_REGISTRY.descriptors[name]
        backends = get_registered_backends()
        has_backend = spec.provider_type in backends
        assert spec.implemented == has_backend, (
            f"Profile '{name}' has implemented={spec.implemented} "
            f"but backend registered={has_backend}"
        )


class TestSchemeConformance:
    """Every scheme with a provider either resolves to a backend or raises
    BackendNotImplementedError — never an opaque ValueError."""

    @pytest.mark.parametrize(
        "scheme_key,spec",
        [
            (k, v) for k, v in SCHEMES.items() if v.provider is not None
        ],
    )
    def test_scheme_provider_is_honest(self, scheme_key, spec):
        backends = get_registered_backends()
        if spec.provider in backends:
            backend = get_storage_backend(spec.provider, None)
            assert backend is not None, (
                f"Scheme '{scheme_key}' -> {spec.provider} is implemented but "
                f"get_storage_backend returned None"
            )
        else:
            with pytest.raises(BackendNotImplementedError):
                get_storage_backend(spec.provider, None)
