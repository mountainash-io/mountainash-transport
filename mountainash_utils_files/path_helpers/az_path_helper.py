from upath import UPath
from typing import Union, Any

from mountainash_constants import CONST_STORAGESYSTEM
from .base_path_helper import BasePathHelper

class AZPathHelper(BasePathHelper):

    @classmethod
    def format_path(cls, path: Union[str, UPath]) -> UPath:
        """
        Formats a given path as a valid AZ UPath object.

        :param path: The input path as either a str or UPath object.
        :return: A formatted UPath object with an AZ scheme.
        """
        path_str: str|None = cls.path_to_str(path)

        # Normalize and ensure the path starts with "AZ://"
        normalized_path_str: str | None = cls._normalize_AZ_path(path_str)
        clean_path_str: str | None = cls.strip_trailing_slashes(normalized_path_str)

        # Construct UPath, catching any errors related to path construction
        try:
            return UPath(clean_path_str)
        except Exception as e:
            raise ValueError(f"Invalid AZ path: {clean_path_str} - {e}")

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
    def _normalize_AZ_path(path_str: str|None) -> str|None:
        """
        Normalizes an AZ path string, ensuring it starts with "AZ://"
        and correcting common path errors.

        :param path_str: The raw path string to normalize.
        :return: A normalized AZ path string.
        """

        return BasePathHelper._normalize_path_schema(path_str=path_str, scheme_key=CONST_STORAGESYSTEM.AZ.value)
