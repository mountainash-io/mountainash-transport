import os
import io
from typing import Any, List, Union, IO, Optional

from upath import UPath
from .base_file_helper import Base_FileHelper

from mountainash_utils_files.path_helpers import PathHelper
from mountainash_settings import SettingsParameters, get_settings
from mountainash_settings.settings.auth.storage.constants import CONST_STORAGE_PROVIDER_TYPE

class GCS_FileHelper(Base_FileHelper):
    """
    Google Cloud Storage implementation of the Base_FileHelper interface.
    Handles file operations on Google Cloud Storage.
    """

    def __init__(self, 
                 auth_parameters: SettingsParameters
                 ) -> None:
        """
        Initialize the GCS_FileHelper.
        
        Args:
            auth_parameters: Settings parameters for authentication
        """
        # Initialize base class
        super().__init__()

        self.auth_parameters = auth_parameters
        self.storage_provider_type = CONST_STORAGE_PROVIDER_TYPE.GCS
        self.storage_system = "GCS"
        
        # Get auth settings
        self.io_auth_settings = get_settings(auth_parameters)
        
        # Connection requirements
        self.requires_io_connection = True
        self.requires_ssh_connection = False

        # Initialize client
        self.io_client = None
        
        # Set interface attributes and connect
        self.set_interface_attributes()
        self.connect()

    def set_interface_attributes(self):
        """Set the interface attributes for GCS storage."""
        # Native method support
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

        self.supports_native_get_to_local_path = False
        self.supports_encrypt_native_get_to_local_path = False
        self.supports_decrypt_native_get_to_local_path = False
        self.supports_compress_native_get_to_local_path = False
        self.supports_decompress_native_get_to_local_path = False

        self.supports_native_put_from_local_path = True
        self.supports_encrypt_native_put_from_local_path = True
        self.supports_decrypt_native_put_from_local_path = True
        self.supports_compress_native_put_from_local_path = True
        self.supports_decompress_native_put_from_local_path = True

        self.supports_native_get_to_native_path = False
        self.supports_encrypt_native_get_to_native_path = False
        self.supports_decrypt_native_get_to_native_path = False
        self.supports_compress_native_get_to_native_path = False
        self.supports_decompress_native_get_to_native_path = False

        self.supports_native_put_from_native_path = False
        self.supports_encrypt_native_put_from_native_path = False
        self.supports_decrypt_native_put_from_native_path = False
        self.supports_compress_native_put_from_native_path = False
        self.supports_decompress_native_put_from_native_path = False

        # Smart open support
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

        # General support
        self.supports_get_to_stream = False
        self.supports_get_to_path = True
        self.supports_put_from_stream = True
        self.supports_put_from_path = True

        # Preferences
        self.prefer_native_on_get = True
        self.prefer_smartopen_on_get = False
        self.prefer_native_on_put = True
        self.prefer_smartopen_on_put = False

        # Polars support
        self.supports_polars_native_read_parquet = True
        self.supports_polars_stream_read_parquet = True
        self.supports_decrypt_polars_read_parquet = True
        self.supports_decompress_polars_read_parquet = True
        self.supports_pyarrow_write_parquet = True
        self.supports_encrypt_pyarrow_write_parquet = True
        self.supports_compress_pyarrow_write_parquet = True

        self.supports_directories = False

    #================================================================
    # Connection operations

    def connect(self) -> bool:
        """Connect to GCS."""
        # For now, return True as smart-open handles GCS connections
        # In a full implementation, you would initialize the GCS client here
        return True

    def check_if_io_connected(self) -> bool:
        """Check if connected to GCS."""
        # For now, return True as smart-open handles GCS connections
        return True

    def get_connection_client_parameters(self) -> dict:
        """Get connection client parameters."""
        transport_params: dict[str, Any] = {}
        return transport_params

    #================================================================
    # File operations

    def _native_put_object_from_stream(self,
                   destination_path: UPath, 
                   source_stream: IO, 
                   length: int,            
                   encrypt: Optional[bool] = False,
                   decrypt: Optional[bool] = False,
                   compress: Optional[bool] = False,
                   decompress: Optional[bool] = False
                   ) -> bool:
        """Put an object to GCS from a stream."""
        try:
            with self.open_write_binarystream(destination_path=destination_path) as destination_stream:
                self.copy_stream_to_stream(
                    source_stream=source_stream, 
                    destination_stream=destination_stream,
                    encrypt=encrypt, 
                    decrypt=decrypt, 
                    compress=compress, 
                    decompress=decompress
                )
            return True
        except Exception as e:
            print(f"Error putting object from stream to {destination_path}: {e}")
            return False

    def _native_put_object_from_path(self, 
                   destination_path: UPath, 
                   source_path: UPath,      
                   **kwargs        
                   ) -> bool:
        """Put an object to GCS from a local path."""
        self.check_kwargs_for_compression_encryption("_native_put_object_from_path", **kwargs)
        
        try:
            with open(source_path, 'rb') as source_file:
                with self.open_write_binarystream(destination_path=destination_path) as destination_stream:
                    destination_stream.write(source_file.read())
            return True
        except Exception as e:
            print(f"Error copying file from {source_path} to {destination_path}: {e}")
            return False

    def _native_get_object_to_stream(self,
                   source_path: UPath, 
                   destination_stream: IO,  
                   length: int,            
                   encrypt: Optional[bool] = False,
                   decrypt: Optional[bool] = False,
                   compress: Optional[bool] = False,
                   decompress: Optional[bool] = False
                   ) -> bool:
        """Get an object from GCS to a stream."""
        try:
            with self.open_read_binarystream(source_path=source_path) as source_stream:
                self.copy_stream_to_stream(
                    source_stream=source_stream, 
                    destination_stream=destination_stream,
                    encrypt=encrypt, 
                    decrypt=decrypt, 
                    compress=compress, 
                    decompress=decompress
                )
            return True
        except Exception as e:
            print(f"Error getting object from {source_path} to stream: {e}")
            return False

    def _native_get_object_to_path(self, 
                   source_path: UPath, 
                   destination_path: UPath,
                   **kwargs            
                   ) -> bool:
        """Get an object from GCS to a local path."""
        self.check_kwargs_for_compression_encryption("_native_get_object_to_path", **kwargs)
        
        try:
            with self.open_read_binarystream(source_path=source_path) as source_stream:
                with open(destination_path, 'wb') as destination_file:
                    destination_file.write(source_stream.read())
            return True
        except Exception as e:
            print(f"Error copying file from {source_path} to {destination_path}: {e}")
            return False

    #================================================================
    # Filesystem operations

    def list_sources(self, path: Union[str, UPath], **kwargs) -> List[UPath]:
        """
        List available data sources in the specified path or directory.
        """
        u_path: UPath|None = PathHelper.format_path(path) 

        if not u_path:
            return []

        try:
            # Use glob to list objects with optional pattern
            pattern = kwargs.get('pattern', '*')
            paths = list(u_path.glob(pattern))
            return [UPath(p) for p in paths]
        except Exception as e:
            print(f"Error listing sources: {e}")
            return []

    def path_exists(self, path: Optional[Union[str, UPath]], **kwargs) -> bool:
        """
        Check if the specified path exists.
        """
        u_path: UPath|None = PathHelper.format_path(path)        

        if not u_path:
            return False

        try:
            return u_path.exists()
        except Exception as e:
            print(f"Error checking if path exists: {e}")
            return False

    def get_size(self, path: Optional[Union[str, UPath]]) -> int:
        """
        Get the size of the data at the specified path.
        """
        u_path: UPath|None = PathHelper.format_path(path) 

        if not u_path:
            return 0

        try:
            stat = u_path.stat()
            return stat.st_size if hasattr(stat, 'st_size') else 0
        except Exception as e:
            print(f"Error getting size: {e}")
            return 0

    def path_is_dir(self, path: Optional[Union[str, UPath]]) -> bool:
        """
        Checks if the specified path is a directory.
        """
        u_path: UPath|None = PathHelper.format_path(path)        

        if not u_path:
            return False

        try:
            return u_path.is_dir()
        except Exception as e:
            print(f"Error checking if path is directory: {e}")
            return False

    def path_is_file(self, path: Optional[Union[str, UPath]]) -> bool:
        """
        Checks if the specified path is a file.
        """
        u_path: UPath|None = PathHelper.format_path(path)        

        if not u_path:
            return False

        try:
            return u_path.is_file()
        except Exception as e:
            print(f"Error checking if path is file: {e}")
            return False

    def create_directory(self, path: Optional[Union[str, UPath]]) -> bool:
        """
        Creates a directory if it does not exist.
        Note: GCS doesn't have true directories, but this can create a placeholder object.
        """
        # GCS doesn't have true directories, so this is a no-op
        # In practice, directories are implied by object names with slashes
        return True