"""Tests for the 15 legacy class aliases preserved in providers/__init__.py.

Each legacy name must:
  1. Still import from ``mountainash_utils_files.settings.providers``.
  2. Be the **same class object** (``is``) as its new consolidated settings
     class — pure aliases, not subclasses — so ``isinstance`` checks pass
     for every legacy name.
"""

from __future__ import annotations

import pytest

from mountainash_settings.auth import NoAuth
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.settings.providers import (
    AzureBlobStorageAuthSettings,
    AzureFilesStorageAuthSettings,
    AzureStorageSettings,
    BackblazeB2StorageAuthSettings,
    FTPSettings,
    FTPStorageAuthSettings,
    GCSSettings,
    GCSStorageAuthSettings,
    GitHubRepoSettings,
    GitHubStorageAuthSettings,
    LocalSettings,
    LocalStorageAuthSettings,
    MinIOStorageAuthSettings,
    NFSStorageAuthSettings,
    R2StorageAuthSettings,
    S3ExpressStorageAuthSettings,
    S3Settings,
    S3StorageAuthSettings,
    SFTPStorageAuthSettings,
    SMBSettings,
    SMBStorageAuthSettings,
    SSHSettings,
    SSHStorageAuthSettings,
)


# --- S3 family (5 aliases → S3Settings) ------------------------------------

S3_ALIASES = [
    ("S3StorageAuthSettings", S3StorageAuthSettings),
    ("R2StorageAuthSettings", R2StorageAuthSettings),
    ("S3ExpressStorageAuthSettings", S3ExpressStorageAuthSettings),
    ("MinIOStorageAuthSettings", MinIOStorageAuthSettings),
    ("BackblazeB2StorageAuthSettings", BackblazeB2StorageAuthSettings),
]

# --- GCS (1 alias → GCSSettings) -------------------------------------------

GCS_ALIASES = [
    ("GCSStorageAuthSettings", GCSStorageAuthSettings),
]

# --- Azure (2 aliases → AzureStorageSettings) ------------------------------

AZURE_ALIASES = [
    ("AzureBlobStorageAuthSettings", AzureBlobStorageAuthSettings),
    ("AzureFilesStorageAuthSettings", AzureFilesStorageAuthSettings),
]

# --- SSH / SFTP (2 aliases → SSHSettings) ---------------------------------

SSH_ALIASES = [
    ("SSHStorageAuthSettings", SSHStorageAuthSettings),
    ("SFTPStorageAuthSettings", SFTPStorageAuthSettings),
]

# --- FTP (1 alias → FTPSettings) -------------------------------------------

FTP_ALIASES = [
    ("FTPStorageAuthSettings", FTPStorageAuthSettings),
]

# --- SMB (1 alias → SMBSettings) -------------------------------------------

SMB_ALIASES = [
    ("SMBStorageAuthSettings", SMBStorageAuthSettings),
]

# --- Local / NFS (2 aliases → LocalSettings) -------------------------------

LOCAL_ALIASES = [
    ("LocalStorageAuthSettings", LocalStorageAuthSettings),
    ("NFSStorageAuthSettings", NFSStorageAuthSettings),
]

# --- GitHub (1 alias → GitHubRepoSettings) ---------------------------------

GITHUB_ALIASES = [
    ("GitHubStorageAuthSettings", GitHubStorageAuthSettings),
]


@pytest.mark.unit
class TestAliasIdentity:
    """Identity checks — each legacy name must be the same class object."""

    @pytest.mark.parametrize("name,alias", S3_ALIASES, ids=lambda x: x if isinstance(x, str) else None)
    def test_s3_aliases_are_s3settings(self, name, alias):
        assert alias is S3Settings, f"{name} must BE S3Settings (pure alias)"

    @pytest.mark.parametrize("name,alias", GCS_ALIASES, ids=lambda x: x if isinstance(x, str) else None)
    def test_gcs_aliases_are_gcssettings(self, name, alias):
        assert alias is GCSSettings, f"{name} must BE GCSSettings (pure alias)"

    @pytest.mark.parametrize("name,alias", AZURE_ALIASES, ids=lambda x: x if isinstance(x, str) else None)
    def test_azure_aliases_are_azurestoragesettings(self, name, alias):
        assert alias is AzureStorageSettings, (
            f"{name} must BE AzureStorageSettings (pure alias)"
        )

    @pytest.mark.parametrize("name,alias", SSH_ALIASES, ids=lambda x: x if isinstance(x, str) else None)
    def test_ssh_aliases_are_sshsettings(self, name, alias):
        assert alias is SSHSettings, f"{name} must BE SSHSettings (pure alias)"

    @pytest.mark.parametrize("name,alias", FTP_ALIASES, ids=lambda x: x if isinstance(x, str) else None)
    def test_ftp_aliases_are_ftpsettings(self, name, alias):
        assert alias is FTPSettings, f"{name} must BE FTPSettings (pure alias)"

    @pytest.mark.parametrize("name,alias", SMB_ALIASES, ids=lambda x: x if isinstance(x, str) else None)
    def test_smb_aliases_are_smbsettings(self, name, alias):
        assert alias is SMBSettings, f"{name} must BE SMBSettings (pure alias)"

    @pytest.mark.parametrize("name,alias", LOCAL_ALIASES, ids=lambda x: x if isinstance(x, str) else None)
    def test_local_aliases_are_localsettings(self, name, alias):
        assert alias is LocalSettings, (
            f"{name} must BE LocalSettings (pure alias)"
        )

    @pytest.mark.parametrize("name,alias", GITHUB_ALIASES, ids=lambda x: x if isinstance(x, str) else None)
    def test_github_aliases_are_githubreposettings(self, name, alias):
        assert alias is GitHubRepoSettings, (
            f"{name} must BE GitHubRepoSettings (pure alias)"
        )


