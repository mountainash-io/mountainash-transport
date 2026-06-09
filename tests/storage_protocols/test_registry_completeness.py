"""Verify every expected provider type has a registered backend."""

import pytest
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.storage.registry import get_registered_backends
import mountainash_transport.storage.backends  # trigger registrations

REQUIRED_BACKENDS = {
    CONST_STORAGE_PROVIDER_TYPE.LOCAL,
    CONST_STORAGE_PROVIDER_TYPE.S3,
    CONST_STORAGE_PROVIDER_TYPE.R2,
    CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS,
    CONST_STORAGE_PROVIDER_TYPE.MINIO,
}

ASPIRATIONAL_BACKENDS = {
    CONST_STORAGE_PROVIDER_TYPE.GCS,
    CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
    CONST_STORAGE_PROVIDER_TYPE.SFTP,
    CONST_STORAGE_PROVIDER_TYPE.SSH,
    CONST_STORAGE_PROVIDER_TYPE.B2,
}

class TestRegistryCompleteness:
    def test_all_required_backends_registered(self):
        backends = get_registered_backends()
        for provider in REQUIRED_BACKENDS:
            assert provider in backends, f"Missing backend for {provider}"

    @pytest.mark.parametrize("provider", list(ASPIRATIONAL_BACKENDS))
    def test_aspirational_backends_tracked(self, provider):
        backends = get_registered_backends()
        if provider in backends:
            pytest.skip(f"{provider} implemented — move to REQUIRED_BACKENDS")
        else:
            pytest.skip(f"{provider} not yet implemented — aspirational")
