"""Storage provider settings classes.

Three legacy class-hierarchies have been consolidated into unified,
descriptor-driven settings:

* S3 / S3Express / R2 / MinIO / Backblaze B2 → :class:`S3Settings`
  (discriminated by ``FLAVOR``)
* Azure Blob + Azure Files → :class:`AzureStorageSettings`
  (discriminated by ``SERVICE_TYPE``)
* GCS → :class:`GCSSettings`

The old names remain available as pure aliases so existing downstream
imports and ``isinstance`` checks continue to work. Callers targeting
the Azure aliases MUST set ``SERVICE_TYPE="blob"`` or ``"files"``
explicitly — the aliases do not preset the discriminator.
"""

from .azure_settings import AZURE_STORAGE_DESCRIPTOR, AzureStorageSettings
from .ftp_settings import FTP_DESCRIPTOR, FTPSettings
from .gcs_settings import GCS_DESCRIPTOR, GCSSettings
from .s3_settings import S3_DESCRIPTOR, S3Settings
from .smb_settings import SMB_DESCRIPTOR, SMBSettings
from .ssh_settings import SSH_DESCRIPTOR, SSHSettings

# --- Backwards-compatible aliases for the migrated GCS + Azure providers.
# Pure aliases (not subclasses) so existing downstream imports and
# ``isinstance`` checks against the old names continue to work.
GCSStorageAuthSettings = GCSSettings
AzureBlobStorageAuthSettings = AzureStorageSettings
AzureFilesStorageAuthSettings = AzureStorageSettings

# --- Backwards-compatible aliases for the consolidated S3-family ----------
# Pure aliases (not subclasses) so isinstance() checks still pass against
# any of the five names.
S3StorageAuthSettings = S3Settings
R2StorageAuthSettings = S3Settings
S3ExpressStorageAuthSettings = S3Settings
MinIOStorageAuthSettings = S3Settings
BackblazeB2StorageAuthSettings = S3Settings

# --- Backwards-compatible aliases for the unified SSH / SFTP provider -----
# SFTP has no kwarg differences vs SSH (both wrap
# ``paramiko.SSHClient.connect``); the SFTP distinction is opening the
# SFTP subsystem after connecting. Alias both legacy names to SSHSettings.
SSHStorageAuthSettings = SSHSettings
SFTPStorageAuthSettings = SSHSettings

# --- Backwards-compatible alias for the migrated FTP provider -------------
FTPStorageAuthSettings = FTPSettings

# --- Backwards-compatible alias for the migrated SMB provider -------------
SMBStorageAuthSettings = SMBSettings

# Remaining legacy (pre-migration) provider classes — migrated
# incrementally in Phase 4.
from .nfs import NFSStorageAuthSettings
from .github import GitHubStorageAuthSettings
from .local import LocalStorageAuthSettings


__all__ = [
    # Unified Azure provider (aliases preserve legacy Blob/Files names).
    "AzureStorageSettings",
    "AZURE_STORAGE_DESCRIPTOR",
    "AzureBlobStorageAuthSettings",
    "AzureFilesStorageAuthSettings",
    # Migrated GCS provider (alias preserves legacy name).
    "GCSSettings",
    "GCS_DESCRIPTOR",
    "GCSStorageAuthSettings",
    # Consolidated S3-family.
    "S3Settings",
    "S3_DESCRIPTOR",
    "S3StorageAuthSettings",
    "R2StorageAuthSettings",
    "S3ExpressStorageAuthSettings",
    "MinIOStorageAuthSettings",
    "BackblazeB2StorageAuthSettings",
    # Unified SSH / SFTP provider (aliases preserve legacy names).
    "SSHSettings",
    "SSH_DESCRIPTOR",
    "SSHStorageAuthSettings",
    "SFTPStorageAuthSettings",
    # Migrated FTP provider (alias preserves legacy name).
    "FTPSettings",
    "FTP_DESCRIPTOR",
    "FTPStorageAuthSettings",
    # Migrated SMB provider (alias preserves legacy name).
    "SMBSettings",
    "SMB_DESCRIPTOR",
    "SMBStorageAuthSettings",
    # Other providers (migration pending).
    "NFSStorageAuthSettings",
    "GitHubStorageAuthSettings",
    "LocalStorageAuthSettings",
]
