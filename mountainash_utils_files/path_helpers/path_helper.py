from upath import UPath
from typing import Union, Any, Type, Optional
import platform

from mountainash_acdrs.constants import CONST_STORAGESYSTEM
from mountainash_acdrs.utils.path_utils import BasePathUtils, LocalPathUtils, S3PathUtils, GCSPathUtils, AZPathUtils, SFTPPathUtils, SSHPathUtils


class PathHelper:

    path_util_classes = {
        CONST_STORAGESYSTEM.LOCAL_DISK.value: LocalPathUtils,
        CONST_STORAGESYSTEM.S3.value:   S3PathUtils,
        CONST_STORAGESYSTEM.S3U.value:  S3PathUtils,
        CONST_STORAGESYSTEM.GCS.value:  GCSPathUtils,
        CONST_STORAGESYSTEM.AZ.value:   AZPathUtils,
        CONST_STORAGESYSTEM.SFTP.value: SFTPPathUtils,
        CONST_STORAGESYSTEM.SSH.value:  SSHPathUtils,
        # Add other filesystem formatters as needed
    }


    @classmethod
    def _get_util_class(cls, storage_system: str) -> Type[BasePathUtils]:
        """
        Returns the path utility class for the given storage system.

        :param storage_system: The storage system for which to get the path utility class.
        :return: The path utility class for the given storage system.
        """
        util_class: Optional[Type[BasePathUtils]] = cls.path_util_classes.get(storage_system, None)

        if not util_class:
            raise ValueError(f"Unsupported storage_system: {storage_system}")
        
        return util_class


    @classmethod
    def format_path(cls, path: Optional[Union[str, UPath]]) -> Optional[UPath]:

        if not path:
            return None

        # if isinstance(path, UPath):
        #     return path

        storage_system: str|None = cls.identify_storage_system(path)
        util_class: Type[BasePathUtils] = cls._get_util_class(storage_system=storage_system) if storage_system else LocalPathUtils

        return util_class.format_path(path=path)

    @classmethod
    def combine_path_and_filename(cls, path:  Optional[Union[str, UPath]], filename: Optional[str]) -> Optional[UPath]:

        storage_system: str | None = cls.identify_storage_system(path)
        util_class: Type[BasePathUtils] = cls._get_util_class(storage_system=storage_system) if storage_system else LocalPathUtils

        return util_class.combine_path_and_filename(path=path, filename=filename)

    @classmethod
    def path_to_str(cls, path:  Optional[Union[str, UPath]]) -> Optional[str]:

        if not path:
            return None

        storage_system: str | None = cls.identify_storage_system(path)
        util_class: Type[BasePathUtils] = cls._get_util_class(storage_system=storage_system) if storage_system else LocalPathUtils

        return util_class.path_to_str(path=path)

    @classmethod
    def identify_storage_system(cls, path: Optional[Union[str, UPath]]) -> Optional[str]:
        """
        Identifies the storage system based on the given path or UPath object.

        :param path: The path as a string or UPath object.
        :return: A string indicating the storage system ('local', 's3', 'gcs', 'azure', 'sftp', 'ssh').
        """

        return BasePathUtils.identify_storage_system(path=path)

    @classmethod
    def get_local_platform_slash(cls) -> str:

        return BasePathUtils.get_local_platform_slash()