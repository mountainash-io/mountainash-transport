"""Storage provider settings classes.

All 15 legacy provider classes have been consolidated into seven
descriptor-driven settings classes:

* S3 / S3Express / R2 / MinIO / Backblaze B2 → :class:`S3Settings`
  (discriminated by ``FLAVOR``)
* Azure Blob + Azure Files → :class:`AzureStorageSettings`
  (discriminated by ``SERVICE_TYPE``)
* GCS → :class:`GCSSettings`
* SSH + SFTP → :class:`SSHSettings` (no kwarg difference — SFTP is just
  the subsystem opened after connecting)
* FTP / FTPS → :class:`FTPSettings` (discriminated by ``USE_TLS``)
* SMB / CIFS → :class:`SMBSettings`
* Local + NFS + CIFS mounts → :class:`LocalSettings` (NFS / CIFS drive
  a pre-mount step via ``MOUNT_SPEC``)
* GitHub repository read → :class:`GitHubRepoSettings` (scope-cut)

The old names remain available as pure aliases so existing downstream
imports and ``isinstance`` checks continue to work. Callers targeting
the Azure aliases MUST set ``SERVICE_TYPE="blob"`` or ``"files"``
explicitly — the aliases do not preset the discriminator.
"""

from .azure_settings import AZURE_STORAGE_DESCRIPTOR, AzureStorageSettings
from .ftp_settings import FTP_DESCRIPTOR, FTPSettings
from .gcs_settings import GCS_DESCRIPTOR, GCSSettings
from .github_settings import GITHUB_REPO_DESCRIPTOR, GitHubRepoSettings
from .local_settings import LOCAL_DESCRIPTOR, LocalSettings
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

# --- Backwards-compatible aliases for the migrated Local provider ---------
# NFSStorageAuthSettings is now an alias for LocalSettings; legacy NFS
# users should pass ``MOUNT_SPEC={"mount_type": "nfs", ...}`` to drive
# the handler's pre-mount step. See :class:`LocalSettings` docstring.
LocalStorageAuthSettings = LocalSettings
NFSStorageAuthSettings = LocalSettings

# --- Backwards-compatible alias for the migrated GitHub provider ----------
# Scope-cut to repository read access only. Legacy fields (STORAGE_TYPE,
# PACKAGE_TYPE, PACKAGE_VISIBILITY, BRANCH, PATH, CREATE_PATH,
# API_VERSION) are no longer recognised; downstream callers passing
# them will see a pydantic ``Extra inputs are not permitted`` error
# and should migrate — BRANCH maps to REF, everything else is either
# per-operation or was only relevant to the retired non-repository
# storage modes.
GitHubStorageAuthSettings = GitHubRepoSettings


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
    # Local filesystem + NFS/CIFS fold-in (aliases preserve legacy names).
    "LocalSettings",
    "LOCAL_DESCRIPTOR",
    "LocalStorageAuthSettings",
    "NFSStorageAuthSettings",
    # GitHub repository (read-only, scope-cut).
    "GitHubRepoSettings",
    "GITHUB_REPO_DESCRIPTOR",
    "GitHubStorageAuthSettings",
]
