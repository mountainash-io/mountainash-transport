"""Tests for STORAGE_REGISTRY wrapper and helpers.

This is the **settings** registry (spec-driven, wraps
``mountainash_settings.profiles.Registry``). It is distinct from
``tests/test_registry.py`` which covers the older per-path
``storage_backends`` dispatch table.
"""

from __future__ import annotations

import pytest

# Trigger provider registration so STORAGE_REGISTRY is populated.
import mountainash_utils_files.settings.providers  # noqa: F401

from mountainash_utils_files.settings.providers import (
    AZURE_STORAGE_SPEC,
    AzureStorageSettings,
    FTP_SPEC,
    FTPSettings,
    GCS_SPEC,
    GCSSettings,
    GITHUB_REPO_SPEC,
    GitHubRepoSettings,
    HTTP_SPEC,
    HTTPSettings,
    LOCAL_SPEC,
    LocalSettings,
    S3_SPEC,
    S3Settings,
    SMB_SPEC,
    SMBSettings,
    SSH_SPEC,
    SSHSettings,
)
from mountainash_utils_files.settings.registry import (
    STORAGE_REGISTRY,
    get_spec,
    get_settings_class,
    register,
)


EXPECTED_PROVIDERS = {
    "s3",
    "gcs",
    "azure_storage",
    "ssh",
    "ftp",
    "smb",
    "local",
    "github_repo",
    "http",
}


@pytest.mark.unit
class TestStorageRegistry:
    def test_registry_name(self):
        """The registry exposes the expected domain name."""
        assert STORAGE_REGISTRY.name == "storage"

    def test_all_eight_providers_registered(self):
        """All 8 Phase 4 specs register themselves at import time."""
        registered = set(STORAGE_REGISTRY.descriptors.keys())
        missing = EXPECTED_PROVIDERS - registered
        assert not missing, f"missing from STORAGE_REGISTRY: {missing}"

    def test_no_unexpected_providers(self):
        """Only the 8 expected providers are registered (no stragglers)."""
        registered = set(STORAGE_REGISTRY.descriptors.keys())
        extras = registered - EXPECTED_PROVIDERS
        assert not extras, f"unexpected extras in STORAGE_REGISTRY: {extras}"

    @pytest.mark.parametrize(
        "name,expected_spec",
        [
            ("s3", S3_SPEC),
            ("gcs", GCS_SPEC),
            ("azure_storage", AZURE_STORAGE_SPEC),
            ("ssh", SSH_SPEC),
            ("ftp", FTP_SPEC),
            ("smb", SMB_SPEC),
            ("local", LOCAL_SPEC),
            ("github_repo", GITHUB_REPO_SPEC),
        ],
    )
    def test_get_spec_returns_canonical_spec(self, name, expected_spec):
        """get_spec() returns the exact module-level spec object."""
        assert get_spec(name) is expected_spec

    @pytest.mark.parametrize(
        "name,expected_class",
        [
            ("s3", S3Settings),
            ("gcs", GCSSettings),
            ("azure_storage", AzureStorageSettings),
            ("ssh", SSHSettings),
            ("ftp", FTPSettings),
            ("smb", SMBSettings),
            ("local", LocalSettings),
            ("github_repo", GitHubRepoSettings),
        ],
    )
    def test_get_settings_class_returns_registered_class(
        self, name, expected_class
    ):
        """get_settings_class() returns the class registered via @register."""
        assert get_settings_class(name) is expected_class

    def test_nonexistent_provider_raises_key_error(self):
        """Looking up an unknown provider name raises ``KeyError``."""
        with pytest.raises(KeyError):
            get_spec("does_not_exist")

    def test_register_is_bound_to_storage_registry(self):
        """The exported ``register`` decorator targets STORAGE_REGISTRY."""
        from mountainash_utils_files.settings.descriptor import (
            ParameterSpec,
            StorageDescriptor,
        )
        from mountainash_utils_files.settings.profile import StorageProfile
        from mountainash_auth_client import CONST_AUTH_MODE

        dummy_spec = StorageDescriptor(
            name="_test_registry_binding",
            provider_type="_test",
            parameters=[
                ParameterSpec(name="FOO", type=str, tier="core", default=None)
            ],
            default_auth=CONST_AUTH_MODE.NONE,
            supported_auth=frozenset({CONST_AUTH_MODE.NONE}),
        )
        snapshot = STORAGE_REGISTRY._snapshot_for_tests()
        try:
            @register
            class _DummySettings(StorageProfile):
                __spec__ = dummy_spec

            assert "_test_registry_binding" in STORAGE_REGISTRY.descriptors
            assert get_settings_class("_test_registry_binding") is _DummySettings
        finally:
            STORAGE_REGISTRY._reset_for_tests(*snapshot)

    def test_reset_for_tests_restores_snapshot(self):
        """_reset_for_tests rolls back to the snapshot state."""
        from mountainash_utils_files.settings.descriptor import (
            ParameterSpec,
            StorageDescriptor,
        )
        from mountainash_utils_files.settings.profile import StorageProfile
        from mountainash_auth_client import CONST_AUTH_MODE

        snapshot = STORAGE_REGISTRY._snapshot_for_tests()
        tmp_spec = StorageDescriptor(
            name="_snapshot_dummy",
            provider_type="_test",
            parameters=[
                ParameterSpec(name="BAR", type=str, tier="core", default=None)
            ],
            default_auth=CONST_AUTH_MODE.NONE,
            supported_auth=frozenset({CONST_AUTH_MODE.NONE}),
        )

        @register
        class _TmpSettings(StorageProfile):
            __spec__ = tmp_spec

        assert "_snapshot_dummy" in STORAGE_REGISTRY.descriptors

        STORAGE_REGISTRY._reset_for_tests(*snapshot)

        assert "_snapshot_dummy" not in STORAGE_REGISTRY.descriptors
        # Original 8 providers still present.
        for name in EXPECTED_PROVIDERS:
            assert name in STORAGE_REGISTRY.descriptors

    def test_registry_supports_contains(self):
        """The wrapper supports ``in`` membership checks by name."""
        assert "s3" in STORAGE_REGISTRY
        assert "definitely_not_here" not in STORAGE_REGISTRY
