"""Azure Storage settings (unified Blob + Files).

Collapses the legacy ``AzureBlobStorageAuthSettings`` and
``AzureFilesStorageAuthSettings`` classes into a single
:class:`AzureStorageSettings` class discriminated by a ``SERVICE_TYPE``
field (``"blob"`` or ``"files"``). Both services share the same
authentication surface (shared-key, SAS, AAD, connection string) and
differ only in the hostname suffix (``.blob.`` vs ``.file.``) and a
handful of Files-specific flags.

Mirrors the Phase 3 ``AzureKeyVaultSettings`` pattern and the Phase 4
``S3Settings`` pattern: the class is a two-line shell; all parameters
live on the descriptor; the adapter
(:func:`mountainash_utils_files.settings.adapters.azure.build_handler_kwargs`)
produces kwargs for ``BlobServiceClient`` or ``ShareServiceClient``.
"""

from __future__ import annotations

import re
import typing as t

from mountainash_settings.auth import (
    AzureADAuth,
    NoAuth,
    PasswordAuth,
    TokenAuth,
)

from ..base import StorageAuthBase
from ..descriptor import MISSING, ParameterSpec, StorageDescriptor
from ..profile import StorageProfile
from ..registry import register
from ...constants import CONST_STORAGE_PROVIDER_TYPE

__all__ = [
    "AZURE_STORAGE_SPEC",
    "AzureStorageSettings",
    "validate_service_type",
]


_VALID_SERVICE_TYPES: frozenset[str] = frozenset({"blob", "files"})
_ACCOUNT_NAME_RE = re.compile(r"^[a-z0-9]{3,24}$")
_CONTAINER_OR_SHARE_RE = re.compile(r"^[a-z0-9](?!.*--)[a-z0-9-]{1,61}[a-z0-9]$")

# Azure public endpoints use the *singular* host token for both services
# (``<account>.blob.core.windows.net`` and ``<account>.file.core.windows.net``).
# The SERVICE_TYPE discriminator is plural ("blob" | "files") at the API
# layer for clarity; map it to the hostname token here.
_SERVICE_URL_TOKEN: dict[str, str] = {"blob": "blob", "files": "file"}


def validate_service_type(v: str) -> str:
    """Validate the Azure ``SERVICE_TYPE`` discriminator."""
    if v not in _VALID_SERVICE_TYPES:
        raise ValueError(
            f"Invalid Azure service type: {v!r}. Must be one of "
            f"{sorted(_VALID_SERVICE_TYPES)}."
        )
    return v


def _validate_account_name(v: str) -> str:
    if not v:
        raise ValueError("ACCOUNT_NAME is required for Azure Storage")
    if not _ACCOUNT_NAME_RE.match(v):
        raise ValueError(
            "ACCOUNT_NAME must be 3-24 chars, lowercase alphanumeric only"
        )
    return v


def _validate_container_or_share(v: t.Optional[str]) -> t.Optional[str]:
    if v is None:
        return None
    if not (3 <= len(v) <= 63):
        raise ValueError("CONTAINER_OR_SHARE must be 3-63 characters")
    if not _CONTAINER_OR_SHARE_RE.match(v):
        raise ValueError(
            "Invalid CONTAINER_OR_SHARE format: lowercase letters, numbers, "
            "and single hyphens only"
        )
    return v


