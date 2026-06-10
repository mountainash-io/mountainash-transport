"""Storage provider settings classes.

All 15 legacy provider classes are consolidated into eight descriptor-driven
settings classes, plus HTTP/HTTPS:

* S3 / S3Express / R2 / MinIO / Backblaze B2 → :class:`S3Settings`
  (discriminated by ``FLAVOR``)
* Azure Blob + Azure Files → :class:`AzureStorageSettings`
  (discriminated by ``SERVICE_TYPE``)
* GCS → :class:`GCSSettings`
* SFTP → :class:`SFTPStorageProfile` (paramiko SFTP subsystem)
* FTP / FTPS → :class:`FTPSettings` (discriminated by ``USE_TLS``)
* SMB / CIFS → :class:`SMBSettings`
* Local + NFS + CIFS mounts → :class:`LocalSettings` (NFS / CIFS drive
  a pre-mount step via ``MOUNT_SPEC``)
* GitHub repository read → :class:`GitHubRepoSettings` (scope-cut)
* HTTP / HTTPS → :class:`HTTPSettings` (httpx-backed)
"""

from __future__ import annotations

from .azure_storage_profile import AZURE_STORAGE_SPEC, AzureStorageProfile, validate_service_type
from .ftp_storage_profile import FTP_SPEC, FTPStorageProfile
from .gcs_storage_profile import GCS_SPEC, GCSStorageProfile
from .github_storage_profile import GITHUB_REPO_SPEC, GitHubRepoStorageProfile
from .http_storage_profile import HTTP_SPEC, HTTPStorageProfile
from .local_storage_profile import LOCAL_SPEC, LocalStorageProfile
from .s3_storage_profile import S3_SPEC, S3StorageProfile, validate_flavor
from .sftp_storage_profile import SFTP_SPEC, SFTPStorageProfile
from .smb_storage_profile import SMB_SPEC, SMBStorageProfile




__all__ = [
    "AZURE_STORAGE_SPEC",
    "AzureStorageProfile",
    "FTP_SPEC",
    "FTPStorageProfile",
    "GCS_SPEC",
    "GCSStorageProfile",
    "GITHUB_REPO_SPEC",
    "GitHubRepoStorageProfile",
    "HTTP_SPEC",
    "HTTPStorageProfile",
    "LOCAL_SPEC",
    "LocalStorageProfile",
    "S3_SPEC",
    "S3StorageProfile",
    "SFTP_SPEC",
    "SFTPStorageProfile",
    "SMB_SPEC",
    "SMBStorageProfile",
    "validate_flavor",
    "validate_service_type"
]
