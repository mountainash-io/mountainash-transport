"""Storage provider settings classes.

All 15 legacy provider classes are consolidated into eight descriptor-driven
settings classes, plus HTTP/HTTPS:

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
* HTTP / HTTPS → :class:`HTTPSettings` (httpx-backed)
"""

from .azure_settings import AZURE_STORAGE_DESCRIPTOR, AzureStorageSettings
from .ftp_settings import FTP_DESCRIPTOR, FTPSettings
from .gcs_settings import GCS_DESCRIPTOR, GCSSettings
from .github_settings import GITHUB_REPO_DESCRIPTOR, GitHubRepoSettings
from .http_settings import HTTP_DESCRIPTOR, HTTPSettings
from .local_settings import LOCAL_DESCRIPTOR, LocalSettings
from .s3_settings import S3_DESCRIPTOR, S3Settings
from .smb_settings import SMB_DESCRIPTOR, SMBSettings
from .ssh_settings import SSH_DESCRIPTOR, SSHSettings


__all__ = [
    "AZURE_STORAGE_DESCRIPTOR",
    "AzureStorageSettings",
    "FTP_DESCRIPTOR",
    "FTPSettings",
    "GCS_DESCRIPTOR",
    "GCSSettings",
    "GITHUB_REPO_DESCRIPTOR",
    "GitHubRepoSettings",
    "HTTP_DESCRIPTOR",
    "HTTPSettings",
    "LOCAL_DESCRIPTOR",
    "LocalSettings",
    "S3_DESCRIPTOR",
    "S3Settings",
    "SMB_DESCRIPTOR",
    "SMBSettings",
    "SSH_DESCRIPTOR",
    "SSHSettings",
]
