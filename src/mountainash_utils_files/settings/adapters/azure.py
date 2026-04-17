"""azure-storage adapter — builds BlobServiceClient / ShareServiceClient kwargs.

Produces a dict suitable for passing to either
``azure.storage.blob.BlobServiceClient`` or
``azure.storage.fileshare.ShareServiceClient``, depending on the
profile's ``SERVICE_TYPE`` discriminator.

The returned dict also carries two extra keys the (future) handler can
inspect to pick the right SDK client class:

- ``service_type``        – ``"blob"`` or ``"files"``
- ``service_class_path``  – dotted path to the concrete SDK class

All ``azure.*`` imports are lazy to avoid a hard dependency on the
Azure SDKs for pure-settings usage.
"""

from __future__ import annotations

import typing as t

if t.TYPE_CHECKING:
    from ..profile import StorageProfile


__all__ = ["build_handler_kwargs"]


_SERVICE_CLASS_PATHS: dict[str, str] = {
    "blob": "azure.storage.blob.BlobServiceClient",
    "files": "azure.storage.fileshare.ShareServiceClient",
}

# Azure public endpoints use the *singular* host token for both services
# (``<account>.blob.core.windows.net`` and ``<account>.file.core.windows.net``).
# The SERVICE_TYPE discriminator is plural ("blob" | "files") for clarity
# at the API layer, so map it to the hostname token here.
_SERVICE_URL_TOKEN: dict[str, str] = {
    "blob": "blob",
    "files": "file",
}


def _unwrap_secret(v: t.Any) -> t.Optional[str]:
    if v is None:
        return None
    if hasattr(v, "get_secret_value"):
        return v.get_secret_value()
    return str(v)


def _resolve_account_url(
    account_url: t.Optional[str],
    account_name: t.Optional[str],
    service_type: str,
    endpoint_suffix: str,
) -> t.Optional[str]:
    if account_url:
        return str(account_url)
    if account_name:
        host_token = _SERVICE_URL_TOKEN.get(service_type, service_type)
        return f"https://{account_name}.{host_token}.{endpoint_suffix}"
    return None


def _resolve_credential(auth: t.Any, account_name: t.Optional[str]) -> t.Any:
    """Resolve an Azure credential object from the discriminated auth union.

    - ``AzureADAuth`` (managed_identity=True) → ``ManagedIdentityCredential``
    - ``AzureADAuth`` + tenant/client/secret  → ``ClientSecretCredential``
    - ``AzureADAuth`` otherwise               → ``DefaultAzureCredential``
    - ``TokenAuth``                           → ``AzureSasCredential``
    - ``PasswordAuth``                        → ``AzureNamedKeyCredential``
      (``name = username or ACCOUNT_NAME``; ``key = password``)
    - ``NoAuth`` / missing                    → ``None``
    """
    if auth is None:
        return None
    auth_type = type(auth).__name__

    if auth_type == "NoAuth":
        return None

    if auth_type == "AzureADAuth":
        from azure.identity import (  # type: ignore[import-untyped]
            ClientSecretCredential,
            DefaultAzureCredential,
            ManagedIdentityCredential,
        )

        tenant_id = getattr(auth, "tenant_id", None)
        client_id = getattr(auth, "client_id", None)
        client_secret = getattr(auth, "client_secret", None)
        managed_identity = getattr(auth, "managed_identity", False)

        if managed_identity:
            return ManagedIdentityCredential(
                client_id=client_id if client_id else None
            )
        if tenant_id and client_id and client_secret:
            return ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=_unwrap_secret(client_secret) or "",
            )
        return DefaultAzureCredential()

    if auth_type == "TokenAuth":
        token = _unwrap_secret(getattr(auth, "token", None))
        if not token:
            return None
        from azure.core.credentials import (  # type: ignore[import-untyped]
            AzureSasCredential,
        )

        return AzureSasCredential(signature=token)

    if auth_type == "PasswordAuth":
        username = getattr(auth, "username", None) or account_name
        password = _unwrap_secret(getattr(auth, "password", None))
        if not username or not password:
            return None
        from azure.core.credentials import (  # type: ignore[import-untyped]
            AzureNamedKeyCredential,
        )

        return AzureNamedKeyCredential(name=username, key=password)

    # Unknown auth type — let the caller fall back to ambient credentials.
    return None


def build_handler_kwargs(profile: "StorageProfile") -> dict[str, t.Any]:
    """Build ``BlobServiceClient`` / ``ShareServiceClient`` kwargs from profile.

    Signature widened to ``StorageProfile`` to satisfy the upstream
    ``__adapter__: Callable[[DescriptorProfile], dict[str, Any]]``
    contract; callers always pass an :class:`AzureStorageSettings`
    instance in practice.

    Returns a dict with SDK kwargs plus ``service_type`` and
    ``service_class_path`` metadata the handler uses to dispatch to the
    correct concrete client class.
    """
    service_type = getattr(profile, "SERVICE_TYPE", "blob") or "blob"
    account_name = getattr(profile, "ACCOUNT_NAME", None)
    account_url = getattr(profile, "ACCOUNT_URL", None)
    endpoint_suffix = (
        getattr(profile, "ENDPOINT_SUFFIX", None) or "core.windows.net"
    )
    token_intent = getattr(profile, "TOKEN_INTENT", None)
    api_version = getattr(profile, "API_VERSION", None)
    secondary_hostname = getattr(profile, "SECONDARY_HOSTNAME", None)
    max_block_size = getattr(profile, "MAX_BLOCK_SIZE", None)

    resolved_url = _resolve_account_url(
        account_url=account_url,
        account_name=account_name,
        service_type=service_type,
        endpoint_suffix=endpoint_suffix,
    )

    auth = getattr(profile, "auth", None)
    credential = _resolve_credential(auth, account_name)

    kwargs: dict[str, t.Any] = {
        "account_url": resolved_url,
        "credential": credential,
        # Metadata the handler uses to pick the concrete SDK client class.
        "service_type": service_type,
        "service_class_path": _SERVICE_CLASS_PATHS.get(service_type),
    }

    # Files + AAD requires token_intent="backup" (SDK raises otherwise).
    if service_type == "files":
        auth_type = type(auth).__name__ if auth is not None else "NoAuth"
        if token_intent:
            kwargs["token_intent"] = token_intent
        elif auth_type == "AzureADAuth":
            kwargs["token_intent"] = "backup"

    if api_version:
        kwargs["api_version"] = api_version
    if secondary_hostname:
        kwargs["secondary_hostname"] = secondary_hostname
    if max_block_size is not None and service_type == "blob":
        kwargs["max_block_size"] = max_block_size

    return kwargs
