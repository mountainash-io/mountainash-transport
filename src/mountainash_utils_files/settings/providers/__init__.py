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
from .gcs_settings import GCS_DESCRIPTOR, GCSSettings
from .s3_settings import S3_DESCRIPTOR, S3Settings

# --- Backwards-compatible aliases for the migrated GCS + Azure providers.
# Pure aliases (not subclasses) so existing downstream imports and
# ``isinstance`` checks against the old names continue to work.
GCSStorageAuthSettings = GCSSettings
AzureBlobStorageAuthSettings = AzureStorageSettings
AzureFilesStorageAuthSettings = AzureStorageSettings

from .ftp import FTPStorageAuthSettings
from .nfs import NFSStorageAuthSettings
from .sftp import SFTPStorageAuthSettings
from .smb import SMBStorageAuthSettings
from .ssh import SSHStorageAuthSettings

from .github import GitHubStorageAuthSettings
from .local import LocalStorageAuthSettings


# --- Backwards-compatible aliases for the consolidated S3-family ----------
# Pure aliases (not subclasses) so isinstance() checks still pass against
# any of the five names.
S3StorageAuthSettings = S3Settings
R2StorageAuthSettings = S3Settings
S3ExpressStorageAuthSettings = S3Settings
MinIOStorageAuthSettings = S3Settings
BackblazeB2StorageAuthSettings = S3Settings


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
    # Other providers (migration pending).
    "SFTPStorageAuthSettings",
    "FTPStorageAuthSettings",
    "NFSStorageAuthSettings",
    "SMBStorageAuthSettings",
    "SSHStorageAuthSettings",
    "GitHubStorageAuthSettings",
    "LocalStorageAuthSettings",
]
