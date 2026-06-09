"""Tests for S3StorageProfile — consolidated S3-family settings.

Covers the flavor discriminator matrix (aws / express / r2 / minio / b2),
the adapter-produced boto3 kwargs, ROLE_ARN nested-envelope path, and
regression guards for USE_SSL default + PATH_STYLE removal.
"""

from __future__ import annotations

import pytest

from mountainash_auth_client import IAMAuth, NoAuth
from pydantic import SecretStr

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.settings.profiles import (
    S3_SPEC,
    S3StorageProfile,
    validate_flavor,
)


# PROVIDER_TYPE aliases per flavor so errors surface the right constant.
_PROVIDER_TYPE_BY_FLAVOR: dict[str, str] = {
    "aws": CONST_STORAGE_PROVIDER_TYPE.S3,
    "express": CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS,
    "r2": CONST_STORAGE_PROVIDER_TYPE.R2,
    "minio": CONST_STORAGE_PROVIDER_TYPE.MINIO,
    "b2": CONST_STORAGE_PROVIDER_TYPE.B2,
}


def _make(
    flavor: str,
    *,
    auth=None,
    region: str = "us-east-1",
    **extra,
):
    """Return an S3StorageProfile for ``flavor`` with minimal required fields."""
    kwargs = {
        "PROVIDER_TYPE": _PROVIDER_TYPE_BY_FLAVOR[flavor],
        "FLAVOR": flavor,
        "REGION": region,
        "auth": auth if auth is not None else NoAuth(),
    }
    kwargs.update(extra)
    return S3StorageProfile(**kwargs)


@pytest.mark.unit
class TestFlavorValidator:
    @pytest.mark.parametrize(
        "flavor", ["aws", "express", "r2", "minio", "b2"]
    )
    def test_valid_flavor_accepted(self, flavor):
        assert validate_flavor(flavor) == flavor

    @pytest.mark.parametrize(
        "bad", ["AWS", "wasabi", "s3", "", "oracle"]
    )
    def test_invalid_flavor_raises(self, bad):
        with pytest.raises(ValueError):
            validate_flavor(bad)


@pytest.mark.unit
class TestS3StorageProfileConstruction:
    @pytest.mark.parametrize(
        "flavor", ["aws", "express", "r2", "minio", "b2"]
    )
    def test_instantiates_per_flavor(self, flavor):
        # minio needs an ENDPOINT_URL to survive to_handler_kwargs but
        # construction-only doesn't invoke the adapter.
        s = _make(flavor)
        assert s.FLAVOR == flavor
        assert s.REGION == "us-east-1"

    def test_invalid_flavor_rejected_at_construction(self):
        with pytest.raises(Exception):
            _make("not-a-real-flavor")

    def test_use_ssl_default_is_true(self):
        """Regression: USE_SSL now defaults True (old code had False)."""
        s = _make("aws")
        assert s.USE_SSL is True

    def test_path_style_field_removed(self):
        """PATH_STYLE was retired in favour of ADDRESSING_STYLE."""
        assert "PATH_STYLE" not in S3StorageProfile.model_fields
        assert "ADDRESSING_STYLE" in S3StorageProfile.model_fields


@pytest.mark.unit
class TestS3HandlerKwargsMatrix:
    """Flavor × adapter-output matrix."""

    @pytest.mark.parametrize(
        "flavor", ["aws", "express", "r2", "b2"]
    )
    def test_flat_dict_has_service_and_region(self, flavor):
        # For r2, we must supply ACCOUNT_ID to derive the endpoint.
        extra = {"ACCOUNT_ID": "myacct"} if flavor == "r2" else {}
        s = _make(flavor, **extra)
        kw = s.to_handler_kwargs()
        assert kw["service_name"] == "s3"
        assert "region_name" in kw
        assert kw["use_ssl"] is True
        assert kw["verify"] is True

    def test_aws_default_has_no_endpoint_override(self):
        """AWS flavor lets boto3's default resolver pick the endpoint."""
        s = _make("aws")
        kw = s.to_handler_kwargs()
        assert "endpoint_url" not in kw

    def test_r2_auto_builds_endpoint_from_account_id(self):
        s = _make("r2", ACCOUNT_ID="tenant123")
        kw = s.to_handler_kwargs()
        assert kw["endpoint_url"] == "https://tenant123.r2.cloudflarestorage.com"
        # R2 forces region_name="auto" regardless of REGION.
        assert kw["region_name"] == "auto"

    def test_r2_without_endpoint_or_account_raises(self):
        s = _make("r2")
        with pytest.raises(ValueError, match="R2"):
            s.to_handler_kwargs()

    def test_minio_requires_explicit_endpoint_url(self):
        s = _make("minio")
        with pytest.raises(ValueError, match="MinIO"):
            s.to_handler_kwargs()

    def test_minio_with_endpoint_url_works(self):
        s = _make("minio", ENDPOINT_URL="http://minio.internal:9000")
        kw = s.to_handler_kwargs()
        assert kw["endpoint_url"] == "http://minio.internal:9000"

    def test_b2_default_endpoint_templated_from_region(self):
        s = _make("b2", region="us-west-002")
        kw = s.to_handler_kwargs()
        assert kw["endpoint_url"] == "https://s3.us-west-002.backblazeb2.com"

    def test_express_forces_virtual_addressing(self):
        s = _make("express")
        kw = s.to_handler_kwargs()
        # The Config object should carry virtual addressing style.
        config = kw.get("config")
        # botocore.config.Config._user_provided_options is private — just
        # inspect the public dict-of-dicts.
        s3_cfg = config._user_provided_options.get("s3") if config else None
        assert s3_cfg is not None
        assert s3_cfg.get("addressing_style") == "virtual"


