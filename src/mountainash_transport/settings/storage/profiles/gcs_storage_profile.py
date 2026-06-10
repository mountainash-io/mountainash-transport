"""Google Cloud Storage settings.

Descriptor-driven GCS settings class. Mirrors the Phase 3
``GCPSecretsSettings`` pattern and the Phase 4 ``S3Settings`` pattern:
the class is a two-line shell; all parameters live on
:data:`GCS_SPEC`; the adapter
(:func:`mountainash_transport.settings.adapters.gcs.build_handler_kwargs`)
produces kwargs for ``google.cloud.storage.Client``.
"""

from __future__ import annotations

import re
import typing as t

from mountainash_auth_client import CONST_AUTH_MODE

from ...profile_spec import MISSING, ParameterSpec, StorageProfileSpec
from mountainash_settings.profiles import Profile

from ..registry import register
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE

__all__ = ["GCS_SPEC", "GCSStorageProfile"]


_PROJECT_ID_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
_IP_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")


def _validate_project(v: str) -> str:
    """Validate GCP project ID."""
    if not v:
        raise ValueError("PROJECT is required for GCS")
    if not (6 <= len(v) <= 30):
        raise ValueError("PROJECT must be between 6 and 30 characters")
    if not _PROJECT_ID_RE.match(v):
        raise ValueError(
            "Invalid PROJECT format: must start with a lowercase letter and "
            "contain only lowercase letters, numbers, and hyphens"
        )
    return v


def _validate_bucket_name(v: t.Optional[str]) -> t.Optional[str]:
    """Validate GCS bucket name (optional)."""
    if v is None:
        return None
    if not (3 <= len(v) <= 63):
        raise ValueError("BUCKET_NAME must be between 3 and 63 characters")
    if not _BUCKET_NAME_RE.match(v):
        raise ValueError(
            "Invalid BUCKET_NAME format: must contain only lowercase letters, "
            "numbers, dots, hyphens, and underscores"
        )
    if ".." in v:
        raise ValueError("BUCKET_NAME cannot contain consecutive dots")
    if _IP_RE.match(v):
        raise ValueError("BUCKET_NAME cannot be formatted as an IP address")
    if v.startswith("goog"):
        raise ValueError("BUCKET_NAME cannot start with 'goog'")
    return v


GCS_SPEC = StorageProfileSpec(
    name="gcs",
    provider_type=CONST_STORAGE_PROVIDER_TYPE.GCS,
    sdk_package="google-cloud-storage",
    handler_module="mountainash_transport.storage.backends.gcs",
    handler_class="GCSStorageBackend",
    supports_streaming=True,
    supports_multipart=True,
    read_only=False,
    parameters=[
        ParameterSpec(
            name="PROJECT",
            type=str,
            tier="core",
            default=MISSING,
            validator=_validate_project,
            driver_key="project",
            description="GCP project ID (6-30 chars, lowercase).",
        ),
        ParameterSpec(
            name="BUCKET_NAME",
            type=str,
            tier="core",
            default=None,
            validator=_validate_bucket_name,
            description=(
                "Default GCS bucket. Optional client-level metadata; "
                "google-cloud-storage takes bucket per-operation."
            ),
        ),
        ParameterSpec(
            name="API_ENDPOINT",
            type=str,
            tier="advanced",
            default=None,
            description=(
                "Override the default GCS API endpoint. Passed through "
                "``client_options={'api_endpoint': ...}`` to the SDK."
            ),
        ),
        ParameterSpec(
            name="LOCATION",
            type=str,
            tier="advanced",
            default=None,
            description=(
                "GCS location / region hint (e.g. ``us-central1``, ``eu``). "
                "Used for bucket creation; client-level metadata only."
            ),
        ),
        ParameterSpec(
            name="USER_PROJECT",
            type=str,
            tier="advanced",
            default=None,
            description=(
                "Billing project for requester-pays buckets. Forwarded via "
                "``client_options={'quota_project_id': ...}``."
            ),
        ),
    ],
    default_auth=CONST_AUTH_MODE.SERVICE_ACCOUNT,
    supported_auth=frozenset({CONST_AUTH_MODE.SERVICE_ACCOUNT, CONST_AUTH_MODE.IAM, CONST_AUTH_MODE.OAUTH2, CONST_AUTH_MODE.TOKEN, CONST_AUTH_MODE.NONE}),
    implemented=False,
)


# Adapter is imported lazily to avoid a circular import with the adapters
# package which depends on StorageProfile.
# def _adapter(profile: "GCSStorageProfile", auth=None) -> dict[str, t.Any]:
#     from ..adapters.gcs import build_handler_kwargs

#     return build_handler_kwargs(profile, auth)


@register
class GCSStorageProfile(Profile):
    """Google Cloud Storage settings.

    Fields are installed from :data:`GCS_SPEC` by the
    :class:`~mountainash_settings.profiles.Profile` metaclass.
    Auth is resolved via the discriminated ``auth`` union (defaulting to
    ``ServiceAccountAuth`` for GCS); see
    :func:`~mountainash_transport.settings.adapters.gcs.build_handler_kwargs`.
    """

    __spec__ = GCS_SPEC

    def get_connection_url(self) -> str:
        """Return a best-effort connection URL for logging/inspection."""
        endpoint = getattr(self, "API_ENDPOINT", None)
        bucket = getattr(self, "BUCKET_NAME", None)
        base = f"https://{endpoint}" if endpoint else "https://storage.googleapis.com"
        if bucket:
            return f"{base}/{bucket}"
        return base


    def to_handler_kwargs(self) -> dict[str, t.Any]:
        """Build ``google.cloud.storage.Client`` kwargs from a :class:`GCSSettings` profile.

        Returns SDK-level config only (project, client options).
        Credential resolution is handled by the auth strategy layer.
        """
        project = getattr(self, "PROJECT", None)
        api_endpoint = getattr(self, "API_ENDPOINT", None)
        user_project = getattr(self, "USER_PROJECT", None)

        kwargs: dict[str, t.Any] = {
            "project": project,
        }

        client_options_kwargs: dict[str, t.Any] = {}
        if api_endpoint:
            client_options_kwargs["api_endpoint"] = api_endpoint
        if user_project:
            client_options_kwargs["quota_project_id"] = user_project

        if client_options_kwargs:
            try:
                from google.api_core.client_options import (  # type: ignore[import-untyped]
                    ClientOptions,
                )

                kwargs["client_options"] = ClientOptions(**client_options_kwargs)
            except ImportError:
                # google-api-core not installed — pass the raw dict; the
                # handler can lazily wrap it.
                kwargs["client_options"] = client_options_kwargs

        return kwargs
