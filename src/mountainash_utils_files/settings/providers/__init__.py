from .azure_blob import AzureBlobStorageAuthSettings
from .azure_files import AzureFilesStorageAuthSettings
from .gcs import GCSStorageAuthSettings
from .s3 import S3StorageAuthSettings

from .ftp import FTPStorageAuthSettings
from .nfs import NFSStorageAuthSettings
from .sftp import SFTPStorageAuthSettings
from .smb import SMBStorageAuthSettings
from .ssh import SSHStorageAuthSettings

from .minio import MinIOStorageAuthSettings
from .b2 import BackblazeB2StorageAuthSettings

from .github import GitHubStorageAuthSettings
from .local import LocalStorageAuthSettings
from .r2 import R2StorageAuthSettings

__all__ = [
    "AzureBlobStorageAuthSettings",
    "AzureFilesStorageAuthSettings",
    "GCSStorageAuthSettings",
    "S3StorageAuthSettings",
    "SFTPStorageAuthSettings",
    "FTPStorageAuthSettings",
    "NFSStorageAuthSettings",
    "SMBStorageAuthSettings",

    "SSHStorageAuthSettings",

    "MinIOStorageAuthSettings",
    "BackblazeB2StorageAuthSettings",
    "GitHubStorageAuthSettings",
    "LocalStorageAuthSettings",
    "R2StorageAuthSettings"
    ]
