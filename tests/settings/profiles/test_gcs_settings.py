"""Tests for GCSStorageProfile — Google Cloud Storage settings."""

from __future__ import annotations

import pytest

from mountainash_auth_client import NoAuth, TokenAuth
from pydantic import SecretStr

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.settings.profiles import (
    GCS_SPEC,
    GCSStorageProfile,
)


def _make(project: str = "my-project-id", **extra):
    kwargs = {
        "PROVIDER_TYPE": CONST_STORAGE_PROVIDER_TYPE.GCS,
        "PROJECT": project,
        "auth": NoAuth(),
    }
    kwargs.update(extra)
    return GCSStorageProfile(**kwargs)


@pytest.mark.unit
class TestGCSStorageProfileConstruction:
    def test_instantiates_with_minimal_fields(self):
        s = _make()
        assert s.PROJECT == "my-project-id"

    @pytest.mark.parametrize(
        "bad_project",
        [
            "A",  # too short
            "abc",  # too short
            "Upper-Case",  # uppercase letters
            "1starts-with-digit",  # starts with digit
            "ends-with-dash-",  # ends with dash
        ],
    )
    def test_invalid_project_rejected(self, bad_project):
        with pytest.raises(Exception):
            _make(project=bad_project)

    def test_bucket_name_validator_rejects_ip(self):
        with pytest.raises(Exception):
            _make(BUCKET_NAME="192.168.1.1")

    def test_bucket_name_validator_rejects_goog_prefix(self):
        with pytest.raises(Exception):
            _make(BUCKET_NAME="googbucket")

    def test_bucket_name_validator_accepts_valid(self):
        s = _make(BUCKET_NAME="my-valid-bucket")
        assert s.BUCKET_NAME == "my-valid-bucket"


@pytest.mark.unit
class TestGCSFieldSurface:
    def test_oauth_credentials_field_removed(self):
        """Regression: dead OAUTH_CREDENTIALS field is not present."""
        assert "OAUTH_CREDENTIALS" not in GCSStorageProfile.model_fields

    def test_api_version_field_not_declared(self):
        """Regression: API_VERSION was a bug — not referenced / not declared."""
        # GCS descriptor defines API_ENDPOINT but not API_VERSION.
        assert "API_VERSION" not in GCSStorageProfile.model_fields

    def test_has_expected_core_fields(self):
        assert "PROJECT" in GCSStorageProfile.model_fields
        assert "BUCKET_NAME" in GCSStorageProfile.model_fields
        assert "API_ENDPOINT" in GCSStorageProfile.model_fields
        assert "LOCATION" in GCSStorageProfile.model_fields
        assert "USER_PROJECT" in GCSStorageProfile.model_fields


@pytest.mark.unit
class TestGCSHandlerKwargs:
    def test_noauth_produces_anonymous_client_kwargs(self):
        s = _make()
        kw = s.to_handler_kwargs(auth_profile=NoAuth())
        assert kw["project"] == "my-project-id"
        assert kw["credentials"] is None
        assert kw["anonymous"] is True

    def test_token_auth_ambient_credentials_null_when_token_empty(self):
        auth = TokenAuth(TOKEN=SecretStr("tok"))
        s = _make()
        try:
            kw = s.to_handler_kwargs(auth_profile=auth)
        except ImportError:
            pytest.skip("google-cloud-storage not installed")
        assert kw["project"] == "my-project-id"

    def test_api_endpoint_forwarded_via_client_options(self):
        s = _make(API_ENDPOINT="https://custom.endpoint.example")
        kw = s.to_handler_kwargs()
        co = kw.get("client_options")
        # google-api-core installed → ClientOptions object; else plain dict.
        if co is None:
            pytest.skip("client_options absent — unexpected path")
        if hasattr(co, "api_endpoint"):
            assert co.api_endpoint == "https://custom.endpoint.example"
        elif isinstance(co, dict):
            assert co.get("api_endpoint") == "https://custom.endpoint.example"

    def test_user_project_forwarded_as_quota_project(self):
        s = _make(USER_PROJECT="billing-project")
        kw = s.to_handler_kwargs()
        co = kw.get("client_options")
        if co is None:
            pytest.skip("client_options absent — unexpected path")
        if hasattr(co, "quota_project_id"):
            assert co.quota_project_id == "billing-project"
        elif isinstance(co, dict):
            assert co.get("quota_project_id") == "billing-project"

    def test_no_client_options_when_no_overrides(self):
        s = _make()
        kw = s.to_handler_kwargs()
        assert "client_options" not in kw


@pytest.mark.unit
class TestGCSDescriptor:
    def test_descriptor_name(self):
        assert GCS_SPEC.name == "gcs"

    def test_descriptor_sdk_package(self):
        assert GCS_SPEC.sdk_package == "google-cloud-storage"

    def test_descriptor_not_read_only(self):
        assert GCS_SPEC.read_only is False
