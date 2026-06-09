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

from mountainash_auth_client import CONST_AUTH_MODE
from mountainash_auth_client import AuthProfile, IAMAuth, TokenAuth

from ...profile_spec import ParameterSpec, StorageProfileSpec
from mountainash_settings.profiles import Profile

from ..registry import register
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from ...utils.secrets import _unwrap_secret

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
# def _adapter(profile: "S3StorageProfile", auth=None) -> dict[str, t.Any]:
#     from ..adapters.s3 import build_handler_kwargs

#     return build_handler_kwargs(profile, auth)


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


    def _auth_kwargs(self,
        auth_profile: AuthProfile | None
    ) -> dict[str, t.Any]:
        """Translate the discriminated auth union into s3 kwargs.
        """
        if auth_profile is None:
            return {}

        if isinstance(auth_profile, IAMAuth):
            out: dict[str, t.Any] = {"auth_protocol": "iam"}


            if auth_profile.ACCESS_KEY_ID:
                out["aws_access_key_id"] = auth_profile.ACCESS_KEY_ID
            if auth_profile.SECRET_ACCESS_KEY:
                out["aws_secret_access_key"] = _unwrap_secret(auth_profile.SECRET_ACCESS_KEY)
            if auth_profile.SESSION_TOKEN:
                out["aws_session_token"] = _unwrap_secret(auth_profile.SESSION_TOKEN)

            return out

        elif isinstance(auth_profile, TokenAuth):
            out: dict[str, t.Any] = {"auth_protocol": "token"}
            if auth_profile.TOKEN:
                out["aws_session_token"] = _unwrap_secret(auth_profile.TOKEN)

            return out
        # Unknown auth type — surface no credentials, let the handler decide.
        return {}


    def to_handler_kwargs(self, auth_profile: AuthProfile | None = None) -> dict[str, t.Any]:
        """Build boto3 S3 client kwargs from an :class:`S3Settings` profile.

        Signature widened to ``StorageProfile`` to satisfy the upstream
        ``__adapter__: Callable[[Profile], dict[str, Any]]`` contract;
        callers always pass an :class:`S3Settings` instance in practice.

        Returns either a flat dict ready for ``boto3.client("s3", **kwargs)`` or
        a nested ``{"base_kwargs": ..., "role_arn": ..., "session_name": ...}``
        dict when ``ROLE_ARN`` is set.
        """
        try:
            import botocore.config as _botocore_config
        except ImportError:  # pragma: no cover - botocore is a boto3 transitive
            _botocore_config = None  # type: ignore[assignment]

        flavor = getattr(self, "FLAVOR", "aws")
        region = getattr(self, "REGION", None)
        endpoint_url = getattr(self, "ENDPOINT_URL", None)
        account_id = getattr(self, "ACCOUNT_ID", None)
        use_ssl = getattr(self, "USE_SSL", True)
        addressing_style = self._resolve_addressing_style(
            flavor, getattr(self, "ADDRESSING_STYLE", "auto")
        )
        accelerate = bool(getattr(self, "ACCELERATE_ENDPOINT", False))
        dualstack = bool(getattr(self, "DUALSTACK_ENDPOINT", False))
        verify_ssl = getattr(self, "VERIFY_SSL", True)
        role_arn = getattr(self, "ROLE_ARN", None)

        # R2 always uses region_name="auto"; others honour REGION.
        effective_region = "auto" if flavor == "r2" else region

        base: dict[str, t.Any] = {
            "service_name": "s3",
            "region_name": effective_region,
            "use_ssl": use_ssl,
            "verify": verify_ssl,
        }

        resolved_endpoint = self._resolve_endpoint_url(
            flavor, region, endpoint_url, account_id
        )
        if resolved_endpoint is not None:
            base["endpoint_url"] = resolved_endpoint


        auth_kwargs = self._auth_kwargs(auth_profile)
        base.update(auth_kwargs)

        # # Credentials from IAMAuth / TokenAuth fields.
        # if isinstance(auth, IAMAuth):
        #     if auth.ACCESS_KEY_ID:
        #         base["aws_access_key_id"] = auth.ACCESS_KEY_ID
        #     if auth.SECRET_ACCESS_KEY:
        #         base["aws_secret_access_key"] = _unwrap_secret(auth.SECRET_ACCESS_KEY)
        #     if auth.SESSION_TOKEN:
        #         base["aws_session_token"] = _unwrap_secret(auth.SESSION_TOKEN)
        # elif isinstance(auth, TokenAuth):
        #     if auth.TOKEN:
        #         base["aws_session_token"] = _unwrap_secret(auth.TOKEN)

        if _botocore_config is not None:
            s3_config: dict[str, t.Any] = {"addressing_style": addressing_style}
            # Accelerate / dualstack only apply to standard AWS S3.
            if flavor == "aws":
                if accelerate:
                    s3_config["use_accelerate_endpoint"] = True
                if dualstack:
                    s3_config["use_dualstack_endpoint"] = True
            config_kwargs: dict[str, t.Any] = {"s3": s3_config}
            connect_timeout = getattr(self, "CONNECT_TIMEOUT", None)
            read_timeout = getattr(self, "READ_TIMEOUT", None)
            if connect_timeout is not None:
                config_kwargs["connect_timeout"] = connect_timeout
            if read_timeout is not None:
                config_kwargs["read_timeout"] = read_timeout
            base["config"] = _botocore_config.Config(**config_kwargs)

        if role_arn:
            return {
                "base_kwargs": base,
                "role_arn": role_arn,
                "session_name": "mountainash-transport",
            }

        return base
