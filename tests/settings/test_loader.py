"""Tests for resolve_storage — the load_storage successor."""

from __future__ import annotations

import pytest

from mountainash_settings import SettingsParameters
from mountainash_transport import (
    ProfileNotFoundError,
    ProfileResolutionError,
    StorageError,
)
from mountainash_transport.settings.storage.loader import resolve_storage


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
        from mountainash_settings.secrets import MemorySecretStore

        backend = MemorySecretStore()
        backend.set("aws", {"secret_key": "resolved-secret"})

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
            config_files=[str(cfg)], secret_store=backend
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


def test_selected_readers_are_isolated(tmp_path):
    from mountainash_settings.secrets import MemorySecretStore

    cfg = tmp_path / "profiles.yaml"
    cfg.write_text(
        PROFILES_YAML.replace(
            "SECRET_ACCESS_KEY: shhh", "SECRET_ACCESS_KEY: secret:aws.secret_key"
        )
    )
    first, second = MemorySecretStore(), MemorySecretStore()
    first.set("aws", {"secret_key": "first"})
    second.set("aws", {"secret_key": "second"})
    for store, expected in ((first, "first"), (second, "second"), (first, "first")):
        params = SettingsParameters.create(config_files=[str(cfg)], secret_store=store)
        _, auth = resolve_storage("lake", settings_parameters=params)
        assert auth.SECRET_ACCESS_KEY.get_secret_value() == expected
    # The reader is borrowed, and remains usable after resolution.
    first.set("after", {"value": "still open"})
    assert first.get("after") == {"value": "still open"}


