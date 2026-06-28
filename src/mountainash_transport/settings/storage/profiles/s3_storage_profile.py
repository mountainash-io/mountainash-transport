"""Consolidated S3-family settings (AWS S3, S3 Express, R2, MinIO, B2).

Collapses five per-flavor settings classes into one :class:`S3StorageProfile`
class discriminated by a ``FLAVOR`` field. All five flavors wrap boto3 for
data-plane operations; the only structural differences are endpoint URL,
addressing-style constraints, and a couple of flavor-specific fields
(``ACCOUNT_ID`` for R2 endpoint templating).

Mirrors the Phase 3 ``AWSSecretsSettings`` pattern: the class is a two-line
shell; all parameters live on the descriptor; the adapter
(:func:`mountainash_transport.settings.adapters.s3.build_handler_kwargs`)
produces boto3 kwargs.
"""

from __future__ import annotations

import typing as t

from mountainash_auth_client import CONST_AUTH_PROFILES
from mountainash_auth_client.targets import TargetFamily

from ...profile_spec import ParameterSpec, StorageProfileSpec
from mountainash_settings.profiles import Profile

from ..registry import register
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE

__all__ = ["S3_SPEC", "S3StorageProfile", "validate_flavor"]


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


S3_SPEC = StorageProfileSpec(
    name="s3",
    # Canonical provider_type is AWS S3; all five flavors are re-registered
    # in the backend layer so that CONST_STORAGE_PROVIDER_TYPE.{R2,S3EXPRESS,
    # MINIO,B2} also resolve to the same S3 backend class.
    provider_type=CONST_STORAGE_PROVIDER_TYPE.S3,
    sdk_package="boto3",
    handler_module="mountainash_transport.storage.backends.s3",
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
    default_auth=CONST_AUTH_PROFILES.IAM,
    supported_auth=frozenset({CONST_AUTH_PROFILES.IAM, CONST_AUTH_PROFILES.NONE}),
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


def _s3_boto_kwargs(profile: "S3StorageProfile", kw: dict[str, t.Any]) -> dict[str, t.Any]:
    """Build boto3 client kwargs, composing on the driver_key merge (``kw``).

    ``kw`` already carries the driver_key fields (region_name, use_ssl, and
    endpoint_url when ENDPOINT_URL is set). This recomputes the flavor-dependent
    region/endpoint/addressing and the botocore Config, preserving the exact
    output the legacy ``to_handler_kwargs`` produced.
    """
    try:
        import botocore.config as _botocore_config
    except ImportError:  # pragma: no cover - botocore is a boto3 transitive
        _botocore_config = None  # type: ignore[assignment]

    flavor = getattr(profile, "FLAVOR", "aws")
    region = getattr(profile, "REGION", None)
    endpoint_url = getattr(profile, "ENDPOINT_URL", None)
    account_id = getattr(profile, "ACCOUNT_ID", None)
    use_ssl = getattr(profile, "USE_SSL", True)
    addressing_style = profile._resolve_addressing_style(
        flavor, getattr(profile, "ADDRESSING_STYLE", "auto")
    )
    accelerate = bool(getattr(profile, "ACCELERATE_ENDPOINT", False))
    dualstack = bool(getattr(profile, "DUALSTACK_ENDPOINT", False))
    verify_ssl = getattr(profile, "VERIFY_SSL", True)

    effective_region = "auto" if flavor == "r2" else region

    base: dict[str, t.Any] = dict(kw)            # compose on driver_key output
    base["service_name"] = "s3"
    base["region_name"] = effective_region
    base["use_ssl"] = use_ssl
    base["verify"] = verify_ssl

    resolved_endpoint = profile._resolve_endpoint_url(
        flavor, region, endpoint_url, account_id
    )
    if resolved_endpoint is not None:
        base["endpoint_url"] = resolved_endpoint
    else:
        base.pop("endpoint_url", None)           # aws/express: never present

    if _botocore_config is not None:
        s3_config: dict[str, t.Any] = {"addressing_style": addressing_style}
        if flavor == "aws":
            if accelerate:
                s3_config["use_accelerate_endpoint"] = True
            if dualstack:
                s3_config["use_dualstack_endpoint"] = True
        config_kwargs: dict[str, t.Any] = {"s3": s3_config}
        connect_timeout = getattr(profile, "CONNECT_TIMEOUT", None)
        read_timeout = getattr(profile, "READ_TIMEOUT", None)
        if connect_timeout is not None:
            config_kwargs["connect_timeout"] = connect_timeout
        if read_timeout is not None:
            config_kwargs["read_timeout"] = read_timeout
        base["config"] = _botocore_config.Config(**config_kwargs)

    return base


@register
class S3StorageProfile(Profile):
    """Unified S3-family settings for AWS S3, S3 Express, R2, MinIO, and B2.

    Fields are installed from :data:`S3_SPEC` by the
    :class:`~mountainash_settings.profiles.Profile` metaclass. The
    ``FLAVOR`` field discriminates per-flavor endpoint defaults and
    addressing-style constraints; see
    :func:`~mountainash_transport.settings.adapters.s3.build_handler_kwargs`.
    """

    __spec__ = S3_SPEC
    __adapters__ = {TargetFamily.BOTO: _s3_boto_kwargs}

    def _sdk_family(self) -> TargetFamily:
        return TargetFamily.BOTO

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



    def _resolve_endpoint_url(self,
        flavor: str,
        region: t.Optional[str],
        endpoint_url: t.Optional[str],
        account_id: t.Optional[str],
    ) -> t.Optional[str]:
        """Return the boto3 endpoint_url for the given flavor.

        - ``aws``: None (let boto3 use its default resolver).
        - ``express``: None (SDK auto-detects from bucket name).
        - ``r2``: ``https://{ACCOUNT_ID}.r2.cloudflarestorage.com`` if
        ACCOUNT_ID set, else explicit ENDPOINT_URL, else ValueError.
        - ``minio``: explicit ENDPOINT_URL required.
        - ``b2``: ``https://s3.{REGION}.backblazeb2.com`` default.
        """
        if endpoint_url:
            return endpoint_url
        if flavor == "r2":
            if account_id:
                return f"https://{account_id}.r2.cloudflarestorage.com"
            raise ValueError(
                "R2 flavor requires either ENDPOINT_URL or ACCOUNT_ID."
            )
        if flavor == "minio":
            raise ValueError(
                "MinIO flavor requires an explicit ENDPOINT_URL."
            )
        if flavor == "b2":
            region = region or "us-east-005"
            return f"https://s3.{region}.backblazeb2.com"
        # aws / express — let boto3 default resolver handle it.
        return None


    def _resolve_addressing_style(self, flavor: str, configured: str) -> str:
        """S3 Express requires virtual addressing; others honour configuration."""
        if flavor == "express":
            return "virtual"
        return configured


    def to_handler_kwargs(self) -> dict[str, t.Any]:
        """Deprecated shim — kept for downstream callers (Phase 4 D2a).

        Delegates to the unified ``emit()`` pipeline. Internal callers should
        use ``emit(TargetFamily.BOTO)`` directly. Slated for removal in a later major.
        """
        return self.emit(self._sdk_family())
