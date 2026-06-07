"""Shared helpers for mountainash-utils-files settings tests."""

from __future__ import annotations

import typing as t

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE


# Canonical PROVIDER_TYPE per settings class name.
PROVIDER_TYPE_BY_CLASS: dict[str, str] = {
    "S3Settings": CONST_STORAGE_PROVIDER_TYPE.S3,
    "GCSSettings": CONST_STORAGE_PROVIDER_TYPE.GCS,
    "AzureStorageSettings": CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
    "SSHSettings": CONST_STORAGE_PROVIDER_TYPE.SSH,
    "FTPSettings": CONST_STORAGE_PROVIDER_TYPE.FTP,
    "SMBSettings": CONST_STORAGE_PROVIDER_TYPE.SMB,
    "LocalSettings": CONST_STORAGE_PROVIDER_TYPE.LOCAL,
    "GitHubRepoSettings": CONST_STORAGE_PROVIDER_TYPE.GITHUB,
}


def provider_type_for(cls: type) -> str:
    """Return the canonical PROVIDER_TYPE string for a settings class."""
    return PROVIDER_TYPE_BY_CLASS[cls.__name__]


def construct(cls: type, **kwargs: t.Any) -> t.Any:
    """Instantiate a settings class, auto-filling ``PROVIDER_TYPE``."""
    kwargs.setdefault("PROVIDER_TYPE", provider_type_for(cls))
    return cls(**kwargs)
