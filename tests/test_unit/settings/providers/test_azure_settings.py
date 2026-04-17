"""Tests for AzureStorageSettings — unified Azure Blob + Files settings."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mountainash_settings.auth import AzureADAuth, NoAuth, PasswordAuth, TokenAuth
from pydantic import SecretStr

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.settings.providers.azure_settings import (
    AZURE_STORAGE_DESCRIPTOR,
    AzureStorageSettings,
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
    return AzureStorageSettings(**kwargs)


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
class TestAzureAuthResolution:
    def test_noauth_credential_is_none(self):
        s = _make("blob", auth=NoAuth())
        kw = s.to_handler_kwargs()
        assert kw["credential"] is None

    def test_token_auth_builds_sas_credential(self):
        sas = pytest.importorskip("azure.core.credentials")
        s = _make("blob", auth=TokenAuth(token=SecretStr("?sv=2020-02-10&sig=abc")))
        kw = s.to_handler_kwargs()
        assert isinstance(kw["credential"], sas.AzureSasCredential)

    def test_password_auth_builds_named_key_credential(self):
        az = pytest.importorskip("azure.core.credentials")
        s = _make(
            "blob",
            auth=PasswordAuth(
                username="teststg", password=SecretStr("sh4redK3y=")
            ),
        )
        kw = s.to_handler_kwargs()
        cred = kw["credential"]
        assert isinstance(cred, az.AzureNamedKeyCredential)
        # Named key uses plain strings — not SecretStr
        # .named_key is a namedtuple (name, key) on real credentials.
        name, key = cred.named_key
        assert name == "teststg"
        assert key == "sh4redK3y="

    def test_azure_ad_auth_builds_client_secret_credential(self):
        az_identity = pytest.importorskip("azure.identity")
        s = _make(
            "blob",
            auth=AzureADAuth(
                tenant_id="my-tenant",
                client_id="my-client",
                client_secret=SecretStr("supersecret"),
                managed_identity=False,
            ),
        )
        kw = s.to_handler_kwargs()
        assert isinstance(
            kw["credential"], az_identity.ClientSecretCredential
        )

    def test_azure_ad_auth_managed_identity_branch(self):
        az_identity = pytest.importorskip("azure.identity")
        s = _make(
            "blob",
            auth=AzureADAuth(
                managed_identity=True,
                client_id="managed-id",
            ),
        )
        kw = s.to_handler_kwargs()
        assert isinstance(
            kw["credential"], az_identity.ManagedIdentityCredential
        )


@pytest.mark.unit
class TestAzureFilesTokenIntent:
    """Azure Files + AAD requires token_intent."""

    def test_files_with_ad_auto_sets_backup_intent(self):
        pytest.importorskip("azure.identity")
        s = _make(
            "files",
            auth=AzureADAuth(
                tenant_id="t", client_id="c",
                client_secret=SecretStr("s"), managed_identity=False,
            ),
        )
        kw = s.to_handler_kwargs()
        assert kw.get("token_intent") == "backup"

    def test_files_without_aad_no_token_intent(self):
        s = _make("files", auth=NoAuth())
        kw = s.to_handler_kwargs()
        assert "token_intent" not in kw

    def test_blob_never_sets_token_intent_by_default(self):
        pytest.importorskip("azure.identity")
        s = _make(
            "blob",
            auth=AzureADAuth(
                tenant_id="t", client_id="c",
                client_secret=SecretStr("s"), managed_identity=False,
            ),
        )
        kw = s.to_handler_kwargs()
        assert "token_intent" not in kw


@pytest.mark.unit
class TestAzureDescriptor:
    def test_descriptor_name(self):
        assert AZURE_STORAGE_DESCRIPTOR.name == "azure_storage"

    def test_descriptor_sdk_package(self):
        assert AZURE_STORAGE_DESCRIPTOR.sdk_package == "azure-storage-blob"

    def test_descriptor_not_read_only(self):
        assert AZURE_STORAGE_DESCRIPTOR.read_only is False
