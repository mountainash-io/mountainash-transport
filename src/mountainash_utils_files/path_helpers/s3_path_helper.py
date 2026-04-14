from typing import Union, Optional
from upath import UPath

from .base_path_helper import BasePathHelper

class S3PathHelper(BasePathHelper):

    @classmethod
    def format_namespace(cls, path: Optional[UPath|str] = None, bucket_name: Optional[str] = None) -> Optional[str]:
        """
        Formats a given namespace as a valid S3 namespace.

        :param namespace: The input namespace as a string.
        :return: A formatted namespace string.
        """
        u_path: UPath | None = UPath(path) if path else None

        if bucket_name:
            str_bucket_name: str|None = bucket_name
        else:
            str_bucket_name = cls.get_path_bucketname(u_path)

        return f"s3://{str_bucket_name}" if bucket_name else "s3://"


    @classmethod
    def format_path(cls, path: Optional[Union[str, UPath]]) -> Optional[UPath]:
        """
        Formats a given path as a valid S3 UPath object.

        :param path: The input path as either a str or UPath object.
        :return: A formatted UPath object with an S3 scheme.
        """
        # Normalize and ensure the path starts with "s3://"

        u_path: UPath | None = UPath(path) if path else None
        path_str: str | None = cls.path_to_str(u_path)

        normalized_path_str = cls._normalize_s3_path(path_str=path_str)
        clean_path_str: str | None = cls.strip_trailing_slashes(normalized_path_str)

        if not clean_path_str:
            return None

        # Construct UPath, catching any errors related to path construction
        try:
            return UPath(clean_path_str)

        except Exception as e:
            raise ValueError(f"Invalid S3 path: {clean_path_str} - {e}")



    @classmethod
    def get_path_protocol(cls, path: Optional[str|UPath]) -> Optional[str]:

        u_path: UPath | None = cls.format_path(path)

        return u_path.protocol if u_path else None

    @classmethod
    def get_path_bucketname(cls, path: Optional[str|UPath]) -> Optional[str]:

        u_path: UPath | None = cls.format_path(path)

        #component strings
        folders_and_file: str | None = cls.get_path_folders_and_filename(u_path)
        bucket_file_and_folders: str | None = cls.get_path_bucket_folders_and_filename(u_path)

        #lengths
        len_file_and_folders: int = len(folders_and_file) if folders_and_file else 0
        len_bucket_file_and_folders: int = len(bucket_file_and_folders) if bucket_file_and_folders else 0
        bucket_end: int = len_bucket_file_and_folders - len_file_and_folders

        path_bucketname: str | None  = bucket_file_and_folders[0:bucket_end] if bucket_file_and_folders else None
        path_bucketname  = cls.strip_all_slashes(path_bucketname)

        return path_bucketname

    @classmethod
    def get_path_bucket_folders_and_filename(cls, path: Optional[str|UPath]) -> Optional[str]:

        u_path: UPath | None = cls.format_path(path)

        return u_path.path if u_path else None

    @classmethod
    def get_path_filename(cls, path: Optional[str|UPath]) -> Optional[str]:

        u_path: UPath | None = cls.format_path(path)

        return u_path.name if u_path else None


    @classmethod
    def get_path_filetype(cls, path: Optional[str|UPath]) -> Optional[str]:

        u_path: UPath | None = cls.format_path(path)
        return u_path.suffix if u_path else None

    @classmethod
    def get_path_folders(cls, path: Optional[str|UPath]) -> Optional[str]:

        u_path: UPath | None = cls.format_path(path)

        path_folders: str | None = "/".join(u_path.parts[1:-1]) if u_path else None
        path_folders = cls.strip_all_slashes(path_folders)

        return path_folders

    @classmethod
    def get_path_folders_and_filename(cls, path: Optional[str|UPath]) -> Optional[str]:

        u_path: UPath | None = cls.format_path(path)

        path_folders = cls.get_path_folders(u_path)
        path_filename = cls.get_path_filename(u_path)

        if path_folders:
            return f"{path_folders}/{path_filename}"
        elif path_filename:
            return path_filename
        else:
            return None



    # @classmethod
    # def combine_path_and_filename(cls, path: Union[str, UPath], filename: str) -> Optional[UPath]:
    #     """
    #     Combines directory and filename into a single UPath object, correcting for issues like doubled-up slashes.

    #     :param path: The base path (or directory) as a string.
    #     :param filename: The filename as a string.
    #     :return: A UPath object representing the combined path.
    #     """
    #     u_path: UPath | None = cls.format_path(path)

    #     if not u_path:
    #         raise ValueError(f"Invalid path: {path}")

    #     clean_filename: str|None = cls.strip_all_slashes(filename)

    #     if not clean_filename:
    #         raise ValueError(f"Invalid filename: {filename}")

    #     return u_path / clean_filename



    @staticmethod
    def _normalize_s3_path(path_str: Optional[str]) -> Optional[str]:
        """
        Normalizes an S3 path string, ensuring it starts with "s3://"
        and correcting common path errors.

        :param path_str: The raw path string to normalize.
        :return: A normalized S3 path string.
        """

        return BasePathHelper._normalize_path_schema(path_str, "S3")
