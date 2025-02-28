from typing import Any, List, Union, IO, Optional, Iterator
from upath import UPath
from .base_file_helper import Base_FileHelper
from .s3_file_helper import S3_FileHelper  # Inherit from S3 since R2 is S3-compatible

from mountainash_utils_files.path_helpers import PathHelper
from mountainash_utils_files.path_helpers import S3PathHelper  # We can reuse S3PathHelper since R2 uses the same format
from mountainash_settings import SettingsParameters, get_settings
from mountainash_settings.settings.auth.storage.providers.r2 import R2StorageAuthSettings

from minio import Minio
from minio.error import MinioException
import io

class R2_FileHelper(S3_FileHelper):
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

        # Override storage system to R2
        self.storage_system = "R2"
        
        self.requires_io_connection = True
        self.requires_ssh_connection = False
        # self.supports_directories = False

        self.set_interface_attributes()

        # Initialize client as None
        self.io_client = None
        self.connect()

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
                    secret_key=settings.SECRET_ACCESS_KEY.get_secret_value(),
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
        settings = get_settings(self.auth_parameters)
        
        # Create Minio client for transport
        client = Minio(
            endpoint=settings.ENDPOINT, #.replace('https://', '').replace('http://', ''),
            access_key=settings.ACCESS_KEY_ID,
            secret_key=settings.SECRET_ACCESS_KEY.get_secret_value(),
            secure=settings.USE_SSL,
        )

        # Configure transport parameters
        transport_params = {
            'client': client
        }

        return transport_params