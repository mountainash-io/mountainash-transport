"""Storage provider settings classes.

The five S3-compatible flavors (S3, S3Express, R2, MinIO, Backblaze B2)
were consolidated into the single :class:`S3Settings` class. The old names
remain available as pure aliases so existing downstream imports and
``isinstance`` checks continue to work without subclass relationships.
"""

from .azure_blob import AzureBlobStorageAuthSettings
from .azure_files import AzureFilesStorageAuthSettings
from .gcs import GCSStorageAuthSettings
from .s3_settings import S3_DESCRIPTOR, S3Settings

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
    "AzureBlobStorageAuthSettings",
    "AzureFilesStorageAuthSettings",
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
