"""Verify the new public API exports are correct."""
import pytest


class TestPublicAPI:

    def test_facade_importable(self):
        from mountainash_utils_files import StorageFacade, copy_between, storage
        assert callable(StorageFacade)
        assert callable(copy_between)
        assert callable(storage)

    def test_protocols_importable(self):
        from mountainash_utils_files import (
            StorageReadProtocol, StorageWriteProtocol, StorageListProtocol,
            StorageDeleteProtocol, StorageMetadataProtocol, StorageCopyProtocol,
            StorageDirectoryProtocol, StorageConnectionProtocol,
        )

    def test_registry_importable(self):
        from mountainash_utils_files import get_storage_backend, detect_provider_from_path

    def test_constants_importable(self):
        from mountainash_utils_files import CONST_STORAGE_PROVIDER_TYPE

    def test_exceptions_importable(self):
        from mountainash_utils_files import (
            StorageError, UnsupportedOperationError,
            PathNotFoundError, AuthenticationError,
        )

    def test_path_helper_importable(self):
        from mountainash_utils_files import PathHelper

    def test_storage_convenience_factory(self):
        from mountainash_utils_files import storage, StorageReadProtocol
        facade = storage()
        assert facade.supports(StorageReadProtocol)
