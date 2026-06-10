"""Enforce that every registered backend conforms to its declared protocols."""
import pytest
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.storage.protocols import (
    StorageReadProtocol, StorageWriteProtocol,
    StorageEnumerateProtocol, StorageDeleteProtocol, StorageMetadataProtocol,
    StorageCopyProtocol, StorageDirectoryProtocol,
)
from mountainash_transport.storage.registry import get_registered_backends
import mountainash_transport.storage.backends  # noqa: F401

EXPECTED_PROTOCOLS = {
    CONST_STORAGE_PROVIDER_TYPE.LOCAL: {
        StorageReadProtocol, StorageWriteProtocol,
        StorageDeleteProtocol, StorageMetadataProtocol,
        StorageCopyProtocol, StorageDirectoryProtocol,
    },
    CONST_STORAGE_PROVIDER_TYPE.S3: {
        StorageReadProtocol, StorageWriteProtocol,
        StorageEnumerateProtocol, StorageDeleteProtocol, StorageMetadataProtocol,
        StorageCopyProtocol,
    },
    CONST_STORAGE_PROVIDER_TYPE.R2: {
        StorageReadProtocol, StorageWriteProtocol,
        StorageEnumerateProtocol, StorageDeleteProtocol, StorageMetadataProtocol,
        StorageCopyProtocol,
    },
    CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS: {
        StorageReadProtocol, StorageWriteProtocol,
        StorageEnumerateProtocol, StorageDeleteProtocol, StorageMetadataProtocol,
        StorageCopyProtocol,
    },
    CONST_STORAGE_PROVIDER_TYPE.MINIO: {
        StorageReadProtocol, StorageWriteProtocol,
        StorageEnumerateProtocol, StorageDeleteProtocol, StorageMetadataProtocol,
        StorageCopyProtocol,
    },
    CONST_STORAGE_PROVIDER_TYPE.SSH: {
        StorageReadProtocol, StorageWriteProtocol,
        StorageDeleteProtocol, StorageMetadataProtocol,
        StorageDirectoryProtocol,
    },
    CONST_STORAGE_PROVIDER_TYPE.HTTP: {
        StorageReadProtocol, StorageWriteProtocol, StorageMetadataProtocol,
    },
}

EXCLUDED_PROTOCOLS = {
    CONST_STORAGE_PROVIDER_TYPE.S3: {StorageDirectoryProtocol},
    CONST_STORAGE_PROVIDER_TYPE.R2: {StorageDirectoryProtocol},
    CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS: {StorageDirectoryProtocol},
    CONST_STORAGE_PROVIDER_TYPE.MINIO: {StorageDirectoryProtocol},
    CONST_STORAGE_PROVIDER_TYPE.SSH: {StorageEnumerateProtocol, StorageCopyProtocol},
    CONST_STORAGE_PROVIDER_TYPE.HTTP: {
        StorageEnumerateProtocol,
        StorageDeleteProtocol, StorageCopyProtocol, StorageDirectoryProtocol,
    },
}


class TestProtocolConformance:
    @pytest.mark.parametrize("provider_type", list(EXPECTED_PROTOCOLS.keys()))
    def test_backend_implements_required_protocols(self, provider_type):
        backends = get_registered_backends()
        assert provider_type in backends
        backend_cls = backends[provider_type]
        for protocol in EXPECTED_PROTOCOLS[provider_type]:
            assert issubclass(backend_cls, protocol), (
                f"{backend_cls.__name__} does not implement {protocol.__name__}"
            )

    @pytest.mark.parametrize("provider_type", list(EXCLUDED_PROTOCOLS.keys()))
    def test_backend_excludes_unsupported_protocols(self, provider_type):
        backends = get_registered_backends()
        backend_cls = backends[provider_type]
        for protocol in EXCLUDED_PROTOCOLS[provider_type]:
            assert not issubclass(backend_cls, protocol), (
                f"{backend_cls.__name__} should NOT implement {protocol.__name__}"
            )