@pytest.mark.unit
class TestAliasIsinstance:
    """isinstance round-trip — a new-API instance is-a every legacy name."""

    def test_s3_instance_isinstance_all_s3_aliases(self):
        inst = S3Settings(
            PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.S3,
            REGION="us-east-1",
            auth=NoAuth(),
        )
        for name, alias in S3_ALIASES:
            assert isinstance(inst, alias), (
                f"S3Settings instance must isinstance-match {name}"
            )

    def test_gcs_instance_isinstance_alias(self):
        inst = GCSSettings(
            PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.GCS,
            PROJECT="my-project",
            auth=NoAuth(),
        )
        assert isinstance(inst, GCSStorageAuthSettings)

    def test_azure_instance_isinstance_both_aliases(self):
        inst = AzureStorageSettings(
            PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
            SERVICE_TYPE="blob",
            ACCOUNT_NAME="acct01",
            auth=NoAuth(),
        )
        assert isinstance(inst, AzureBlobStorageAuthSettings)
        assert isinstance(inst, AzureFilesStorageAuthSettings)

    def test_ssh_instance_isinstance_both_aliases(self):
        from mountainash_settings.auth import PasswordAuth
        from pydantic import SecretStr

        inst = SSHSettings(
            PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.SSH,
            HOST="server.example",
            USERNAME="alice",
            auth=PasswordAuth(username="alice", password=SecretStr("pw")),
        )
        assert isinstance(inst, SSHStorageAuthSettings)
        assert isinstance(inst, SFTPStorageAuthSettings)

    def test_ftp_instance_isinstance_alias(self):
        inst = FTPSettings(
            PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.FTP,
            HOST="ftp.example",
            auth=NoAuth(),
        )
        assert isinstance(inst, FTPStorageAuthSettings)

    def test_smb_instance_isinstance_alias(self):
        from mountainash_settings.auth import PasswordAuth
        from pydantic import SecretStr

        inst = SMBSettings(
            PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.SMB,
            SERVER="file.example",
            USERNAME="alice",
            auth=PasswordAuth(username="alice", password=SecretStr("pw")),
        )
        assert isinstance(inst, SMBStorageAuthSettings)

    def test_local_instance_isinstance_both_aliases(self):
        inst = LocalSettings(
            PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.LOCAL,
            ROOT_PATH="/tmp",
            auth=NoAuth(),
        )
        assert isinstance(inst, LocalStorageAuthSettings)
        assert isinstance(inst, NFSStorageAuthSettings)

    def test_github_instance_isinstance_alias(self):
        from mountainash_settings.auth import TokenAuth
        from pydantic import SecretStr

        inst = GitHubRepoSettings(
            PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.GITHUB,
            ORG="mountainash-io",
            REPO="mountainash",
            auth=TokenAuth(token=SecretStr("ghp_x")),
        )
        assert isinstance(inst, GitHubStorageAuthSettings)


@pytest.mark.unit
def test_fifteen_legacy_names_present():
    """Sanity: exactly 15 distinct legacy aliases are exported."""
    all_aliases = (
        S3_ALIASES
        + GCS_ALIASES
        + AZURE_ALIASES
        + SSH_ALIASES
        + FTP_ALIASES
        + SMB_ALIASES
        + LOCAL_ALIASES
        + GITHUB_ALIASES
    )
    assert len(all_aliases) == 15
    names = {n for n, _ in all_aliases}
    assert len(names) == 15, "duplicate legacy names"
