"""Tests for resolve_storage — the load_storage successor."""
from __future__ import annotations

from mountainash_transport import (
    ProfileNotFoundError,
    ProfileResolutionError,
    StorageError,
)


class TestResolverExceptions:
    def test_hierarchy(self):
        err = ProfileNotFoundError("missing", available=["scratch", "lake"])
        assert isinstance(err, ProfileResolutionError)
        assert isinstance(err, StorageError)

    def test_not_found_message_names_profile_and_available(self):
        err = ProfileNotFoundError("missing", available=["scratch"])
        assert "missing" in str(err)
        assert "scratch" in str(err)
        assert err.name == "missing"
        assert err.available == ["scratch"]

    def test_resolution_error_carries_name_and_reason(self):
        err = ProfileResolutionError("lake", "unknown provider 'nosuch'")
        assert err.name == "lake"
        assert "nosuch" in str(err)


import pytest

from mountainash_settings import SettingsParameters
from mountainash_transport.settings.storage.loader import resolve_storage

PROFILES_YAML = """
storage_profiles:
  scratch:
    provider: local
    parameters:
      ROOT_PATH: /tmp/scratch
  lake:
    provider: s3
    parameters:
      FLAVOR: aws
      REGION: ap-southeast-2
      BUCKET: test-lake
    auth:
      mode: iam
      parameters:
        ACCESS_KEY_ID: AKIATEST
        SECRET_ACCESS_KEY: shhh
  broken-provider:
    provider: nosuch
  bad-pairing:
    provider: local
    auth:
      mode: password
      parameters:
        USERNAME: u
        PASSWORD: p
"""


@pytest.fixture()
def config_params(tmp_path):
    cfg = tmp_path / "profiles.yaml"
    cfg.write_text(PROFILES_YAML)
    return SettingsParameters.create(config_files=[str(cfg)])


class TestResolveStorage:
    def test_local_profile_with_default_auth(self, config_params):
        from mountainash_auth_client import NoAuthProfile
        from mountainash_transport.settings.storage.profiles import LocalStorageProfile

        profile, auth = resolve_storage("scratch", settings_parameters=config_params)
        assert isinstance(profile, LocalStorageProfile)
        assert profile.ROOT_PATH == "/tmp/scratch"
        assert isinstance(auth, NoAuthProfile)

    def test_s3_profile_with_iam_auth(self, config_params):
        from mountainash_auth_client import IAMAuthProfile
        from mountainash_transport.settings.storage.profiles import S3StorageProfile

        profile, auth = resolve_storage("lake", settings_parameters=config_params)
        assert isinstance(profile, S3StorageProfile)
        assert profile.BUCKET == "test-lake"
        assert isinstance(auth, IAMAuthProfile)
        assert auth.ACCESS_KEY_ID == "AKIATEST"
        assert auth.SECRET_ACCESS_KEY.get_secret_value() == "shhh"

    def test_unknown_name_raises_not_found_listing_available(self, config_params):
        from mountainash_transport import ProfileNotFoundError

        with pytest.raises(ProfileNotFoundError) as ei:
            resolve_storage("nope", settings_parameters=config_params)
        assert "scratch" in str(ei.value)

    def test_unknown_provider_raises_resolution_error(self, config_params):
        from mountainash_transport import ProfileResolutionError

        with pytest.raises(ProfileResolutionError):
            resolve_storage("broken-provider", settings_parameters=config_params)

    def test_unsupported_pairing_fails_at_resolve_time(self, config_params):
        from mountainash_transport.connections.errors import UnsupportedAuthProfileError

        with pytest.raises(UnsupportedAuthProfileError):
            resolve_storage("bad-pairing", settings_parameters=config_params)

    def test_caller_settings_class_rejected(self, config_params, tmp_path):
        import dataclasses

        from mountainash_settings import MountainAshBaseSettings
        from mountainash_transport import ProfileResolutionError

        params = dataclasses.replace(
            config_params, settings_class=MountainAshBaseSettings
        )
        with pytest.raises(ProfileResolutionError):
            resolve_storage("scratch", settings_parameters=params)


class TestSecretResolution:
    def test_secret_reference_resolved_via_backend(self, tmp_path):
        from mountainash_settings import FilesystemBackend, replace_secrets_backend

        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir(mode=0o700)
        backend = FilesystemBackend(secrets_dir)
        backend.set("aws", {"secret_key": "resolved-secret"})
        replace_secrets_backend("loader-test", backend)

        cfg = tmp_path / "profiles.yaml"
        cfg.write_text(
            "storage_profiles:\n"
            "  lake:\n"
            "    provider: s3\n"
            "    parameters:\n"
            "      FLAVOR: aws\n"
            "      REGION: ap-southeast-2\n"
            "      BUCKET: test-lake\n"
            "    auth:\n"
            "      mode: iam\n"
            "      parameters:\n"
            "        ACCESS_KEY_ID: AKIATEST\n"
            '        SECRET_ACCESS_KEY: "secret:aws.secret_key"\n'
        )
        params = SettingsParameters.create(
            config_files=[str(cfg)], secrets_provider="loader-test"
        )
        _, auth = resolve_storage("lake", settings_parameters=params)
        assert auth.SECRET_ACCESS_KEY.get_secret_value() == "resolved-secret"


class TestAmbientEnvConfig:
    def test_env_var_config_file(self, tmp_path, monkeypatch):
        cfg = tmp_path / "ambient.yaml"
        cfg.write_text(
            "storage_profiles:\n"
            "  scratch:\n"
            "    provider: local\n"
            "    parameters:\n"
            "      ROOT_PATH: /tmp/ambient\n"
        )
        monkeypatch.setenv("MOUNTAINASH_PROFILES_CONFIG", str(cfg))
        profile, _ = resolve_storage("scratch")
        assert profile.ROOT_PATH == "/tmp/ambient"
