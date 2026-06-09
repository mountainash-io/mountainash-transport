# tests/test_registry.py

import pytest

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.storage.registry import (
    clear_registry,
    detect_provider_from_path,
    get_registered_backends,
    get_storage_backend,
    register_storage_backend,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeBackend:
    """Minimal backend stub used across tests."""

    def __init__(self, storage_profile=None, *, auth_profile=None, connection=None):
        self.storage_profile = storage_profile
        self.auth_profile = auth_profile
        self._connection = connection


# ---------------------------------------------------------------------------
# detect_provider_from_path
# ---------------------------------------------------------------------------

class TestDetectProviderFromPath:
    """Tests for detect_provider_from_path."""

    def test_local_path_no_scheme(self):
        assert detect_provider_from_path("/tmp/some/file.txt") == CONST_STORAGE_PROVIDER_TYPE.LOCAL

    def test_local_relative_path(self):
        assert detect_provider_from_path("relative/path/file.csv") == CONST_STORAGE_PROVIDER_TYPE.LOCAL

    def test_local_empty_path(self):
        assert detect_provider_from_path("") == CONST_STORAGE_PROVIDER_TYPE.LOCAL

    def test_s3_scheme(self):
        assert detect_provider_from_path("s3://my-bucket/key") == CONST_STORAGE_PROVIDER_TYPE.S3

    def test_gs_scheme(self):
        assert detect_provider_from_path("gs://my-bucket/object") == CONST_STORAGE_PROVIDER_TYPE.GCS

    def test_az_scheme(self):
        assert detect_provider_from_path("az://container/blob") == CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB

    def test_sftp_scheme(self):
        assert detect_provider_from_path("sftp://host/path/to/file") == CONST_STORAGE_PROVIDER_TYPE.SFTP

    def test_ssh_scheme(self):
        assert detect_provider_from_path("ssh://host/path") == CONST_STORAGE_PROVIDER_TYPE.SSH

    def test_r2_scheme(self):
        assert detect_provider_from_path("r2://bucket/key") == CONST_STORAGE_PROVIDER_TYPE.R2

    def test_b2_scheme(self):
        assert detect_provider_from_path("b2://bucket/file.txt") == CONST_STORAGE_PROVIDER_TYPE.B2

    def test_scheme_is_case_insensitive(self):
        assert detect_provider_from_path("S3://bucket/key") == CONST_STORAGE_PROVIDER_TYPE.S3

    def test_ftp_scheme(self):
        assert detect_provider_from_path("ftp://host/file") == CONST_STORAGE_PROVIDER_TYPE.FTP

    def test_unknown_scheme_raises_value_error(self):
        with pytest.raises(ValueError, match="Unrecognised scheme"):
            detect_provider_from_path("xyz://some/path")

    def test_unknown_scheme_error_contains_path(self):
        with pytest.raises(ValueError, match="unknown://path"):
            detect_provider_from_path("unknown://path")


# ---------------------------------------------------------------------------
# register_storage_backend / get_storage_backend
# ---------------------------------------------------------------------------

class TestRegisterAndGetBackend:
    """Tests for the decorator registry."""

    def setup_method(self):
        """Save registry state before each test."""
        from mountainash_transport.storage.registry.registry import _backend_registry
        self._saved_registry = dict(_backend_registry)
        _backend_registry.clear()

    def teardown_method(self):
        """Restore registry state after each test."""
        from mountainash_transport.storage.registry.registry import _backend_registry
        _backend_registry.clear()
        _backend_registry.update(self._saved_registry)

    def test_decorator_registers_class(self):
        @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
        class LocalBackend(_FakeBackend):
            pass

        backends = get_registered_backends()
        assert CONST_STORAGE_PROVIDER_TYPE.LOCAL in backends
        assert backends[CONST_STORAGE_PROVIDER_TYPE.LOCAL] is LocalBackend

    def test_decorator_returns_class_unchanged(self):
        @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3)
        class S3Backend(_FakeBackend):
            pass

        assert S3Backend.__name__ == "S3Backend"

    def test_get_storage_backend_instantiates_with_profile(self):
        storage_profile = {"key": "value"}

        @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
        class LocalBackend(_FakeBackend):
            pass

        instance = get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL, storage_profile=storage_profile)
        assert isinstance(instance, LocalBackend)
        assert instance.storage_profile is storage_profile

    def test_unregistered_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="No backend registered"):
            get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.GCS, None)

    def test_unregistered_error_mentions_provider(self):
        with pytest.raises(ValueError, match="gcs"):
            get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.GCS, None)

    def test_duplicate_registration_overwrites(self):
        @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3)
        class FirstBackend(_FakeBackend):
            pass

        @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3)
        class SecondBackend(_FakeBackend):
            pass

        backends = get_registered_backends()
        assert backends[CONST_STORAGE_PROVIDER_TYPE.S3] is SecondBackend

    def test_multiple_backends_registered_independently(self):
        @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
        class LocalBackend(_FakeBackend):
            pass

        @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3)
        class S3Backend(_FakeBackend):
            pass

        backends = get_registered_backends()
        assert backends[CONST_STORAGE_PROVIDER_TYPE.LOCAL] is LocalBackend
        assert backends[CONST_STORAGE_PROVIDER_TYPE.S3] is S3Backend


# ---------------------------------------------------------------------------
# get_registered_backends
# ---------------------------------------------------------------------------

class TestGetRegisteredBackends:
    """Tests for get_registered_backends."""

    def setup_method(self):
        """Save registry state before each test."""
        from mountainash_transport.storage.registry.registry import _backend_registry
        self._saved_registry = dict(_backend_registry)
        _backend_registry.clear()

    def teardown_method(self):
        """Restore registry state after each test."""
        from mountainash_transport.storage.registry.registry import _backend_registry
        _backend_registry.clear()
        _backend_registry.update(self._saved_registry)

    def test_returns_empty_dict_after_clear(self):
        assert get_registered_backends() == {}

    def test_returns_copy_not_original(self):
        @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
        class LocalBackend(_FakeBackend):
            pass

        copy = get_registered_backends()
        copy[CONST_STORAGE_PROVIDER_TYPE.S3] = _FakeBackend  # mutate the copy

        # Original registry must be unaffected
        assert CONST_STORAGE_PROVIDER_TYPE.S3 not in get_registered_backends()


# ---------------------------------------------------------------------------
# clear_registry
# ---------------------------------------------------------------------------

class TestClearRegistry:
    """Tests for clear_registry."""

    def setup_method(self):
        """Save registry state before each test."""
        from mountainash_transport.storage.registry.registry import _backend_registry
        self._saved_registry = dict(_backend_registry)
        _backend_registry.clear()

    def teardown_method(self):
        """Restore registry state after each test."""
        from mountainash_transport.storage.registry.registry import _backend_registry
        _backend_registry.clear()
        _backend_registry.update(self._saved_registry)

    def test_clear_removes_all_backends(self):
        @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
        class LocalBackend(_FakeBackend):
            pass

        assert get_registered_backends()  # non-empty
        clear_registry()
        assert get_registered_backends() == {}

    def test_clear_then_register_works(self):
        @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.GCS)
        class GCSBackend(_FakeBackend):
            pass

        clear_registry()

        @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.GCS)
        class GCSBackend2(_FakeBackend):
            pass

        backends = get_registered_backends()
        assert backends[CONST_STORAGE_PROVIDER_TYPE.GCS] is GCSBackend2
