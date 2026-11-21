"""Storage provider profiles: one class per provider family.

* S3 / S3 Express / R2 / MinIO / Backblaze B2 → :class:`S3StorageProfile`
  (``FLAVOR`` selects the flavor)
* Azure Blob + Azure Files → :class:`AzureStorageProfile` (``SERVICE_TYPE``)
* GCS → :class:`GCSStorageProfile`
* SFTP → :class:`SFTPStorageProfile` (paramiko SFTP subsystem)
* FTP / FTPS → :class:`FTPStorageProfile` (``USE_TLS``)
* SMB / CIFS → :class:`SMBStorageProfile`
* Local filesystem → :class:`LocalStorageProfile` (``ROOT_PATH`` confines the facade)
* GitHub repository read → :class:`GitHubRepoStorageProfile`
* HTTP / HTTPS → :class:`HTTPStorageProfile` (httpx)
"""

from __future__ import annotations

try:
    from .azure_storage_profile import AZURE_STORAGE_SPEC, AzureStorageProfile, validate_service_type
    from .ftp_storage_profile import FTP_SPEC, FTPStorageProfile
    from .gcs_storage_profile import GCS_SPEC, GCSStorageProfile
    from .github_storage_profile import GITHUB_REPO_SPEC, GitHubRepoStorageProfile
    from .http_storage_profile import HTTP_SPEC, HTTPStorageProfile
    from .local_storage_profile import LOCAL_SPEC, LocalStorageProfile
    from .s3_storage_profile import S3_SPEC, S3StorageProfile, validate_flavor
    from .sftp_storage_profile import SFTP_SPEC, SFTPStorageProfile
    from .smb_storage_profile import SMB_SPEC, SMBStorageProfile
except ImportError as _exc:
    from mountainash_transport._core.extras import raise_for_missing_extra
    raise_for_missing_extra("storage profiles", "http", _exc)




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
