from typing import Any, List, Union, IO, Optional, Iterator
from upath import UPath
from .base_file_helper import Base_FileHelper
from .s3_file_helper import S3_FileHelper  # Inherit from S3 since R2 is S3-compatible

from mountainash_utils_files.path_helpers import PathHelper
from mountainash_utils_files.path_helpers import S3PathHelper  # We can reuse S3PathHelper since R2 uses the same format
from mountainash_settings import SettingsParameters, get_settings
from mountainash_settings.settings.auth.storage.providers.r2 import R2StorageAuthSettings
from mountainash_settings.settings.auth.storage.constants import CONST_STORAGE_PROVIDER_TYPE

from minio import Minio
from minio.error import MinioException
import io

class R2_FileHelper():
    """
    Cloudflare R2 File Helper implementation using Minio client.
    
    R2 is S3-compatible, so we can inherit much of the functionality from S3_FileHelper.
    """

    def __init__(self, 
                 auth_parameters: SettingsParameters
                 ) -> None:
        
        if not isinstance(get_settings(auth_parameters), R2StorageAuthSettings):
            raise ValueError(f"Invalid auth parameters type: {type(get_settings(auth_parameters))}. Must be R2StorageAuthSettings")
        self.auth_parameters = auth_parameters

        self.storage_provider_type =  CONST_STORAGE_PROVIDER_TYPE.R2


        # Override storage system to R2
        self.storage_system = "R2"
        
        self.requires_io_connection = True
        self.requires_ssh_connection = False
        # self.supports_directories = False

        self.set_interface_attributes()

        # Initialize client as None
        self.io_client = None
        self.connect()



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

        self.supports_smartopen_read_stream = False
        self.supports_encrypt_smartopen_read_stream = True
        self.supports_decrypt_smartopen_read_stream = True
        self.supports_compress_smartopen_read_stream = False
        self.supports_decompress_smartopen_read_stream = False

        self.supports_smartopen_write_stream = False
        self.supports_encrypt_smartopen_write_stream = False
        self.supports_decrypt_smartopen_write_stream = False
        self.supports_compress_smartopen_write_stream = False
        self.supports_decompress_smartopen_write_stream = False

        self.supports_get_to_stream = False
        self.supports_get_to_path = True
        self.supports_put_from_stream = True
        self.supports_put_from_path = True


        self.prefer_native_on_get = True
        self.prefer_smartopen_on_get = False
        self.prefer_native_on_put = True
        self.prefer_smartopen_on_put = False

        self.supports_directories = False



    #================================================================
    # IO Connection operations

    def connect(self) -> bool:
        """Connect to the R2 storage using Minio client."""
        
        connected = self.check_if_io_connected()
       
        if not connected:
            if self.io_client is not None:
                self.io_client = None

            try:
                # Get settings
                settings = get_settings(self.auth_parameters)
                
                # Configure Minio client for R2
                self.io_client = Minio(
                    endpoint=settings.ENDPOINT, #.replace('https://', '').replace('http://', ''),
                    access_key=settings.ACCESS_KEY_ID,
                    secret_key=settings.SECRET_ACCESS_KEY,
                    secure=settings.USE_SSL,
                    region='auto'
                )

                # Test the connection by listing objects
                if self.check_if_io_connected():
                    print('Connection to R2 successful.')
                    return True
                else:
                    print('Connection to R2 failed.')
                    return False
            except MinioException as e:
                print(f'Error connecting to R2: {e}')
                return False
        else:
            return True

    def check_if_io_connected(self) -> bool:
        """Check if connected to R2 by trying to list objects."""
        
        if not self.io_client:
            return False

        try:            
            settings = get_settings(self.auth_parameters)
            # List objects with a prefix to check connection
            objects = self.io_client.list_objects(settings.BUCKET, prefix="", recursive=False)
            # If we can list objects successfully, the connection is working
            return any(objects)

        except MinioException as e:
            print(f'Failed to list R2 objects: {e}')
            return False

    def get_connection_client_parameters(self) -> dict:
        """Get connection parameters for R2."""


        transport_params = super().get_connection_client_parameters()
        return transport_params
        
        # # Create Minio client for transport
        # client = Minio(
        #     endpoint=settings.ENDPOINT, #.replace('https://', '').replace('http://', ''),
        #     access_key=settings.ACCESS_KEY_ID,
        #     secret_key=settings.SECRET_ACCESS_KEY,
        #     secure=settings.USE_SSL,
        # )

        # # Configure transport parameters
        # new_transport_params = {
        #     'client': self.io_client
        # }

    def _find_objects(self, path: Union[str, UPath]) -> Optional[Iterator[Any]]:

        u_path = PathHelper.format_path(path) 

        if not u_path:
            return None
        
        self.connect()

        if self.io_client:
            bucket_name: str | None = S3PathHelper.get_path_bucketname(u_path)
            if not bucket_name:
                print(f'Failed to get bucket name from path: {u_path}')
                return None
            
            relative_path: str | None = S3PathHelper.get_path_folders_and_filename(u_path)
            if not relative_path:
                print(f'Failed to get relative path from path: {u_path}')
                return None

            wildcard: bool = True if '*' in relative_path else False

            if wildcard:
                # We need to substring the path up to the position of the first wildcard
                prefix_relative_path = relative_path[:relative_path.index('*')]
            else:
                prefix_relative_path = relative_path

            try:
                objects: Iterator[Any] = self.io_client.list_objects_v2(bucket_name=bucket_name, 
                                                                   prefix=prefix_relative_path, 
                                                                   recursive=True)
                return objects
            except Exception as e:
                print(f"Error listing objects: {e}")
                return None