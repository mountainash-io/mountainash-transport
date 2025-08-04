from typing import Union, Optional

from upath import UPath

from mountainash_constants import CONST_STORAGESYSTEM
from .base_path_helper import BasePathHelper

class SSHPathHelper(BasePathHelper):

    @classmethod
    def format_path(cls, path: Optional[Union[str, UPath]] = None) -> Optional[UPath]:
        """
        Formats a given path as a valid SSH UPath object.

        :param path: The input path as either a str or UPath object.
        :return: A formatted UPath object with an SSH scheme.
        """
        path_str: str|None = cls.path_to_str(path)

        # Normalize and ensure the path starts with "SSH://"
        normalized_path_str: str | None = cls._normalize_SSH_path(path_str) if path_str else None
        clean_path_str: str | None = cls.strip_trailing_slashes(normalized_path_str)

        # Construct UPath, catching any errors related to path construction
        try:
            return UPath(clean_path_str)
        except Exception as e:
            raise ValueError(f"Invalid SSH path: {clean_path_str} - {e}")

    @classmethod
    def combine_path_and_filename(cls, path: Optional[Union[str, UPath]] = None, filename: Optional[str]=None) -> Optional[UPath]:
        """
        Combines directory and filename into a single UPath object, correcting for issues like doubled-up slashes.

        :param path: The base path (or directory) as a string.
        :param filename: The filename as a string.
        :return: A UPath object representing the combined path.
        """
        u_path: UPath | None = cls.format_path(path)

        clean_filename: str|None = cls.strip_all_slashes(filename)

        if not u_path:
            return None

        if not clean_filename:
            return None
        return u_path / clean_filename



    @staticmethod
    def _normalize_SSH_path(path_str: str) -> Optional[str]:
        """
        Normalizes an SSH path string, ensuring it starts with "SSH://"
        and correcting common path errors.

        :param path_str: The raw path string to normalize.
        :return: A normalized SSH path string.
        """

        return BasePathHelper._normalize_path_schema(path_str=path_str, scheme_key=CONST_STORAGESYSTEM.SSH)
