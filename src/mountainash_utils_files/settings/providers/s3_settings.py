"""Consolidated S3-family settings (AWS S3, S3 Express, R2, MinIO, B2).

Collapses five per-flavor settings classes into one :class:`S3Settings`
class discriminated by a ``FLAVOR`` field. All five flavors wrap boto3 for
data-plane operations; the only structural differences are endpoint URL,
addressing-style constraints, and a couple of flavor-specific fields
(``ACCOUNT_ID`` for R2 endpoint templating).

Mirrors the Phase 3 ``AWSSecretsSettings`` pattern: the class is a two-line
shell; all parameters live on the descriptor; the adapter
(:func:`mountainash_utils_files.settings.adapters.s3.build_handler_kwargs`)
produces boto3 kwargs.
"""

from __future__ import annotations

import typing as t

from mountainash_auth_client import CONST_AUTH_MODE

from ..descriptor import ParameterSpec, StorageDescriptor
from ..profile import StorageProfile
from ..registry import register
from ...constants import CONST_STORAGE_PROVIDER_TYPE

__all__ = ["S3_SPEC", "S3Settings", "validate_flavor"]


_VALID_FLAVORS: frozenset[str] = frozenset({"aws", "express", "r2", "minio", "b2"})


def validate_flavor(v: str) -> str:
    """Validate the S3 ``FLAVOR`` discriminator."""
    if v not in _VALID_FLAVORS:
        raise ValueError(
            f"Invalid S3 flavor: {v!r}. Must be one of {sorted(_VALID_FLAVORS)}."
        )
    return v


def _validate_addressing_style(v: str) -> str:
    valid = {"auto", "path", "virtual"}
    if v not in valid:
        raise ValueError(
            f"Invalid addressing style: {v!r}. Must be one of {sorted(valid)}."
        )
    return v


S3_SPEC = StorageDescriptor(
    name="s3",
    # Canonical provider_type is AWS S3; all five flavors are re-registered
    # in the backend layer so that CONST_STORAGE_PROVIDER_TYPE.{R2,S3EXPRESS,
    # MINIO,B2} also resolve to the same S3 backend class.
    provider_type=CONST_STORAGE_PROVIDER_TYPE.S3,
    sdk_package="boto3",
    handler_module="mountainash_utils_files.storage_backends.s3",
    handler_class="S3StorageBackend",
    supports_streaming=True,
    supports_multipart=True,
    read_only=False,
    parameters=[
        ParameterSpec(
            name="FLAVOR",
            type=str,
            tier="core",
            default="aws",
            validator=validate_flavor,
            description=(
                "S3-compatible flavor: aws | express | r2 | minio | b2. "
                "Dispatches endpoint URL and addressing-style selection."
            ),
        ),
        ParameterSpec(
            name="REGION",
            type=str,
            tier="core",
            default="us-east-1",
            driver_key="region_name",
            description="AWS-style region name (e.g. us-east-1).",
        ),
        ParameterSpec(
            name="BUCKET",
            type=str,
            tier="core",
            default=None,
            description=(
                "Default bucket. Optional client-level metadata; boto3 takes "
                "bucket per-operation, not at client construction."
            ),
        ),
        ParameterSpec(
            name="ACCOUNT_ID",
            type=str,
            tier="advanced",
            default=None,
            description=(
                "Cloudflare account ID. Used only when FLAVOR='r2' to build "
                "the default endpoint URL https://{ACCOUNT_ID}.r2.cloudflarestorage.com."
            ),
        ),
        ParameterSpec(
            name="ENDPOINT_URL",
            type=str,
            tier="advanced",
            default=None,
            driver_key="endpoint_url",
            description=(
                "Override the default endpoint URL. Required for FLAVOR='minio'. "
                "Auto-derived from ACCOUNT_ID / REGION for r2 / b2."
            ),
        ),
        ParameterSpec(
            name="USE_SSL",
            type=bool,
            tier="advanced",
            default=True,
            driver_key="use_ssl",
            description="Whether to use HTTPS (boto3 `use_ssl`).",
        ),
        ParameterSpec(
            name="ADDRESSING_STYLE",
            type=str,
            tier="advanced",
            default="auto",
            validator=_validate_addressing_style,
            description="S3 addressing style: auto | path | virtual.",
        ),
        ParameterSpec(
            name="ACCELERATE_ENDPOINT",
            type=bool,
            tier="advanced",
            default=False,
            description="Enable S3 Transfer Acceleration (aws flavor only).",
        ),
        ParameterSpec(
            name="DUALSTACK_ENDPOINT",
            type=bool,
            tier="advanced",
            default=False,
            description="Enable dual-stack (IPv6) endpoint (aws flavor only).",
        ),
        ParameterSpec(
            name="VERIFY_SSL",
            type=bool,
            tier="advanced",
            default=True,
            description="Whether to verify SSL certificates.",
        ),
        ParameterSpec(
            name="ROLE_ARN",
            type=str,
            tier="advanced",
            default=None,
            description="IAM Role ARN to assume via STS before creating the client.",
        ),
        ParameterSpec(
            name="CONNECT_TIMEOUT",
            type=t.Optional[float],
            tier="advanced",
            default=None,
            description=(
                "Connection timeout in seconds for boto3 client. "
                "None defers to boto3 default (~60s)."
            ),
        ),
        ParameterSpec(
            name="READ_TIMEOUT",
            type=t.Optional[float],
            tier="advanced",
            default=None,
            description=(
                "Read timeout in seconds for boto3 client. "
                "None defers to boto3 default (~60s)."
            ),
        ),
    ],
    default_auth=CONST_AUTH_MODE.IAM,
    supported_auth=frozenset({CONST_AUTH_MODE.IAM, CONST_AUTH_MODE.TOKEN, CONST_AUTH_MODE.NONE}),
    metadata={
        "flavor_endpoints": {
            "aws": None,
            "express": None,
            "r2": "https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
            "minio": None,
            "b2": "https://s3.{REGION}.backblazeb2.com",
        },
    },
)


# Adapter is imported lazily to avoid a circular import with the adapters
# package which depends on StorageProfile.
def _adapter(profile: "S3Settings", auth=None) -> dict[str, t.Any]:
    from ..adapters.s3 import build_handler_kwargs

    return build_handler_kwargs(profile, auth)


@register
class S3Settings(StorageProfile):
    """Unified S3-family settings for AWS S3, S3 Express, R2, MinIO, and B2.

    Fields are installed from :data:`S3_SPEC` by the
    :class:`~mountainash_settings.profiles.Profile` metaclass. The
    ``FLAVOR`` field discriminates per-flavor endpoint defaults and
    addressing-style constraints; see
    :func:`~mountainash_utils_files.settings.adapters.s3.build_handler_kwargs`.
    """

    __spec__ = S3_SPEC
    __adapter__ = staticmethod(_adapter)

    def get_connection_url(self) -> str:
        """Return a best-effort connection URL for logging/inspection."""
        flavor = getattr(self, "FLAVOR", "aws")
        endpoint_url = getattr(self, "ENDPOINT_URL", None)
        if endpoint_url:
            return str(endpoint_url)
        region = getattr(self, "REGION", "us-east-1")
        account_id = getattr(self, "ACCOUNT_ID", None)
        if flavor == "r2" and account_id:
            return f"https://{account_id}.r2.cloudflarestorage.com"
        if flavor == "b2":
            return f"https://s3.{region}.backblazeb2.com"
        if flavor == "express":
            bucket = getattr(self, "BUCKET", None) or ""
            return f"https://{bucket}.{region}.amazonaws.com"
        return f"https://s3.{region}.amazonaws.com"
