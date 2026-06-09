"""Verify the new public API exports are correct."""
import pytest


class TestPublicAPI:

    def test_facade_importable(self):
        from mountainash_transport import StorageFacade, copy_between, storage
        assert callable(StorageFacade)
        assert callable(copy_between)
        assert callable(storage)

    def test_protocols_importable(self):
        from mountainash_transport import (
            StorageReadProtocol, StorageWriteProtocol, StorageListProtocol,
            StorageDeleteProtocol, StorageMetadataProtocol, StorageCopyProtocol,
            StorageDirectoryProtocol, StorageConnectionProtocol,
        )

    def test_registry_importable(self):
        from mountainash_transport import get_storage_backend, detect_provider_from_path

    def test_constants_importable(self):
        from mountainash_transport import CONST_STORAGE_PROVIDER_TYPE

    def test_exceptions_importable(self):
        from mountainash_transport import (
            StorageError, UnsupportedOperationError,
            PathNotFoundError, AuthenticationError,
        )

    def test_storage_path_importable(self):
        from mountainash_transport import StoragePath
        assert callable(StoragePath.identify_scheme)

    def test_storage_convenience_factory(self):
        from mountainash_transport import storage, StorageReadProtocol
        facade = storage()
        assert facade.supports(StorageReadProtocol)

    def test_transform_exports_are_top_level(self):
        """Pipeline, Gzip, GPG, StreamTransform, TransformError import from package root."""
        from mountainash_transport import (
            GPG,
            Gzip,
            Pipeline,
            StreamTransform,
            TransformError,
        )
        # Construction smoke checks
        assert isinstance(Pipeline(Gzip()).apply_read, type(Pipeline().apply_read))
        assert issubclass(TransformError, Exception)
        assert isinstance(Gzip(), StreamTransform)
