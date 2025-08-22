from typing import Union, Optional

from upath import UPath

from ..constants import CONST_STORAGESYSTEM
from .base_path_helper import BasePathHelper

class SFTPPathHelper(BasePathHelper):

    @classmethod
    def format_namespace(cls, service_name: Optional[str] = None) -> Optional[str]:
        """
        Formats a given namespace as a valid S3 namespace.

        :param namespace: The input namespace as a string.
        :return: A formatted namespace string.
        """

        return f"sftp://{service_name}" if service_name else "sftp://"

    @classmethod
    def format_path(cls, path: Optional[Union[str, UPath]] = None) -> UPath:
        """
        Formats a given path as a valid SFTP UPath object.

        :param path: The input path as either a str or UPath object.
        :return: A formatted UPath object with an SFTP scheme.
        """
        path_str: str|None = cls.path_to_str(path)

        # Normalize and ensure the path starts with "sftp://"
        normalized_path_str = cls._normalize_sftp_path(path_str)
        clean_path_str: str | None = cls.strip_trailing_slashes(normalized_path_str)

        if not clean_path_str:
            raise ValueError(f"Invalid path: {path}")


        # Construct UPath, catching any errors related to path construction
        try:
            return UPath(clean_path_str)
        except Exception as e:
            raise ValueError(f"Invalid SFTP path: {clean_path_str} - {e}")

    # @classmethod
    # def combine_path_and_filename(cls, path: Union[str, UPath], filename: str) -> UPath:
    #     """
    #     Combines directory and filename into a single UPath object, correcting for issues like doubled-up slashes.

    #     :param path: The base path (or directory) as a string.
    #     :param filename: The filename as a string.
    #     :return: A UPath object representing the combined path.
    #     """
    #     u_path = cls.format_path(path)

    #     clean_filename: str = cls.strip_all_slashes(filename)

    #     return u_path / clean_filename



    @staticmethod
    def _normalize_sftp_path(path_str: Optional[str]) -> Optional[str]:
        """
        Normalizes an SFTP path string, ensuring it starts with "SFTP://"
        and correcting common path errors.

        :param path_str: The raw path string to normalize.
        :return: A normalized SFTP path string.
        """
        if not path_str:
            return None

        return BasePathHelper._normalize_path_schema(path_str, CONST_STORAGESYSTEM.SFTP)
