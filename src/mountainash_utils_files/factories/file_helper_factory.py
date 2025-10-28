"""
File Helper Factory for settings-driven storage backend creation.

Uses SettingsParameters to auto-detect storage provider and create appropriate file helper.
"""

import logging
from typing import Type

from mountainash_settings import SettingsParameters

from ..file_helpers.base_file_helper import Base_FileHelper
from ..constants import CONST_STORAGE_PROVIDER_TYPE
from .base_strategy_factory import BaseStrategyFactory
from .settings_type_factory_mixin import SettingsTypeFactoryMixin

logger = logging.getLogger(__name__)


class FileHelperFactory(
    SettingsTypeFactoryMixin,
    BaseStrategyFactory[SettingsParameters, Type[Base_FileHelper]],
):
    """
    Settings-driven factory for file helpers.

    Detects storage provider from SettingsParameters.settings_class and returns
    appropriate file helper class with lazy loading.

    Example:
        settings_params = SettingsParameters.create(
            settings_class=S3StorageAuthSettings,
            config_files=["s3.env"]
        )

        factory = FileHelperFactory()
        helper_class = factory.get_strategy(settings_params)
        helper = helper_class(settings_parameters=settings_params)
    """

    @classmethod
    def _configure_strategy_mapping(cls) -> None:
        """
        Configure strategy mappings using ONLY strings (no imports).

        Maps storage provider types to file helper module paths and class names.
        """
        cls._strategy_modules = {
            CONST_STORAGE_PROVIDER_TYPE.LOCAL: "mountainash_utils_files.file_helpers",
            CONST_STORAGE_PROVIDER_TYPE.S3: "mountainash_utils_files.file_helpers",
            CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS: "mountainash_utils_files.file_helpers",
            CONST_STORAGE_PROVIDER_TYPE.R2: "mountainash_utils_files.file_helpers",
            CONST_STORAGE_PROVIDER_TYPE.GCS: "mountainash_utils_files.file_helpers",
            CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB: "mountainash_utils_files.file_helpers",
            CONST_STORAGE_PROVIDER_TYPE.AZURE_FILES: "mountainash_utils_files.file_helpers",
            CONST_STORAGE_PROVIDER_TYPE.SFTP: "mountainash_utils_files.file_helpers",
            CONST_STORAGE_PROVIDER_TYPE.FTP: "mountainash_utils_files.file_helpers",
            CONST_STORAGE_PROVIDER_TYPE.SSH: "mountainash_utils_files.file_helpers",
            CONST_STORAGE_PROVIDER_TYPE.MINIO: "mountainash_utils_files.file_helpers",
            CONST_STORAGE_PROVIDER_TYPE.SMB: "mountainash_utils_files.file_helpers",
            CONST_STORAGE_PROVIDER_TYPE.NFS: "mountainash_utils_files.file_helpers",
            CONST_STORAGE_PROVIDER_TYPE.B2: "mountainash_utils_files.file_helpers",
            CONST_STORAGE_PROVIDER_TYPE.GITHUB: "mountainash_utils_files.file_helpers",
        }

        cls._strategy_classes = {
            CONST_STORAGE_PROVIDER_TYPE.LOCAL: "Local_FileHelper",
            CONST_STORAGE_PROVIDER_TYPE.S3: "S3_FileHelper",
            CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS: "S3Express_FileHelper",
            CONST_STORAGE_PROVIDER_TYPE.R2: "R2_FileHelper",
            CONST_STORAGE_PROVIDER_TYPE.GCS: "GCS_FileHelper",
            CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB: "Azure_FileHelper",
            CONST_STORAGE_PROVIDER_TYPE.AZURE_FILES: "AzureFiles_FileHelper",
            CONST_STORAGE_PROVIDER_TYPE.SFTP: "SFTP_FileHelper",
            CONST_STORAGE_PROVIDER_TYPE.FTP: "FTP_FileHelper",
            CONST_STORAGE_PROVIDER_TYPE.SSH: "SSH_FileHelper",
            CONST_STORAGE_PROVIDER_TYPE.MINIO: "S3_MinIO_FileHelper",
            CONST_STORAGE_PROVIDER_TYPE.SMB: "SMB_FileHelper",
            CONST_STORAGE_PROVIDER_TYPE.NFS: "NFS_FileHelper",
            CONST_STORAGE_PROVIDER_TYPE.B2: "B2_FileHelper",
            CONST_STORAGE_PROVIDER_TYPE.GITHUB: "GitHub_FileHelper",
        }

    @classmethod
    def get_file_helper(
        cls, settings_parameters: SettingsParameters
    ) -> Base_FileHelper:
        """
        Convenience method to get file helper instance directly.

        Args:
            settings_parameters: SettingsParameters with settings_class

        Returns:
            File helper instance ready to use

        Example:
            factory = FileHelperFactory()
            helper = factory.get_file_helper(settings_params)
            files = helper.list_files("/path/to/dir")
        """
        helper_class = cls.get_strategy(settings_parameters)
        # File helpers instantiate with settings_parameters
        return helper_class(settings_parameters=settings_parameters)


# Legacy compatibility function
def get_file_helper_factory(
    settings_parameters: SettingsParameters,
) -> Base_FileHelper:
    """
    Legacy compatibility function for existing code.

    Args:
        settings_parameters: SettingsParameters with settings_class

    Returns:
        File helper instance

    Note:
        This function exists for backward compatibility.
        New code should use FileHelperFactory directly.
    """
    factory = FileHelperFactory()
    return factory.get_file_helper(settings_parameters)