AZURE_STORAGE_SPEC = StorageDescriptor(
    name="azure_storage",
    # Canonical provider_type is AZURE_BLOB; the AZURE_FILES type is
    # handled by the same settings class with SERVICE_TYPE='files'.
    provider_type=CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
    sdk_package="azure-storage-blob",
    handler_module="mountainash_utils_files.storage_backends.azure",
    handler_class="AzureStorageBackend",
    supports_streaming=True,
    supports_multipart=True,
    read_only=False,
    parameters=[
        ParameterSpec(
            name="SERVICE_TYPE",
            type=str,
            tier="core",
            default="blob",
            validator=validate_service_type,
            description=(
                "Azure Storage sub-service: 'blob' (object) or 'files' "
                "(SMB share). Dispatches endpoint hostname and SDK class."
            ),
        ),
        ParameterSpec(
            name="ACCOUNT_NAME",
            type=str,
            tier="core",
            default=MISSING,
            validator=_validate_account_name,
            description="Azure Storage account name (3-24 chars, lowercase alphanumeric).",
        ),
        ParameterSpec(
            name="CONTAINER_OR_SHARE",
            type=str,
            tier="core",
            default=None,
            validator=_validate_container_or_share,
            description=(
                "Default container (blob) or file share (files). Single field "
                "replaces the per-service CONTAINER_NAME / SHARE_NAME on the "
                "legacy settings classes."
            ),
        ),
        ParameterSpec(
            name="ACCOUNT_URL",
            type=str,
            tier="core",
            default=None,
            driver_key="account_url",
            description=(
                "Full service URL. Auto-derived by the adapter from "
                "ACCOUNT_NAME + SERVICE_TYPE + ENDPOINT_SUFFIX when unset "
                "(the hostname token is 'blob' or 'file' — singular — even "
                "though SERVICE_TYPE is 'files' plural, so we skip the "
                "declarative template and derive the URL in the adapter)."
            ),
        ),
        ParameterSpec(
            name="ENDPOINT_SUFFIX",
            type=str,
            tier="advanced",
            default="core.windows.net",
            description=(
                "DNS suffix for the Azure environment. Override for sovereign "
                "clouds (e.g. 'core.chinacloudapi.cn')."
            ),
        ),
        ParameterSpec(
            name="TOKEN_INTENT",
            type=str,
            tier="advanced",
            default=None,
            description=(
                "Required for Azure Files + AAD: typically 'backup'. Ignored "
                "for Blob."
            ),
        ),
        ParameterSpec(
            name="API_VERSION",
            type=str,
            tier="advanced",
            default=None,
            description="Pin the Azure Storage REST API version.",
        ),
        ParameterSpec(
            name="SECONDARY_HOSTNAME",
            type=str,
            tier="advanced",
            default=None,
            description="RA-GRS secondary-region hostname for read-only failover.",
        ),
        ParameterSpec(
            name="MAX_BLOCK_SIZE",
            type=int,
            tier="advanced",
            default=None,
            description="Override max block/upload size in bytes (blob only).",
        ),
    ],
    auth_modes=[AzureADAuth, TokenAuth, PasswordAuth, NoAuth],
    metadata={
        "service_class_paths": {
            "blob": "azure.storage.blob.BlobServiceClient",
            "files": "azure.storage.fileshare.ShareServiceClient",
        },
    },
)


# Adapter is imported lazily to avoid a circular import with the
# adapters package which depends on StorageProfile.
def _adapter(profile: "AzureStorageSettings") -> dict[str, t.Any]:
    from ..adapters.azure import build_handler_kwargs

    return build_handler_kwargs(profile)


@register
class AzureStorageSettings(StorageProfile, StorageAuthBase):
    """Unified Azure Storage settings for both Blob and Files services.

    Fields are installed from :data:`AZURE_STORAGE_SPEC` by the
    :class:`~mountainash_settings.profiles.Profile` metaclass.
    The ``SERVICE_TYPE`` field discriminates per-service endpoint suffix
    and the concrete SDK client class the handler should instantiate
    (:class:`azure.storage.blob.BlobServiceClient` vs
    :class:`azure.storage.fileshare.ShareServiceClient`).

    Auth maps onto Azure credentials as follows:
        - :class:`AzureADAuth`  → ``ClientSecretCredential`` or
          ``ManagedIdentityCredential`` (based on ``managed_identity``)
        - :class:`TokenAuth`    → ``AzureSasCredential`` (SAS token)
        - :class:`PasswordAuth` → ``AzureNamedKeyCredential`` (account
          name + shared key; username=ACCOUNT_NAME, password=account_key)
        - :class:`NoAuth`       → ``credential=None``
    """

    __spec__ = AZURE_STORAGE_SPEC
    __adapter__ = staticmethod(_adapter)

    def get_connection_url(self) -> str:
        """Return a best-effort connection URL for logging/inspection."""
        account_url = getattr(self, "ACCOUNT_URL", None)
        if account_url:
            base = str(account_url)
        else:
            account = getattr(self, "ACCOUNT_NAME", "") or ""
            service = getattr(self, "SERVICE_TYPE", "blob") or "blob"
            suffix = getattr(self, "ENDPOINT_SUFFIX", "core.windows.net") or "core.windows.net"
            host_token = _SERVICE_URL_TOKEN.get(service, service)
            base = f"https://{account}.{host_token}.{suffix}"
        container_or_share = getattr(self, "CONTAINER_OR_SHARE", None)
        if container_or_share:
            return f"{base}/{container_or_share}"
        return base