def test_reference_without_reader_fails_value_free(tmp_path, monkeypatch):
    from mountainash_settings.secrets.errors import SecretCapabilityError

    cfg = tmp_path / "profiles.yaml"
    cfg.write_text(
        PROFILES_YAML.replace(
            "SECRET_ACCESS_KEY: shhh",
            "SECRET_ACCESS_KEY: secret:private-record.private-field",
        )
    )
    monkeypatch.setenv("MOUNTAINASH_PROFILES_CONFIG", str(cfg))
    monkeypatch.setenv("MOUNTAINASH_SECRETS_PROVIDER", "arbitrary-provider")
    with pytest.raises(SecretCapabilityError) as caught:
        resolve_storage("lake")
    assert "private-record" not in str(caught.value)
    assert "private-field" not in repr(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize("record", [None, {"other": "value"}])
def test_missing_record_or_field_remains_failure(tmp_path, record):
    from mountainash_settings.secrets import MemorySecretStore

    store = MemorySecretStore()
    if record is not None:
        store.set("aws", record)
    cfg = tmp_path / "profiles.yaml"
    cfg.write_text(
        PROFILES_YAML.replace(
            "SECRET_ACCESS_KEY: shhh", "SECRET_ACCESS_KEY: secret:aws.secret_key"
        )
    )
    params = SettingsParameters.create(config_files=[str(cfg)], secret_store=store)
    with pytest.raises(KeyError):
        resolve_storage("lake", settings_parameters=params)


def test_nested_references_resolve_once_and_reference_shaped_values_are_data():
    from mountainash_settings.secrets import MemorySecretStore

    class CountingReader:
        def __init__(self):
            self.store = MemorySecretStore()
            self.store.set(
                "values", {"root": "secret:not.a.lookup", "option": "resolved"}
            )
            self.reads = []

        def get(self, key):
            self.reads.append(key)
            return self.store.get(key)

    reader = CountingReader()
    params = SettingsParameters.create(
        secret_store=reader,
        storage_profiles={
            "nested": {
                "provider": "local",
                "parameters": {
                    "ROOT_PATH": "secret:values.root",
                    "MOUNT_SPEC": {
                        "options": [
                            "secret:values.option",
                            {"nested": "secret:values.option"},
                        ]
                    },
                },
            },
            "lake": {
                "provider": "s3",
                "auth": {
                    "mode": "iam",
                    "parameters": {
                        "SECRET_ACCESS_KEY": "secret:values.root",
                    },
                },
            },
        },
    )
    profile, _ = resolve_storage("nested", settings_parameters=params)
    assert profile.ROOT_PATH == "secret:not.a.lookup"
    assert profile.MOUNT_SPEC == {"options": ["resolved", {"nested": "resolved"}]}
    assert reader.reads == ["values", "values", "values", "values"]
    _, auth = resolve_storage("lake", settings_parameters=params)
    assert auth.SECRET_ACCESS_KEY.get_secret_value() == "secret:not.a.lookup"
    assert reader.reads == ["values"] * 8


def test_reader_errors_propagate_unchanged():
    failure = RuntimeError("reader unavailable")

    class BrokenReader:
        def get(self, key):
            raise failure

    params = SettingsParameters.create(
        secret_store=BrokenReader(),
        storage_profiles={
            "scratch": {
                "provider": "local",
                "parameters": {"ROOT_PATH": "secret:record.field"},
            },
        },
    )
    with pytest.raises(RuntimeError) as caught:
        resolve_storage("scratch", settings_parameters=params)
    assert caught.value is failure


def test_ambient_provider_variable_does_not_select_reader(tmp_path, monkeypatch):
    cfg = tmp_path / "profiles.yaml"
    cfg.write_text(PROFILES_YAML)
    monkeypatch.setenv("MOUNTAINASH_PROFILES_CONFIG", str(cfg))
    monkeypatch.setenv("MOUNTAINASH_SECRETS_PROVIDER", "arbitrary-provider")
    profile, _ = resolve_storage("scratch")
    assert profile.ROOT_PATH == "/tmp/scratch"


@pytest.mark.parametrize("section", ["storage", "auth"])
@pytest.mark.parametrize("from_file", [False, True])
def test_resolved_validation_failure_has_no_value_or_exception_chain(
    section, from_file, tmp_path
):
    from mountainash_settings.secrets import MemorySecretStore
    import yaml

    sentinel = "private-invalid-choice-97241"
    store = MemorySecretStore()
    store.set("private", {"value": sentinel})
    if section == "storage":
        block = {"provider": "s3", "parameters": {"FLAVOR": "secret:private.value"}}
    else:
        block = {
            "provider": "gcs",
            "parameters": {"PROJECT": "test-project"},
            "auth": {
                "mode": "service_account",
                "parameters": {"INFO": "secret:private.value"},
            },
        }
    if from_file:
        cfg = tmp_path / "profiles.yaml"
        cfg.write_text(yaml.safe_dump({"storage_profiles": {"invalid": block}}))
        params = SettingsParameters.create(secret_store=store, config_files=[str(cfg)])
    else:
        params = SettingsParameters.create(
            secret_store=store, storage_profiles={"invalid": block}
        )
    with pytest.raises(ProfileResolutionError) as caught:
        resolve_storage("invalid", settings_parameters=params)
    assert sentinel not in str(caught.value)
    assert sentinel not in repr(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_ordinary_validation_failure_keeps_diagnostics():
    params = SettingsParameters.create(
        storage_profiles={
            "invalid": {
                "provider": "s3",
                "parameters": {"FLAVOR": "ordinary-invalid-choice"},
            },
        }
    )
    with pytest.raises(ProfileResolutionError) as caught:
        resolve_storage("invalid", settings_parameters=params)
    assert "FLAVOR" in str(caught.value)
    assert "ordinary-invalid-choice" in str(caught.value)


@pytest.mark.parametrize("from_file", [False, True])
def test_selected_reader_does_not_hide_non_secret_validation(tmp_path, from_file):
    from mountainash_settings.secrets import MemorySecretStore
    import yaml

    store = MemorySecretStore()
    store.set("aws", {"secret_key": "private-good-value"})
    data = {
        "storage_profiles": {
            "invalid": {
                "provider": "s3",
                "parameters": {
                    "FLAVOR": "ordinary-invalid-choice",
                    "REGION": "secret:aws.secret_key",
                },
                "auth": {
                    "mode": "iam",
                    "parameters": {"SECRET_ACCESS_KEY": "secret:aws.secret_key"},
                },
            }
        }
    }
    if from_file:
        cfg = tmp_path / "profiles.yaml"
        cfg.write_text(yaml.safe_dump(data))
        params = SettingsParameters.create(config_files=[str(cfg)], secret_store=store)
    else:
        params = SettingsParameters.create(secret_store=store, **data)
    with pytest.raises(ProfileResolutionError) as caught:
        resolve_storage("invalid", settings_parameters=params)
    assert "FLAVOR" in str(caught.value)
    assert "ordinary-invalid-choice" in str(caught.value)


def test_config_cannot_supply_reference_location_metadata(tmp_path):
    from mountainash_settings.secrets import MemorySecretStore

    store = MemorySecretStore()
    store.set("private", {"value": "private-invalid-choice"})
    cfg = tmp_path / "profiles.yaml"
    cfg.write_text("""
storage_profiles:
  invalid:
    provider: s3
    parameters:
      FLAVOR: secret:private.value
reference_inputs:
  invalid:
    parameters:
      FLAVOR: false
""")
    params = SettingsParameters.create(config_files=[str(cfg)], secret_store=store)
    with pytest.raises(ValueError, match="reserved"):
        resolve_storage("invalid", settings_parameters=params)
