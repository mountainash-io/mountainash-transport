"""
Settings Factory for auto-detecting and creating appropriate storage settings classes.

Provides utilities to auto-detect storage provider from URLs/paths
and create the corresponding settings class.
"""

import logging
import re
from typing import Dict, Type
from urllib.parse import urlparse

from mountainash_settings import MountainAshBaseSettings

from ..constants import CONST_STORAGE_PROVIDER_TYPE

logger = logging.getLogger(__name__)


class SettingsFactory:
    """
    Factory for auto-detecting and loading appropriate storage settings classes.

    Provides intelligent provider detection from storage URLs and paths.
    """

    # Mapping of URL schemes to storage provider types
    SCHEME_MAP: Dict[str, CONST_STORAGE_PROVIDER_TYPE] = {
        "file": CONST_STORAGE_PROVIDER_TYPE.LOCAL,
        "s3": CONST_STORAGE_PROVIDER_TYPE.S3,
        "s3a": CONST_STORAGE_PROVIDER_TYPE.S3,
        "s3n": CONST_STORAGE_PROVIDER_TYPE.S3,
        "s3express": CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS,
        "gs": CONST_STORAGE_PROVIDER_TYPE.GCS,
        "gcs": CONST_STORAGE_PROVIDER_TYPE.GCS,
        "az": CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
        "azure": CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
        "azblob": CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
        "azfiles": CONST_STORAGE_PROVIDER_TYPE.AZURE_FILES,
        "sftp": CONST_STORAGE_PROVIDER_TYPE.SFTP,
        "ftp": CONST_STORAGE_PROVIDER_TYPE.FTP,
        "ssh": CONST_STORAGE_PROVIDER_TYPE.SSH,
        "smb": CONST_STORAGE_PROVIDER_TYPE.SMB,
        "nfs": CONST_STORAGE_PROVIDER_TYPE.NFS,
        "minio": CONST_STORAGE_PROVIDER_TYPE.MINIO,
        "b2": CONST_STORAGE_PROVIDER_TYPE.B2,
        "r2": CONST_STORAGE_PROVIDER_TYPE.R2,
        "github": CONST_STORAGE_PROVIDER_TYPE.GITHUB,
    }

    # Mapping of provider types to settings classes (lazy loaded)
    SETTINGS_CLASS_MAP: Dict[CONST_STORAGE_PROVIDER_TYPE, Type[MountainAshBaseSettings]] = {}

    @classmethod
    def _ensure_settings_classes_loaded(cls) -> None:
        """
        Lazy load settings class mappings.

        This avoids circular imports and reduces initial load time.
        """
        if cls.SETTINGS_CLASS_MAP:
            return  # Already loaded

        # Lazy import settings classes only when needed
        from ..settings.providers import (
            LocalStorageAuthSettings,
            S3StorageAuthSettings,
            S3ExpressStorageAuthSettings,
            R2StorageAuthSettings,
            GCSStorageAuthSettings,
            AzureBlobStorageAuthSettings,
            AzureFilesStorageAuthSettings,
            SFTPStorageAuthSettings,
            FTPStorageAuthSettings,
            SSHStorageAuthSettings,
            MinIOStorageAuthSettings,
            SMBStorageAuthSettings,
            NFSStorageAuthSettings,
            B2StorageAuthSettings,
            GitHubStorageAuthSettings,
        )

        cls.SETTINGS_CLASS_MAP = {
            CONST_STORAGE_PROVIDER_TYPE.LOCAL: LocalStorageAuthSettings,
            CONST_STORAGE_PROVIDER_TYPE.S3: S3StorageAuthSettings,
            CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS: S3ExpressStorageAuthSettings,
            CONST_STORAGE_PROVIDER_TYPE.R2: R2StorageAuthSettings,
            CONST_STORAGE_PROVIDER_TYPE.GCS: GCSStorageAuthSettings,
            CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB: AzureBlobStorageAuthSettings,
            CONST_STORAGE_PROVIDER_TYPE.AZURE_FILES: AzureFilesStorageAuthSettings,
            CONST_STORAGE_PROVIDER_TYPE.SFTP: SFTPStorageAuthSettings,
            CONST_STORAGE_PROVIDER_TYPE.FTP: FTPStorageAuthSettings,
            CONST_STORAGE_PROVIDER_TYPE.SSH: SSHStorageAuthSettings,
            CONST_STORAGE_PROVIDER_TYPE.MINIO: MinIOStorageAuthSettings,
            CONST_STORAGE_PROVIDER_TYPE.SMB: SMBStorageAuthSettings,
            CONST_STORAGE_PROVIDER_TYPE.NFS: NFSStorageAuthSettings,
            CONST_STORAGE_PROVIDER_TYPE.B2: B2StorageAuthSettings,
            CONST_STORAGE_PROVIDER_TYPE.GITHUB: GitHubStorageAuthSettings,
        }

        logger.debug("Settings class mappings loaded")

    @classmethod
    def from_provider_type(
        cls, provider_type: CONST_STORAGE_PROVIDER_TYPE, **kwargs
    ) -> MountainAshBaseSettings:
        """
        Create settings instance from provider type.

        Args:
            provider_type: Storage provider type enum
            **kwargs: Arguments passed to settings constructor

        Returns:
            Settings instance for the provider

        Raises:
            KeyError: If provider type not supported
        """
        cls._ensure_settings_classes_loaded()

        if provider_type not in cls.SETTINGS_CLASS_MAP:
            raise KeyError(
                f"No settings class for {provider_type}. "
                f"Available: {list(cls.SETTINGS_CLASS_MAP.keys())}"
            )

        settings_class = cls.SETTINGS_CLASS_MAP[provider_type]
        return settings_class(**kwargs)

    @classmethod
    def from_storage_url(
        cls, storage_url: str, **kwargs
    ) -> MountainAshBaseSettings:
        """
        Auto-detect provider from storage URL and create settings.

        Args:
            storage_url: Storage URL (s3://bucket/path, gs://bucket, etc.)
            **kwargs: Arguments passed to settings constructor

        Returns:
            Settings instance for detected provider

        Raises:
            ValueError: If provider cannot be detected from URL

        Example:
            settings = SettingsFactory.from_storage_url(
                "s3://my-bucket/path/to/file",
                config_files=["s3.env"]
            )
        """
        provider_type = cls.detect_provider_from_url(storage_url)
        return cls.from_provider_type(provider_type, **kwargs)

    @classmethod
    def detect_provider_from_url(cls, storage_url: str) -> CONST_STORAGE_PROVIDER_TYPE:
        """
        Detect storage provider from URL.

        Args:
            storage_url: Storage URL or path

        Returns:
            Detected provider type

        Raises:
            ValueError: If provider cannot be detected

        Example:
            provider = SettingsFactory.detect_provider_from_url("s3://bucket/path")
            # Returns: CONST_STORAGE_PROVIDER_TYPE.S3
        """
        # Handle absolute local paths
        if storage_url.startswith("/") or (len(storage_url) > 1 and storage_url[1] == ":"):
            return CONST_STORAGE_PROVIDER_TYPE.LOCAL

        # Parse URL scheme
        parsed = urlparse(storage_url)
        scheme = parsed.scheme.lower() if parsed.scheme else ""

        # Handle URLs without scheme (assume local)
        if not scheme:
            return CONST_STORAGE_PROVIDER_TYPE.LOCAL

        # Check exact scheme match
        if scheme in cls.SCHEME_MAP:
            return cls.SCHEME_MAP[scheme]

        # Pattern matching for complex URLs
        for pattern, provider_type in cls.SCHEME_MAP.items():
            if re.match(pattern, scheme):
                logger.debug(
                    f"Pattern matched: {scheme} → {provider_type} (pattern: {pattern})"
                )
                return provider_type

        raise ValueError(
            f"Cannot detect provider from URL scheme: {scheme}. "
            f"URL: {storage_url}. "
            f"Supported schemes: {list(cls.SCHEME_MAP.keys())}"
        )
