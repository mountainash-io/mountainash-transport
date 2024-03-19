import os
import hashlib
from typing import Any, List, Union, IO
from upath import UPath
from smart_open import open
from .base_file_helper import Base_FileHelper

from mountainash_utils_files import PathHelper
from mountainash_settings import SettingsParameters, get_auth_settings, AuthSettings

class GCS_FileHelpere(Base_FileHelper):

    def __init__(self, 
                 auth_parameters: SettingsParameters
                 ) -> None:
        pass

    @classmethod
    def read_data(cls, source_path: Union[str, UPath], **kwargs) -> Any:
        """
        Read data from the specified source.
        """
        mode = kwargs.get('mode', 'r')  # Default mode is text; use 'rb' for binary
        with open(source_path, mode) as file:
            return file.read()

    @classmethod
    def write_data(cls, destination_path: Union[str, UPath], data: Any, **kwargs):
        """
        Write data to the specified destination.
        """
        mode = kwargs.get('mode', 'w')  # Default mode is text; use 'wb' for binary
        with open(destination_path, mode) as file:
            file.write(data)

    @classmethod
    def copy_to(cls, destination_path: Union[str, UPath], source_file: IO):
        pass

    @classmethod
    def copy_from(cls, source_path: Union[str, UPath]) -> None:
        pass


    @classmethod
    def list_sources(cls, path: Union[str, UPath] = "", **kwargs) -> List[str]:
        """
        List available data sources in the specified path or directory.
        """

        # formatted_path = PathHelper.format_path(path) 
        # return list(formatted_path.fs.glob(path))
            
        return [str(p) for p in UPath(path).glob(kwargs.get('pattern', '*'))]

    @classmethod
    def calculate_checksum(cls, path: Union[str, UPath], algorithm: str = 'sha256') -> None:
        """
        Calculate the checksum of the data at the specified path.
        """
        pass
        # hash_alg = hashlib.new(algorithm)
        # with open(path, 'rb') as file:
        #     for chunk in iter(lambda: file.read(4096), b""):
        #         hash_alg.update(chunk)
        # return hash_alg.hexdigest()

    @classmethod
    def get_size(cls, path: Union[str, UPath]) -> int:
        """
        Get the size of the data at the specified path.
        """
        return os.path.getsize(path)

    @classmethod
    def path_exists(cls,  path: Union[str, UPath]) -> bool:
        """
        Checks if the specified path exists.

        :param path: The path to check.
        :return: True if the path exists, False otherwise.
        """
        u_path: UPath|None = PathHelper.format_path(path)        

        if not u_path:
            return False
        
        return u_path.exists()

    @classmethod
    def path_is_dir(cls,  path: Union[str, UPath]) -> bool:
        """
        Checks if the specified path exists.

        :param path: The path to check.
        :return: True if the path exists, False otherwise.
        """
        u_path: UPath|None = PathHelper.format_path(path)        

        if not u_path:
            return False

        return u_path.is_dir()
    
    @classmethod
    def path_is_file(cls,  path: Union[str, UPath]) -> bool:
        """
        Checks if the specified path exists.

        :param path: The path to check.
        :return: True if the path exists, False otherwise.
        """
        u_path: UPath|None = PathHelper.format_path(path)        

        if not u_path:
            return False
        return u_path.is_file()    


    @classmethod
    def create_directory(
        cls, 
        path: Union[str, UPath]
        ) -> bool:
        """Creates a directory if it does not exist.

        Args:
            directory: The path of the directory to create.

        Returns:
            True if the directory was created or already exists, False otherwise.

        Example:
            fs = FilesystemInterface('local')
            created = fs.create_directory('data')
        """
        u_path: UPath|None = PathHelper.format_path(path)


        if not u_path:
            return False
        
        try:
            if not u_path.exists():
                #can I use smart open to create a folder?
                os.makedirs(name=u_path.path, exist_ok=True)

        except OSError:
            print(f"Error creating local directory: {u_path.path}")
            return False
        
        return True