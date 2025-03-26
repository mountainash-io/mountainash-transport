from typing import Any, List, Union, IO, Optional, Iterator
from upath import UPath
from .base_file_helper import Base_FileHelper

from mountainash_utils_files.path_helpers import PathHelper
from mountainash_utils_files.path_helpers import S3PathHelper
from mountainash_settings import SettingsParameters, get_settings
from mountainash_settings.settings.auth.storage.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_settings.settings.auth.storage.providers.s3 import S3StorageAuthSettings

import io
import boto3
from botocore.exceptions import ClientError
from urllib.parse import unquote

class S3Express_FileHelper(Base_FileHelper):
    """
    File helper for AWS S3 Express storage class which uses directory buckets.
    Directory buckets provide single-digit millisecond data access and are organized
    in a hierarchical structure.
    """

    def __init__(self, 
                 auth_parameters: SettingsParameters
                 ) -> None:
        
        # Check if auth parameters are of the correct type
        if not isinstance(get_settings(auth_parameters), S3StorageAuthSettings):
            raise ValueError(f"Invalid auth parameters type: {type(get_settings(auth_parameters))}. Must be S3StorageAuthSettings")

        self.auth_parameters = auth_parameters

        # S3 Express uses a different storage provider type
        # Assuming CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS exists or will be added
        self.storage_provider_type = CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS

        # Connection requirements
        self.requires_io_connection = True
        self.requires_ssh_connection = False

        # Initialize client
        self.io_client: Optional[boto3.client] = None
        self.connect()

        self.set_interface_attributes()

    #================================================================
    # Connection Attributes

    def set_interface_attributes(self):
        """Set the interface attributes for S3Express operations."""
        # Attributes - S3 Express supports the same operations as S3
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

        # S3 Express has true directory support unlike standard S3
        self.supports_directories = True

    #================================================================
    # Connection operations

    def connect(self) -> bool:
        """Connect to the S3 Express using boto3 client."""
        connected = self.check_if_io_connected()
        
        settings = get_settings(self.auth_parameters)

        if not connected:
            if self.io_client is not None:
                self.io_client = None

            try:
                # S3 Express uses a different endpoint format
                # Control endpoint: s3express-control.{region}.amazonaws.com
                # Data endpoint: {bucket-name}--x-s3.{region}.amazonaws.com
                
                # Extract zone ID from bucket name (assuming format: base-name--zonal-id--x-s3)
                bucket_parts = settings.BUCKET.split('--')
                if len(bucket_parts) < 3 or not settings.BUCKET.endswith('--x-s3'):
                    raise ValueError(f"Invalid S3 Express bucket name: {settings.BUCKET}. Format should be base-name--zonal-id--x-s3")
                
                zone_id = bucket_parts[1]
                region = settings.REGION
                
                # For S3 Express, we need to specify the zone
                self.io_client = boto3.client(
                    service_name="s3",
                    aws_access_key_id=settings.ACCESS_KEY_ID,
                    aws_secret_access_key=settings.SECRET_ACCESS_KEY,
                    use_ssl=settings.USE_SSL,
                    region_name=region,
                    config=boto3.session.Config(
                        s3={'use_accelerate_endpoint': False,
                            'addressing_style': 'virtual'}
                    )
                )

                # Test the connection
                if self.check_if_io_connected():
                    print('Connection to S3 Express successful.')
                    return True
                else:
                    print('Connection to S3 Express failed.')
                    return False
            except ClientError as e:
                print(f'Error connecting to S3 Express: {e}')
                return False
        else:
            return True

    def check_if_io_connected(self) -> bool:
        """Check if connected to S3 Express by trying to list objects."""
        settings = get_settings(self.auth_parameters)

        if not self.io_client:
            return False

        try:            
            # List objects in bucket with a limit of 1
            objects = self.io_client.list_objects_v2(
                Bucket=settings.BUCKET, 
                MaxKeys=1
            )
            return 'Contents' in objects or objects.get('KeyCount', 0) >= 0
        except ClientError as e:
            print(f'Failed to list S3 Express objects: {e}')
            return False

    def get_connection_client_parameters(self) -> dict:
        """Get connection client parameters for S3 Express."""
        transport_params: dict[str, Any] = {
            'client': self.io_client
        }
        return transport_params

    #================================================================
    # File operations

    def _native_put_object_from_stream(self,
                   destination_path: UPath, 
                   source_stream: io.BytesIO, 
                   length: int,            
                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False
                   ) -> bool|Any:
        """Put an object to S3 Express from a stream."""
        
        settings = get_settings(self.auth_parameters)

        # Get bucket name and object path
        bucket_name: str| None = settings.BUCKET  # Use the bucket from settings
        object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=destination_path)

        # Verify bucket exists
        bucket_exists: bool = self._bucket_exists(bucket_name=bucket_name)
        if not bucket_exists:
            return False

        # Process source stream (encryption, compression)
        processed_source_stream: io.BytesIO = self.process_source_stream(
            source_stream=source_stream,
            encrypt=encrypt, 
            decrypt=decrypt,
            compress=compress,
            decompress=decompress
        )

        # Upload to S3 Express
        try:
            result = self.io_client.put_object(
                Bucket=bucket_name, 
                Key=object_name, 
                Body=processed_source_stream
            ) if self.io_client else False
            return result
        except ClientError as e:
            print(f"Error putting object to S3 Express: {e}")
            return False

    def _native_put_object_from_path(self, 
                   destination_path: UPath, 
                   source_path: UPath,
                   **kwargs            
                   ) -> bool:
        """Put an object to S3 Express from a local file path."""
        
        self.check_kwargs_for_compression_encryption("_native_put_object_from_path", **kwargs)

        settings = get_settings(self.auth_parameters)

        # Format Source
        source_path_str: str | None = PathHelper.path_to_str(path=source_path)

        # Get object name
        object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=destination_path)

        # Upload file
        try:
            with open(source_path_str, 'rb') as file_data:
                self.io_client.upload_fileobj(
                    file_data,
                    settings.BUCKET,
                    object_name
                )
            return True
        except ClientError as e:
            print(f"Error putting object from path to S3 Express: {e}")
            return False

    def _native_get_object_to_stream(self,
                   source_path: UPath, 
                   destination_stream: IO,          
                   length: int = 0,
                   encrypt: bool = False,
                   decrypt: bool = False,
                   compress: bool = False,
                   decompress: bool = False
                   ) -> bool:
        """Get an object from S3 Express to a stream."""

        object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=source_path)
        settings = get_settings(self.auth_parameters)

        try:
            response = self.io_client.get_object(
                Bucket=settings.BUCKET, 
                Key=object_name
            )
            source_stream = io.BytesIO(response['Body'].read())
            
            # Process and copy to destination stream
            self.copy_stream_to_stream(
                source_stream=source_stream, 
                destination_stream=destination_stream,
                encrypt=encrypt, 
                decrypt=decrypt, 
                compress=compress, 
                decompress=decompress
            )
            return True
        except ClientError as e:
            print(f"Error getting object from S3 Express to stream: {e}")
            return False

    def _native_get_object_to_path(self, 
                   source_path: UPath, 
                   destination_path: UPath,            
                   **kwargs
                   ) -> bool|Any:
        """Get an object from S3 Express to a local file path."""
        
        self.check_kwargs_for_compression_encryption("_native_get_object_to_path", **kwargs)
        settings = get_settings(self.auth_parameters)

        str_destination_path: str | None = PathHelper.path_to_str(path=destination_path)
        
        # Get object name
        object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=source_path)

        # Download file
        try:
            with open(str_destination_path, 'wb') as file_data:
                self.io_client.download_fileobj(
                    settings.BUCKET,
                    object_name,
                    file_data
                )
            return True
        except ClientError as e:
            print(f"Error getting object from S3 Express to path: {e}") 
            return False

    #================================================================
    # Filesystem operations

    def _list_bucket_names(self) -> Optional[List]:
        """List all S3 Express directory bucket names."""

        if not self.io_client:
            return None

        try:
            # S3 Express requires a different API call for listing directory buckets
            response = self.io_client.list_directory_buckets()
            
            buckets = [bucket['Name'] for bucket in response.get('Buckets', [])] if response else None
            return buckets
        except ClientError as e:
            print(f'Failed to list S3 Express directory buckets: {e}')
            return None

    def _bucket_exists(self, 
                      bucket_name: str) -> bool:
        """Check if an S3 Express directory bucket exists."""

        if not self.io_client:
            return False 

        try:
            # For S3 Express, we need to check if a specific directory bucket exists
            self.io_client.head_bucket(Bucket=bucket_name)
            return True
        except ClientError:
            return False

    def _find_objects(self, path: Union[str, UPath], maxkeys: Optional[int] = 999999) -> Optional[Iterator[Any]]:
        """Find objects in S3 Express that match the given path."""

        u_path = PathHelper.format_path(path) 
        if not u_path:
            return None

        settings = get_settings(self.auth_parameters)

        self.connect()

        if self.io_client:
            relative_path: str | None = S3PathHelper.get_path_folders_and_filename(u_path)

            if not relative_path:
                print(f'Failed to get relative path from path: {u_path}')
                return None

            wildcard: bool = True if '*' in relative_path else False

            if wildcard:
                # Get prefix up to the wildcard
                prefix_relative_path = relative_path[:relative_path.index('*')]
            else:
                prefix_relative_path = relative_path

            try:
                objects = self.io_client.list_objects_v2(
                    Bucket=settings.BUCKET, 
                    Prefix=prefix_relative_path,
                    MaxKeys=maxkeys
                )      

                return objects if objects and objects.get('KeyCount', 0) > 0 else None
            except ClientError as e:
                print(f"Error listing objects from S3 Express: {e}")
                return None

    def list_sources(self, path: Optional[Union[str, UPath]], **kwargs) -> Optional[List[str|None]]:
        """List available data sources in S3 Express at the specified path."""

        u_path: UPath | None = PathHelper.format_path(path) 
        if not u_path:
            return []

        self.connect()

        if self.io_client:
            try:
                objects = self._find_objects(path=path)

                return [obj['Key'] for obj in objects.get('Contents', [])] if objects and objects.get('KeyCount', 0) > 0 else []
            except ClientError as e:
                print(f"Error listing sources from S3 Express: {e}")
                return []
            
    def get_size(self, path: Union[str, UPath]) -> int:
        """Get the size of data at the specified path in S3 Express."""
        
        u_path: UPath | None = PathHelper.format_path(path=path) 
        if not u_path:
            return 0

        self.connect()
        
        if self.io_client:
            try:
                objects: Iterator[Any] | None = self._find_objects(path=u_path)

                object_sizes: list[int] = [obj['Size'] for obj in objects.get('Contents', [])] if objects and objects.get('KeyCount', 0) > 0 else []

                return sum(object_sizes)
            except ClientError as e:
                print(f"Error getting size from S3 Express: {e}")
                return 0
        return 0

    def path_exists(self, path: Union[str, UPath]) -> bool:
        """Check if the specified path exists in S3 Express."""
        
        u_path = PathHelper.format_path(path=path) 
        if not u_path:
            return False

        self.connect()

        settings = get_settings(self.auth_parameters)
        object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=u_path)
        
        if not object_name:
            return False

        try:
            # For a directory check (path ending with '/')
            if object_name.endswith('/'):
                # Directory check using list_objects_v2 with prefix
                response = self.io_client.list_objects_v2(
                    Bucket=settings.BUCKET,
                    Prefix=object_name,
                    MaxKeys=1
                )
                return response.get('KeyCount', 0) > 0
            else:
                # File check using head_object
                self.io_client.head_object(
                    Bucket=settings.BUCKET,
                    Key=object_name
                )
                return True
        except ClientError:
            return False

    def path_is_dir(self, path: Union[str, UPath]) -> bool:
        """Check if the specified path is a directory in S3 Express."""
        
        # S3 Express has true directory support
        u_path = PathHelper.format_path(path=path)
        settings = get_settings(self.auth_parameters)

        if not u_path:
            return False

        try:
            prefix = S3PathHelper.get_path_folders_and_filename(u_path)
            if not prefix:
                return False

            # Ensure prefix ends with '/'
            if not prefix.endswith('/'):
                prefix += '/'

            # Check if directory exists by listing objects with this prefix
            response = self.io_client.list_objects_v2(
                Bucket=settings.BUCKET,
                Prefix=prefix,
                Delimiter='/',
                MaxKeys=1
            )
            
            # If this path exists as a common prefix, it's a directory
            return len(response.get('CommonPrefixes', [])) > 0 or response.get('KeyCount', 0) > 0
        except ClientError as e:
            print(f"Error checking if path is directory in S3 Express: {e}")
            return False
    
    def path_is_file(self, path: Union[str, UPath]) -> bool:
        """Check if the specified path is a file in S3 Express."""
        
        u_path: UPath | None = PathHelper.format_path(path) 
        settings = get_settings(self.auth_parameters)

        if not u_path:
            return False

        try:
            object_name = S3PathHelper.get_path_folders_and_filename(u_path)
            
            if not object_name:
                return False
                
            # Ensure not a directory (doesn't end with '/')
            if object_name.endswith('/'):
                return False
                
            # Check if object exists
            self.io_client.head_object(
                Bucket=settings.BUCKET,
                Key=object_name
            )
            return True
        except ClientError:
            return False

    def create_directory(self, path: Union[str, UPath]) -> bool:
        """Create a directory in S3 Express if it doesn't exist."""
        
        # S3 Express has true directory support
        u_path = PathHelper.format_path(path=path)
        settings = get_settings(self.auth_parameters)

        if not u_path:
            return False

        try:
            dir_path = S3PathHelper.get_path_folders_and_filename(u_path)
            if not dir_path:
                return False

            # Ensure it ends with / to represent a directory
            if not dir_path.endswith('/'):
                dir_path += '/'

            # Create an empty object with the directory key
            self.io_client.put_object(
                Bucket=settings.BUCKET,
                Key=dir_path,
                Body=b''
            )
            return True
        except ClientError as e:
            print(f"Error creating directory in S3 Express: {e}")
            return False