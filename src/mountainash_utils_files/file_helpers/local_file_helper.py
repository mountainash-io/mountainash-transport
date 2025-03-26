#file: src/mountainash_utils_files/file_helpers/local_file_helper.py

import os
from typing import Any, List, Union, IO,  Optional
from upath import UPath

import shutil
from .base_file_helper import Base_FileHelper

# from mountainash_acdrs.utils.data_storage.base_data_storage import Base_DataStorage
# from mountainash_acdrs.utils.data_storage.data_storage_functions import get_data_storage_object

from mountainash_utils_files.path_helpers import PathHelper
from mountainash_settings import SettingsParameters

from mountainash_settings.settings.auth.storage.constants import CONST_STORAGE_PROVIDER_TYPE

class Local_FileHelper(Base_FileHelper):


    def __init__(self, 
                 auth_parameters: SettingsParameters,
                 ) -> None:

        # super().__init__(auth_parameters)

        self.storage_provider_type =  CONST_STORAGE_PROVIDER_TYPE.LOCAL

        self.requires_io_connection = False
        self.requires_ssh_connection = False

        self.io_client = None
        self.ssh_client = None

        self.set_interface_attributes()


    def set_interface_attributes(self):
        # Attributes
        self.supports_native_get_to_stream = True
        self.supports_encrypt_native_get_to_stream = True
        self.supports_decrypt_native_get_to_stream = True
        self.supports_compress_native_get_to_stream = True
        self.supports_decompress_native_get_to_stream = True

        self.supports_native_put_from_stream = True
        self.supports_encrypt_native_put_from_stream = True
        self.supports_decrypt_native_put_from_stream = True
        self.supports_compress_native_put_from_stream = True
        self.supports_decompress_native_put_from_stream = True


        self.supports_native_get_to_local_path = True
        self.supports_encrypt_native_get_to_local_path = True
        self.supports_decrypt_native_get_to_local_path = True
        self.supports_compress_native_get_to_local_path = True
        self.supports_decompress_native_get_to_local_path = True

        self.supports_native_put_from_local_path = True
        self.supports_encrypt_native_put_from_local_path = True
        self.supports_decrypt_native_put_from_local_path = True
        self.supports_compress_native_put_from_local_path = True
        self.supports_decompress_native_put_from_local_path = True

        self.supports_smartopen_read_stream = True
        self.supports_encrypt_smartopen_read_stream = True
        self.supports_decrypt_smartopen_read_stream = True
        self.supports_compress_smartopen_read_stream = True
        self.supports_decompress_smartopen_read_stream = True

        self.supports_smartopen_write_stream = True
        self.supports_encrypt_smartopen_write_stream = True
        self.supports_decrypt_smartopen_write_stream = True
        self.supports_compress_smartopen_write_stream = True
        self.supports_decompress_smartopen_write_stream = True

        self.supports_get_to_stream = False
        self.supports_get_to_path = True
        self.supports_put_from_stream = True
        self.supports_put_from_path = True


        self.prefer_native_on_get = True
        self.prefer_smartopen_on_get = False
        self.prefer_native_on_put = True
        self.prefer_smartopen_on_put = False


        self.supports_polars_native_read_parquet = True
        self.supports_polars_stream_read_parquet = True
        self.supports_decrypt_polars_read_parquet = True
        self.supports_decompress_polars_read_parquet = True
        self.supports_pyarrow_write_parquet = True
        self.supports_encrypt_pyarrow_write_parquet = True
        self.supports_compress_pyarrow_write_parquet = True

        self.supports_directories = True


    #================================================================
    # Connection operations


    def connect(self) -> bool:
        return True

    def check_if_io_connected(self) -> bool:
        return True


    def get_connection_client_parameters(self) -> dict:

        client_parameters: dict[Any,Any] = {
        }

        return client_parameters

    #================================================================
    # Stream operations
    # - Inherited from Base_DataStorage:
    # - open_read_binarystream
    # - open_write_binarystream
    # - open_read_textstream
    # - open_write_textstream



    #================================================================
    # File operations
 
    def _native_put_object_from_stream(self,
                   destination_path: UPath, 
                   source_stream: IO, 
                   length: int,            
                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False
                   ) -> bool|Any:
        

        with self.open_write_binarystream(destination_path=destination_path) as destination_stream:

            self.copy_stream_to_stream(source_stream=source_stream, destination_stream=destination_stream,
                                    encrypt=encrypt, 
                                    decrypt=decrypt, 
                                    compress=compress, 
                                    decompress=decompress)                                       
        
    def _native_put_object_from_path(self, 
                   destination_path: UPath, 
                   source_path: UPath,      
                   **kwargs        
                    # encrypt: bool = False,
                    # decrypt: bool = False,
                    # compress: bool = False,
                    # decompress: bool = False
                   ) -> bool:
        

        self.check_kwargs_for_compression_encryption(**kwargs)  

        shutil.copyfile(src=source_path, dst=destination_path)       

        return True

    def _native_get_object_to_stream(self,
                   source_path: UPath, 
                   destination_stream: IO,  
                   length: int,            
                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False
                   ) -> bool:
        

        with self.open_read_binarystream(source_path=source_path) as source_stream:

            self.copy_stream_to_stream(source_stream=source_stream, destination_stream=destination_stream,
                                    encrypt=encrypt, 
                                    decrypt=decrypt, 
                                    compress=compress, 
                                    decompress=decompress)                                       
        
        return True

    def _native_get_object_to_path(self, 
                   source_path: UPath, 
                   destination_path: UPath,
                   **kwargs            
                    # encrypt: bool = False,
                    # decrypt: bool = False,
                    # compress: bool = False,
                    # decompress: bool = False
                   ) -> bool|Any:
        
        self.check_kwargs_for_compression_encryption(**kwargs)

        shutil.copyfile(src=source_path, dst=destination_path)       

        return True

        


    # def open_read_stream(self, source_path: Union[str, UPath], **kwargs) -> Iterable:
    #     """
    #     Read data from the specified source.
    #     """
    #     mode = kwargs.get('mode', 'rb')  # Default mode is text; use 'rb' for binary
    #     with open(uri=source_path, mode=mode) as file:
    #         for line in file:
    #             yield line

    # def open_write_stream(self, destination_path: Union[str, UPath], source_data: Iterable, **kwargs) -> None:
    #     """
    #     Write data to the specified destination.
    #     """
    #     mode = kwargs.get('mode', 'w')  # Default mode is text; use 'wb' for binary
    #     with open(uri=destination_path, mode=mode) as file:
    #         for chunk in source_data:
    #             file.write(chunk)


    # def open_read_stream(self, source_path: Union[str, UPath], **kwargs) -> Iterable:
    #     """
    #     Read data from the specified source.
    #     """
    #     mode = kwargs.get('mode', 'rb')  # Default mode is text; use 'rb' for binary
    #     with self.open_read_generator(source_path=source_path, **kwargs) as file:
    #         for line in file:
    #             yield line

    # def open_write_stream(self, destination_path: Union[str, UPath], source_data: Iterable, **kwargs) -> None:
    #     """
    #     Write data to the specified destination.
    #     """
    #     mode = kwargs.get('mode', 'w')  # Default mode is text; use 'wb' for binary
    #     with self.open_write_generator(destination_path=destination_path, **kwargs) as file:
    #         for chunk in source_data:
    #             file.write(chunk)



    # def open_read_generator(self, source_path: Union[str, UPath], **kwargs) -> Any:
    #     """
    #     Read data from the specified source.
    #     """
    #     mode = kwargs.get('mode', 'rb')  # Default mode is text; use 'rb' for binary
    #     return open(uri=source_path, mode=mode)

    # def open_write_generator(self, destination_path: Union[str, UPath],  **kwargs) -> Any:
    #     """
    #     Write data to the specified destination.
    #     """
    #     mode = kwargs.get('mode', 'wb')  # Default mode is text; use 'wb' for binary
    #     return open(uri=destination_path, mode=mode)


    # def read_data(self, source_path: Union[str, UPath], **kwargs) -> Any:
    #     """
    #     Read data from the specified source.
    #     """
    #     mode = kwargs.get('mode', 'r')  # Default mode is text; use 'rb' for binary
    #     with open(source_path, mode) as file:
    #         return file.read()

    
    # def write_data(self, destination_path: Union[str, UPath], data: Any, **kwargs):
    #     """
    #     Write data to the specified destination.
    #     """
    #     mode = kwargs.get('mode', 'w')  # Default mode is text; use 'wb' for binary
    #     with open(destination_path, mode) as file:
    #         file.write(data)

    # def upload_copy(self, destination_path: Union[str, UPath], source_path: Union[str, UPath], source_auth_parameters: SettingsParameters, overwrite: bool = False) -> bool:
    #     pass
    # @abstractmethod
    # def download_copy(self, destination_path: Union[str, UPath], source_path: Union[str, UPath], overwrite: bool = False) -> bool:
    #     pass

    # def upload_copy(self, destination_path: Optional[Union[str, UPath]], source_path: Optional[Union[str, UPath]], obj_source_storage: Base_DataStorage, overwrite: bool = False, fastmode: bool =False) -> bool:

    #     # destination_path = PathHelper.format_path(destination_path)

    #     u_source_path: UPath|None = PathHelper.format_path(path=source_path) 
    #     u_destination_path: UPath|None = PathHelper.format_path(path=destination_path) 

    #     if not u_source_path:
    #         raise ValueError(f"upload_copy(): Invalid source path: {source_path}")
    #     if not u_destination_path:
    #         raise ValueError(f"upload_copy(): Invalid destination path: {destination_path}")

    #     #Fastmode turns off these pretests
    #     if not fastmode:
    #         source_exists: bool =       obj_source_storage.path_exists(path=u_source_path)
    #         source_is_file: bool =      obj_source_storage.path_is_file(path=u_source_path)

    #         destination_exists: bool =              self.path_exists(path=u_destination_path)
    #         destination_parent_exists: bool =       self.prepare_path_parent(path=u_destination_path)                
    #         destination_parent_is_directory: bool = self.path_is_dir(path=u_destination_path.parent)                


    #         if not source_exists:
    #             print(f"upload_copy(): Source path does not exist: {source_path}")
    #             return False

    #         if not source_is_file:
    #             print(f"upload_copy(): Source path is not a file: {source_path}")
    #             return False

    #         if not destination_parent_exists:
    #             print(f"upload_copy(): Destination parent path does not exist: {u_destination_path.parent}")
    #             return False
            
    #         if destination_exists and not overwrite:
    #             print(f"upload_copy(): Destination path already exists: {destination_path}")
    #             return False

    #         if not destination_parent_is_directory:
    #             print(f"upload_copy(): Destination parent path must be a directory: {u_destination_path.parent}")
    #             return False
        
    #     try:
    #         #If here, we are ready to copy!
    #         source_stream: IO = obj_source_storage.open_read_binarystream(source_path=u_source_path)

    #         with self.open_write_binarystream(destination_path=u_destination_path) as dest_file:

    #             shutil.copyfileobj(source_stream, dest_file)

    #             # # If source_file is not seekable (e.g., a network stream), this will read the entire content into memory
    #             # if not source_stream.seekable():
    #             #     dest_file.write(source_stream.read())
    #             # else:
    #             #     # If source_file is seekable, use shutil.copyfileobj for efficiency
    #             #     source_stream.seek(0)  # Ensure we're copying from the start of the file
    #             #     shutil.copyfileobj(source_stream, dest_file)

    #         copied_destination_exists: bool = self.path_exists(path=u_destination_path)

    #         if not copied_destination_exists:
    #             print(f"upload_copy(): Destination path does not exist after copy: {destination_path}")
    #             return False

    #     except Exception as e:
    #         print(f"upload_copy(): Error copying file: {e}")
    #         return False

    #     return True


    # @abstractmethod
    # def download_copy(self, destination_path: Union[str, UPath], source_path: Union[str, UPath], overwrite: bool = False) -> bool:
    #     pass

    # def copy_from(self, source_path: Union[str, UPath]) -> IO:

    #     if not self.path_is_file(source_path):
    #         raise ValueError(f"Source path '{source_path}' is not a file")

    #     # smart_open handles the opening of various backend streams seamlessly
    #     file_obj = BytesIO(open(source_path, 'rb').read())
    #     file_obj.seek(0)  # Ensure the buffer's ready for reading from the start
    #     return file_obj

    def read_from_binarystream(self, source_path: Union[UPath,str], destination_stream: Any, **kwargs) -> bool:
        return True

    def write_to_binarystream(self, destination_path: Union[UPath,str], source_stream: Any, **kwargs) -> bool:
        return True


    
    def list_sources(self, path: Union[str, UPath], pattern: Optional[str] = "*", **kwargs) -> List[str]:
        """
        List available data sources in the specified path or directory.
        """

        # formatted_path = PathHelper.format_path(path) 
        # return list(formatted_path.fs.glob(path))
            
        u_path: UPath|None = PathHelper.format_path(path) 

        if not u_path:
            return []

        return [str(p) for p in u_path.glob(pattern)]

    
    def calculate_checksum(self, path: Optional[Union[str, UPath]], algorithm: str = 'sha256') -> None:
        """
        Calculate the checksum of the data at the specified path.
        """
        pass
        # hash_alg = hashlib.new(algorithm)
        # with open(path, 'rb') as file:
        #     for chunk in iter(lambda: file.read(4096), b""):
        #         hash_alg.update(chunk)
        # return hash_alg.hexdigest()

    
    def get_size(self, path: Optional[Union[str, UPath]]) -> int:
        """
        Get the size of the data at the specified path.
        """

        u_path: UPath|None = PathHelper.format_path(path) 

        if not u_path:
            return 0
                
        return os.path.getsize(filename=u_path)

    
    def path_exists(self,  path: Optional[Union[str, UPath]]) -> bool:
        """
        Checks if the specified path exists.

        :param path: The path to check.
        :return: True if the path exists, False otherwise.
        """
        u_path: UPath|None = PathHelper.format_path(path)        

        if not u_path:
            return False

        return u_path.exists()

    
    def path_is_dir(self,  path: Optional[Union[str, UPath]]) -> bool:
        """
        Checks if the specified path exists.

        :param path: The path to check.
        :return: True if the path exists, False otherwise.
        """
        u_path: UPath|None = PathHelper.format_path(path)        

        if not u_path:
            return False


        return u_path.is_dir()
    
    
    def path_is_file(self,  path: Optional[Union[str, UPath]]) -> bool:
        """
        Checks if the specified path exists.

        :param path: The path to check.
        :return: True if the path exists, False otherwise.
        """
        u_path: UPath|None = PathHelper.format_path(path)        

        if not u_path:
            return False


        return u_path.is_file()    


    
    def create_directory(
        self, 
        path: Optional[Union[str, UPath]]
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
        u_path: Optional[UPath] = PathHelper.format_path(path)

        if not u_path:
            print(f"Error creating local directory: {path}")
            return False

        try:
            if u_path and not u_path.exists():
                #can I use smart open to create a folder?
                u_path.mkdir(parents=True, exist_ok=True)

        except OSError:
            print(f"Error creating local directory: {u_path.path}")
            return False
        
        return True