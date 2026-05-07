"""boto3 S3 adapter — flavor-dispatched kwargs builder.

Builds a dict of kwargs ready for ``boto3.client("s3", **kwargs)``.
Dispatches per-flavor endpoint URL, addressing-style, and session-auth
toggles.

If the profile declares a ``ROLE_ARN``, returns a nested
``{"base_kwargs": ..., "role_arn": ..., "session_name": ...}`` dict
signalling the handler to call STS ``assume_role`` first — mirrors the
mountainash-utils-secrets Phase 3 pattern.
"""

from __future__ import annotations

import typing as t

if t.TYPE_CHECKING:
    from ..profile import StorageProfile


__all__ = ["build_handler_kwargs"]


def _unwrap_secret(v: t.Any) -> t.Optional[str]:
    if v is None:
        return None
    if hasattr(v, "get_secret_value"):
        return v.get_secret_value()
    return str(v)


def _resolve_endpoint_url(
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


def _resolve_addressing_style(flavor: str, configured: str) -> str:
    """S3 Express requires virtual addressing; others honour configuration."""
    if flavor == "express":
        return "virtual"
    return configured


def build_handler_kwargs(profile: "StorageProfile") -> dict[str, t.Any]:
    """Build boto3 S3 client kwargs from an :class:`S3Settings` profile.

    Signature widened to ``StorageProfile`` to satisfy the upstream
    ``__adapter__: Callable[[DescriptorProfile], dict[str, Any]]`` contract;
    callers always pass an :class:`S3Settings` instance in practice.

    Returns either a flat dict ready for ``boto3.client("s3", **kwargs)`` or
    a nested ``{"base_kwargs": ..., "role_arn": ..., "session_name": ...}``
    dict when ``ROLE_ARN`` is set.
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
    addressing_style = _resolve_addressing_style(
        flavor, getattr(profile, "ADDRESSING_STYLE", "auto")
    )
    accelerate = bool(getattr(profile, "ACCELERATE_ENDPOINT", False))
    dualstack = bool(getattr(profile, "DUALSTACK_ENDPOINT", False))
    verify_ssl = getattr(profile, "VERIFY_SSL", True)
    role_arn = getattr(profile, "ROLE_ARN", None)

    # R2 always uses region_name="auto"; others honour REGION.
    effective_region = "auto" if flavor == "r2" else region

    base: dict[str, t.Any] = {
        "service_name": "s3",
        "region_name": effective_region,
        "use_ssl": use_ssl,
        "verify": verify_ssl,
    }

    resolved_endpoint = _resolve_endpoint_url(
        flavor, region, endpoint_url, account_id
    )
    if resolved_endpoint is not None:
        base["endpoint_url"] = resolved_endpoint

    # Credentials from IAMAuth / TokenAuth fields.
    auth = getattr(profile, "auth", None)
    if auth is not None:
        auth_type = type(auth).__name__
        if auth_type == "IAMAuth":
            if getattr(auth, "access_key_id", None):
                base["aws_access_key_id"] = auth.access_key_id
            if getattr(auth, "secret_access_key", None):
                base["aws_secret_access_key"] = _unwrap_secret(
                    auth.secret_access_key
                )
            if getattr(auth, "session_token", None):
                base["aws_session_token"] = _unwrap_secret(auth.session_token)
        elif auth_type == "TokenAuth":
            if getattr(auth, "token", None):
                base["aws_session_token"] = _unwrap_secret(auth.token)

    if _botocore_config is not None:
        s3_config: dict[str, t.Any] = {"addressing_style": addressing_style}
        # Accelerate / dualstack only apply to standard AWS S3.
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

    if role_arn:
        return {
            "base_kwargs": base,
            "role_arn": role_arn,
            "session_name": "mountainash-utils-files",
        }

    return base
