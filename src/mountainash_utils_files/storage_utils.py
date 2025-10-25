"""
High-level storage utilities for settings-driven file operations.

Provides a unified API for creating file helpers and performing storage operations
with automatic provider detection and lazy loading.
"""

import logging
from typing import Optional

from mountainash_settings import SettingsParameters, MountainAshBaseSettings

from .file_helpers.base_file_helper import Base_FileHelper
from .constants import CONST_STORAGE_PROVIDER_TYPE
from .factories import FileHelperFactory, SettingsFactory

logger = logging.getLogger(__name__)


class StorageUtils:
    """
    High-level API for settings-driven storage operations.

    All operations driven by SettingsParameters, with automatic provider
    detection and lazy loading of provider-specific implementations.

    Example:
        # Create settings parameters
        settings_params = SettingsParameters.create(
            settings_class=S3StorageAuthSettings,
            config_files=["s3.env"]
        )

        # Auto-detect and create file helper
        helper = StorageUtils.create_file_helper(settings_params)
        files = helper.list_files("s3://bucket/path/")
    """

    @classmethod
    def create_file_helper(
        cls, settings_parameters: SettingsParameters
    ) -> Base_FileHelper:
        """
        Create file helper from settings parameters.

        Auto-detects storage provider from settings_class and returns appropriate helper.

        Args:
            settings_parameters: SettingsParameters with settings_class

        Returns:
            File helper instance ready to use

        Example:
            settings_params = SettingsParameters.create(
                settings_class=S3StorageAuthSettings,
                config_files=["s3.env"]
            )
            helper = StorageUtils.create_file_helper(settings_params)
            exists = helper.path_exists("s3://bucket/file.txt")
        """
        factory = FileHelperFactory()
        return factory.get_file_helper(settings_parameters)

    @classmethod
    def create_settings_from_url(
        cls, storage_url: str, **kwargs
    ) -> MountainAshBaseSettings:
        """
        Auto-detect provider from URL and create appropriate settings.

        Args:
            storage_url: Storage URL (s3://bucket, gs://bucket, /local/path, etc.)
            **kwargs: Arguments passed to settings constructor

        Returns:
            Settings instance for detected provider

        Example:
            settings = StorageUtils.create_settings_from_url(
                "s3://my-bucket/path/",
                config_files=["s3.env"]
            )
        """
        return SettingsFactory.from_storage_url(storage_url, **kwargs)

    @classmethod
    def create_settings_from_provider(
        cls, provider_type: CONST_STORAGE_PROVIDER_TYPE, **kwargs
    ) -> MountainAshBaseSettings:
        """
        Create settings for specific storage provider.

        Args:
            provider_type: Storage provider type enum
            **kwargs: Arguments passed to settings constructor

        Returns:
            Settings instance for the provider

        Example:
            settings = StorageUtils.create_settings_from_provider(
                CONST_STORAGE_PROVIDER_TYPE.S3,
                config_files=["s3.env"]
            )
        """
        return SettingsFactory.from_provider_type(provider_type, **kwargs)

    @classmethod
    def detect_provider_from_url(cls, storage_url: str) -> CONST_STORAGE_PROVIDER_TYPE:
        """
        Detect storage provider from URL.

        Args:
            storage_url: Storage URL or path

        Returns:
            Detected provider type

        Example:
            provider = StorageUtils.detect_provider_from_url("s3://bucket/path")
            # Returns: CONST_STORAGE_PROVIDER_TYPE.S3
        """
        return SettingsFactory.detect_provider_from_url(storage_url)

    @classmethod
    def create_from_url(
        cls,
        storage_url: str,
        config_files: Optional[list] = None,
        **settings_kwargs,
    ) -> tuple[Base_FileHelper, MountainAshBaseSettings]:
        """
        Complete workflow: URL → settings → file helper.

        Convenience method for quick setup from storage URL.

        Args:
            storage_url: Storage URL (s3://bucket, gs://bucket, etc.)
            config_files: Optional configuration files
            **settings_kwargs: Additional settings constructor arguments

        Returns:
            Tuple of (file_helper, settings)

        Example:
            helper, settings = StorageUtils.create_from_url(
                "s3://my-bucket/path/",
                config_files=["s3.env"]
            )
            files = helper.list_files("s3://my-bucket/path/")
        """
        # Create settings from URL
        settings = cls.create_settings_from_url(
            storage_url, config_files=config_files, **settings_kwargs
        )

        # Create settings parameters
        settings_params = settings.extract_settings_parameters()

        # Create file helper
        helper = cls.create_file_helper(settings_params)

        return helper, settings

    @classmethod
    def path_exists(
        cls,
        path: str,
        settings_parameters: Optional[SettingsParameters] = None,
        storage_url: Optional[str] = None,
        **settings_kwargs,
    ) -> bool:
        """
        Check if path exists using auto-detected storage provider.

        Args:
            path: Path to check
            settings_parameters: Optional settings parameters
            storage_url: Optional URL to auto-detect provider
            **settings_kwargs: Settings constructor arguments

        Returns:
            True if path exists, False otherwise

        Example:
            # Using settings parameters
            exists = StorageUtils.path_exists(
                "s3://bucket/file.txt",
                settings_parameters=settings_params
            )

            # Or auto-detect from URL
            exists = StorageUtils.path_exists(
                "s3://bucket/file.txt",
                storage_url="s3://bucket",
                config_files=["s3.env"]
            )
        """
        if settings_parameters is None:
            if storage_url is None:
                storage_url = path
            helper, _ = cls.create_from_url(storage_url, **settings_kwargs)
        else:
            helper = cls.create_file_helper(settings_parameters)

        return helper.path_exists(path)

    @classmethod
    def list_files(
        cls,
        path: str,
        settings_parameters: Optional[SettingsParameters] = None,
        storage_url: Optional[str] = None,
        **settings_kwargs,
    ) -> list:
        """
        List files at path using auto-detected storage provider.

        Args:
            path: Path to list
            settings_parameters: Optional settings parameters
            storage_url: Optional URL to auto-detect provider
            **settings_kwargs: Settings constructor arguments

        Returns:
            List of file paths

        Example:
            files = StorageUtils.list_files(
                "s3://bucket/path/",
                storage_url="s3://bucket",
                config_files=["s3.env"]
            )
        """
        if settings_parameters is None:
            if storage_url is None:
                storage_url = path
            helper, _ = cls.create_from_url(storage_url, **settings_kwargs)
        else:
            helper = cls.create_file_helper(settings_parameters)

        return helper.list_files(path)