@pytest.mark.unit
class TestS3AuthIntegration:
    def test_iam_auth_credentials_flow_to_boto(self):
        auth = IAMAuth(
            ACCESS_KEY_ID="AKID",
            SECRET_ACCESS_KEY=SecretStr("secret"),
        )
        s = _make("aws")
        kw = s.to_handler_kwargs(auth_profile=auth)
        assert kw["aws_access_key_id"] == "AKID"
        assert kw["aws_secret_access_key"] == "secret"

    def test_noauth_surfaces_no_creds(self):
        s = _make("aws")
        kw = s.to_handler_kwargs()
        assert "aws_access_key_id" not in kw
        assert "aws_secret_access_key" not in kw


@pytest.mark.unit
class TestS3RoleArnEnvelope:
    """ROLE_ARN path returns a nested ``{base_kwargs, role_arn, session_name}`` dict."""

    def test_role_arn_produces_nested_envelope(self):
        s = _make(
            "aws",
            ROLE_ARN="arn:aws:iam::123456789012:role/MyRole",
        )
        kw = s.to_handler_kwargs()
        assert kw["role_arn"] == "arn:aws:iam::123456789012:role/MyRole"
        assert "base_kwargs" in kw
        assert "session_name" in kw
        assert kw["base_kwargs"]["service_name"] == "s3"

    def test_no_role_arn_flat_dict(self):
        """Absent ROLE_ARN yields a flat dict — not the envelope."""
        s = _make("aws")
        kw = s.to_handler_kwargs()
        assert "role_arn" not in kw
        assert "base_kwargs" not in kw


@pytest.mark.unit
class TestS3Descriptor:
    def test_descriptor_name(self):
        assert S3_SPEC.name == "s3"

    def test_descriptor_sdk_is_boto3(self):
        assert S3_SPEC.sdk_package == "boto3"

    def test_descriptor_handler_class(self):
        assert S3_SPEC.handler_class == "S3StorageBackend"

    def test_descriptor_not_read_only(self):
        assert S3_SPEC.read_only is False

    def test_descriptor_supports_multipart(self):
        assert S3_SPEC.supports_multipart is True


@pytest.mark.unit
class TestS3TimeoutConfiguration:
    """CONNECT_TIMEOUT and READ_TIMEOUT propagate to botocore.config.Config."""

    def test_timeouts_default_to_none(self):
        s = _make("aws")
        assert s.CONNECT_TIMEOUT is None
        assert s.READ_TIMEOUT is None

    def test_timeouts_in_handler_kwargs_when_set(self):
        s = _make("aws", CONNECT_TIMEOUT=5.0, READ_TIMEOUT=30.0)
        kw = s.to_handler_kwargs()
        config = kw["config"]
        assert config._user_provided_options.get("connect_timeout") == 5.0
        assert config._user_provided_options.get("read_timeout") == 30.0

    def test_timeouts_omitted_from_config_when_none(self):
        s = _make("aws")
        kw = s.to_handler_kwargs()
        config = kw["config"]
        opts = config._user_provided_options
        assert "connect_timeout" not in opts
        assert "read_timeout" not in opts

    def test_explicit_none_omitted_from_config(self):
        s = _make("aws", CONNECT_TIMEOUT=None, READ_TIMEOUT=None)
        kw = s.to_handler_kwargs()
        config = kw["config"]
        opts = config._user_provided_options
        assert "connect_timeout" not in opts
        assert "read_timeout" not in opts
