from typing import Union, Optional
from .base_path_helper import BasePathHelper

from upath import UPath

# from ..constants import CONST_STORAGESYSTEM

class LocalPathHelper(BasePathHelper):



    @classmethod
    def format_namespace(cls, namespace: Optional[str] = None) -> Optional[str]:
        """
        Formats a given namespace as a valid S3 namespace.

        :param namespace: The input namespace as a string.
        :return: A formatted namespace string.
        """

        return f"file://{namespace}" if namespace else "file://"

    @classmethod
    def format_path(cls, path: Optional[Union[str, UPath]]) -> Optional[UPath]:
        """
        Formats a path string, resolving home directory and removing redundant slashes.

        :param path: A string representing the path.
        :return: A UPath object representing the formatted path.
        """
        # Create a UPath object, which should handle various filesystems transparently
        # Expand user's home directory shorthand (~)

        path_str: Optional[str] = cls.path_to_str(path=path)

        if not path_str:
            return None

        #Let "/" alone!
        if len(path_str) > 1:
            clean_path_str: str | None = cls.strip_trailing_slashes(path_str)
        else:
            clean_path_str = path_str

        if not clean_path_str:
            return None

        try:
            u_path: UPath|None = UPath(UPath(clean_path_str).expanduser()) if clean_path_str else None

        except Exception as e:
            raise ValueError(f"Invalid path: {path} - {e}")

        return u_path



    # @classmethod
    # def path_exists(cls,  path: Union[str, UPath]) -> bool:
    #     """
    #     Checks if the specified path exists.

    #     :param path: The path to check.
    #     :return: True if the path exists, False otherwise.
    #     """
    #     u_path: UPath = cls.format_path(path)

    #     if u_path.is_file() or u_path.is_dir():
    #         return True
    #     else:
    #         return False
