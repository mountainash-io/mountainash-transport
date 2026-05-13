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

from __future__ import annotations

import warnings

from .azure_settings import AZURE_STORAGE_SPEC, AzureStorageSettings
from .ftp_settings import FTP_SPEC, FTPSettings
from .gcs_settings import GCS_SPEC, GCSSettings
from .github_settings import GITHUB_REPO_SPEC, GitHubRepoSettings
from .http_settings import HTTP_SPEC, HTTPSettings
from .local_settings import LOCAL_SPEC, LocalSettings
from .s3_settings import S3_SPEC, S3Settings
from .smb_settings import SMB_SPEC, SMBSettings
from .ssh_settings import SSH_SPEC, SSHSettings


__all__ = [
    "AZURE_STORAGE_SPEC",
    "AzureStorageSettings",
    "FTP_SPEC",
    "FTPSettings",
    "GCS_SPEC",
    "GCSSettings",
    "GITHUB_REPO_SPEC",
    "GitHubRepoSettings",
    "HTTP_SPEC",
    "HTTPSettings",
    "LOCAL_SPEC",
    "LocalSettings",
    "S3_SPEC",
    "S3Settings",
    "SMB_SPEC",
    "SMBSettings",
    "SSH_SPEC",
    "SSHSettings",
]


_DEPRECATED = {
    "AZURE_STORAGE_DESCRIPTOR": ("AZURE_STORAGE_SPEC", AZURE_STORAGE_SPEC),
    "FTP_DESCRIPTOR": ("FTP_SPEC", FTP_SPEC),
    "GCS_DESCRIPTOR": ("GCS_SPEC", GCS_SPEC),
    "GITHUB_REPO_DESCRIPTOR": ("GITHUB_REPO_SPEC", GITHUB_REPO_SPEC),
    "HTTP_DESCRIPTOR": ("HTTP_SPEC", HTTP_SPEC),
    "LOCAL_DESCRIPTOR": ("LOCAL_SPEC", LOCAL_SPEC),
    "S3_DESCRIPTOR": ("S3_SPEC", S3_SPEC),
    "SMB_DESCRIPTOR": ("SMB_SPEC", SMB_SPEC),
    "SSH_DESCRIPTOR": ("SSH_SPEC", SSH_SPEC),
}


def __getattr__(name: str):
    if name in _DEPRECATED:
        new_name, obj = _DEPRECATED[name]
        warnings.warn(
            f"{name!r} is renamed to {new_name!r}. "
            f"Update imports before mountainash-utils-files 26.6.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
