"""Tests for AzureStorageProfile — unified Azure Blob + Files settings."""

from __future__ import annotations

import pytest

from mountainash_auth_client import NoAuth

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.settings.storage.profiles import (
    AZURE_STORAGE_SPEC,
    AzureStorageProfile,
    validate_service_type,
)


_PROVIDER_TYPE_BY_SERVICE: dict[str, str] = {
    "blob": CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
    "files": CONST_STORAGE_PROVIDER_TYPE.AZURE_FILES,
}


def _make(service_type: str = "blob", *, auth=None, **extra):
    kwargs = {
        "PROVIDER_TYPE": _PROVIDER_TYPE_BY_SERVICE[service_type],
        "SERVICE_TYPE": service_type,
        "ACCOUNT_NAME": "teststg",
        "auth": auth if auth is not None else NoAuth(),
    }
    kwargs.update(extra)
    return AzureStorageProfile(**kwargs)


@pytest.mark.unit
class TestServiceTypeValidator:
    @pytest.mark.parametrize("value", ["blob", "files"])
    def test_valid_service_type_accepted(self, value):
        assert validate_service_type(value) == value

    @pytest.mark.parametrize(
        "bad", ["BLOB", "file", "queue", "table", ""]
    )
    def test_invalid_service_type_rejected(self, bad):
        with pytest.raises(ValueError):
            validate_service_type(bad)


@pytest.mark.unit
class TestAzureAccountUrlAutoBuild:
    """ACCOUNT_URL is auto-derived from SERVICE_TYPE when unset.

    Critical detail: the hostname token is singular (``blob`` / ``file``)
    even though SERVICE_TYPE is plural (``blob`` / ``files``).
    """

    def test_blob_url_uses_blob_token(self):
        s = _make("blob")
        kw = s.to_handler_kwargs()
        assert kw["account_url"] == "https://teststg.blob.core.windows.net"

    def test_files_url_uses_file_singular_token(self):
        s = _make("files")
        kw = s.to_handler_kwargs()
        # Note: "file" — singular — not "files"
        assert kw["account_url"] == "https://teststg.file.core.windows.net"

    def test_explicit_account_url_wins(self):
        s = _make("blob", ACCOUNT_URL="https://override.example/custom")
        kw = s.to_handler_kwargs()
        assert kw["account_url"] == "https://override.example/custom"

    def test_sovereign_cloud_endpoint_suffix(self):
        s = _make("blob", ENDPOINT_SUFFIX="core.chinacloudapi.cn")
        kw = s.to_handler_kwargs()
        assert kw["account_url"] == "https://teststg.blob.core.chinacloudapi.cn"


@pytest.mark.unit
class TestAzureServiceClassDispatch:
    def test_blob_dispatches_to_blob_service_client(self):
        s = _make("blob")
        kw = s.to_handler_kwargs()
        assert kw["service_type"] == "blob"
        assert kw["service_class_path"] == "azure.storage.blob.BlobServiceClient"

    def test_files_dispatches_to_share_service_client(self):
        s = _make("files")
        kw = s.to_handler_kwargs()
        assert kw["service_type"] == "files"
        assert (
            kw["service_class_path"]
            == "azure.storage.fileshare.ShareServiceClient"
        )


@pytest.mark.unit
class TestAzureHandlerKwargs:
    """to_handler_kwargs returns SDK-level config only (no auth)."""

    def test_no_credential_key_in_kwargs(self):
        """Credential resolution is handled by the auth strategy layer."""
        s = _make("blob")
        kw = s.to_handler_kwargs()
        assert "credential" not in kw

    def test_token_intent_forwarded_when_explicit(self):
        s = _make("files", TOKEN_INTENT="backup")
        kw = s.to_handler_kwargs()
        assert kw["token_intent"] == "backup"

    def test_no_token_intent_without_explicit_setting(self):
        """Auto-injection of token_intent for AAD is handled by the strategy layer."""
        s = _make("files")
        kw = s.to_handler_kwargs()
        assert "token_intent" not in kw


@pytest.mark.unit
class TestAzureDescriptor:
    def test_descriptor_name(self):
        assert AZURE_STORAGE_SPEC.name == "azure_storage"

    def test_descriptor_sdk_package(self):
        assert AZURE_STORAGE_SPEC.sdk_package == "azure-storage-blob"

    def test_descriptor_not_read_only(self):
        assert AZURE_STORAGE_SPEC.read_only is False
