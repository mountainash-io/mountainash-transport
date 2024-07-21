from typing import Union, Optional
import re
from abc import ABC

from upath import UPath
from urllib.parse import urlparse

from mountainash_utils_os import get_platform_slash
from mountainash_utils_dataclasses import DataclassUtils
from mountainash_constants import CONST_STORAGESYSTEM, CONST_STORAGESYSTEM_PREFIX

class BasePathHelper(ABC):

    @classmethod
    def format_path(cls, 
                    path: Optional[Union[str, UPath]]
                    ) -> Optional[UPath]:
        
        raise NotImplementedError("format_path must be implemented in subclasses")


    @classmethod
    def wildcard_match(cls, pattern: str, target_filename: str) -> bool:
        """
        Checks if the target filename matches the given wildcard pattern.

        :param pattern: The wildcard pattern, e.g., 'filename*.*', 'file*', 'filename1.*', 'filename*.csv'
        :param target_filename: The target filename to match, e.g., 'filename1.csv'
        :return: True if the target filename matches the pattern, False otherwise.
        """
        # Convert the wildcard pattern to a regular expression pattern
        # Escape special characters except for the wildcard '*', then replace '*' with '.*' to match any character zero or more times
        regex_pattern = re.escape(pattern).replace(r'\*', '.*')
        
        # Add start and end anchors to ensure the entire string must match
        regex_pattern = f'^{regex_pattern}$'

        # Perform the match using the regex pattern
        return bool(re.match(regex_pattern, target_filename))


    @classmethod
    def path_to_str(cls, path: Optional[Union[str, UPath]]) -> Optional[str]:
        """
        Converts a UPath object to its string representation.

        :param path: The UPath object.
        :return: The string representation of the path.
        """
        # u_path = cls.format_path(path)

        if not path:
            return None
        
        return str(path)
        # return str(object=UPath(path))
    
    @classmethod
    def get_local_platform_slash(cls) -> str:
        return get_platform_slash()


    @classmethod
    def strip_all_slashes(cls, path: Optional[Union[str, UPath]]) -> Optional[str]:

        # Remove trailing or leading slashes from filename
        path_str: str | None = cls.path_to_str(path=path)

        if path_str and len(path_str) > 1:
            path_str = path_str.strip("\\").strip("/")

        return path_str

    @classmethod
    def strip_trailing_slashes(cls, path: Optional[Union[str, UPath]]) -> Optional[str]:

        path_str: str | None = cls.path_to_str(path=path)

        # Remove trailing or leading slashes from filename
        if path_str  and len(path_str) > 1:
            path_str = path_str.rstrip("\\").rstrip("/")

        return path_str

    @classmethod
    def combine_path_and_filename(cls, path: Optional[Union[str, UPath]], filename: Optional[str]) -> Optional[UPath]:
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

    @classmethod
    def identify_storage_system(cls, path: Optional[Union[str, UPath]]) -> Optional[str]:
        """
        Identifies the storage system based on the given path or UPath object.

        :param path: The path as a string or UPath object.
        :return: A string indicating the storage system ('local', 's3', 'gcs', 'azure', 'sftp', 'ssh').
        """

        path_str: str | None = cls.path_to_str(path)

        if not path_str:
            return CONST_STORAGESYSTEM.LOCAL_DISK.value
      
        parsed = urlparse(path_str)
        path_scheme = parsed.scheme.lower()

        if path_scheme in DataclassUtils.get_enum_values_set(enumclass=CONST_STORAGESYSTEM_PREFIX):

            storage_system = CONST_STORAGESYSTEM_PREFIX.find_member(value=path_scheme)
            if storage_system is None:
                raise ValueError(f"Failed to identify storage system for path: {path_str}.")
            elif isinstance(storage_system, list) and len(storage_system) > 1:
                raise ValueError(f"Multiple storage systems found for path: {path_str}.")
            elif isinstance(storage_system, list) and len(storage_system) == 1:
                return storage_system[0]
            elif isinstance(storage_system, str):
                return storage_system
            else:
                raise ValueError(f"Failed to identify storage system for path: {path_str}")

        else:
            print(f"Could not identify storage prefix in {path} - Assuming LOCAL_DISK")
            return CONST_STORAGESYSTEM.LOCAL_DISK.value

    @classmethod
    def _normalize_path_schema(cls, path_str: Optional[str], scheme_key: str) -> Optional[str]:
        """
        Normalizes a path string, ensuring it starts with the specified scheme and "//".

        :param path_str: The raw path string to normalize.
        :param scheme: The URI scheme to ensure in the path (e.g., "s3", "gcs", "az").
        :return: A normalized path string with the correct scheme.
        """

        if not path_str or len(path_str) == 0:
            return None

        scheme_prefix = CONST_STORAGESYSTEM_PREFIX.get(member=scheme_key).lower()
        scheme_length = len(scheme_prefix)
        candidate_path: Optional[str] = None

        #TODO. Use urlparse to parse the path and check if the scheme is correct
        provided_scheme_str = path_str[:scheme_length]

        parsed = urlparse(path_str)
        # existing_scheme = parsed.scheme

        #Correct prefix and scheme
        if parsed.scheme == scheme_prefix:

            #All good
            if path_str.startswith(f"{scheme_prefix}://"):
                return path_str
            
            #All good but scheme was capitalised 
            if path_str.lower().startswith(f"{scheme_prefix}://"):
                #Only replace the start
                path_str.replace(f"{provided_scheme_str}:", f"{scheme_prefix}:", __count=1)
                if path_str.startswith(f"{scheme_prefix}://"):
                    return path_str
            else:
                #Perahaps the path was lacking slashes?
                candidate_path = f"{scheme_prefix}://{path_str.lstrip('/')}"
                raise ValueError(f"Failed to normalize path: '{path_str}' to scheme: '{scheme_key}'. The correct path *may* be '{candidate_path}', but you should check to be sure.'")

    # @classmethod
    # def identify_storage_system(cls, path: Union[str, UPath]) -> str:
    #     """
    #     Identifies the storage system based on the given path or UPath object.

    #     :param path: The path as a string or UPath object.
    #     :return: A string indicating the storage system ('local', 's3', 'gcs', 'azure', 'sftp', 'ssh').
    #     """
    #     # Ensure path is a UPath object
    #     if not isinstance(path, UPath):
    #         try:
    #             path_upath = UPath(UPath(path).expanduser())
    #             # Extract the scheme from the UPath object
    #             scheme = path_upath.parts[0].lower().split(":")[0]

    #         except Exception as e:
    #             print(f"Failed to convert path '{path}' to UPath: {e}. Using the path string as is.")
    #             scheme = path.lower().split(":")[0]
    #     else:
    #         path_upath = UPath(path.expanduser())
    #         # Extract the scheme from the UPath object
    #         scheme = path_upath.parts[0].lower().split(":")[0]

    #     # Map the scheme to the storage system
    #     if scheme == CONST_STORAGESYSTEM.LOCAL_DISK.value:  # Local paths might not have a scheme but have a drive
    #         identified_scheme = CONST_STORAGESYSTEM.LOCAL_DISK.value
    #     elif scheme == "/":  # Local paths on Linux / MacOS
    #         identified_scheme = CONST_STORAGESYSTEM.LOCAL_DISK.value

    #     elif re.match(pattern='^[a-z]$', string=scheme):  #Local paths on windows start with a single letter
    #         identified_scheme = CONST_STORAGESYSTEM.LOCAL_DISK.value
    #         if not is_platform_os_windows():
    #             print("Warning: Local Windows path identified in non-Windows system. Assuming local disk.")

    #     else:
    #         identified_scheme = CONST_STORAGESYSTEM.get(CONST_STORAGESYSTEM.find_member(scheme))

    #     if not identified_scheme:
    #         raise ValueError(f"Unsupported scheme: {scheme}")
    
    #     return identified_scheme
        

    #             # Check if the path starts with a known storage system prefix
    #     for storage_system, prefix in CONST_STORAGESYSTEM_PREFIX.items():
