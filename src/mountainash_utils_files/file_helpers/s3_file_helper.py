#file: src/mountainash_utils_files/file_helpers/s3_file_helper.py

from typing import Any, List, Union, IO, Optional, Iterator
from mountainash_settings.settings.base.base_settings import Dict
from upath import UPath
import os
from .base_file_helper import Base_FileHelper

from mountainash_utils_files.path_helpers import PathHelper
from mountainash_utils_files.path_helpers import S3PathHelper
from mountainash_settings import SettingsParameters, get_settings
from mountainash_settings.settings.auth.storage.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_settings.settings.auth.storage.providers.s3 import S3StorageAuthSettings

from ..dataclasses import FileMetadata

from minio import Minio
from minio.error import S3Error
from urllib.parse import unquote
import io
import boto3

class S3_FileHelper(Base_FileHelper):

    def __init__(self, 
                 auth_parameters: SettingsParameters
                 ) -> None:
        
        # super().__init__(auth_parameters)


        if not isinstance(get_settings(auth_parameters), S3StorageAuthSettings):
            raise ValueError(f"Invalid auth parameters type: {type(get_settings(auth_parameters))}. Must be RS3StorageAuthSettings")

        self.auth_parameters = auth_parameters

        self.storage_provider_type =  CONST_STORAGE_PROVIDER_TYPE.S3

        #Objects
        self.requires_io_connection = True
        self.requires_ssh_connection = False

        # self.endpoint_url = f"{self.io_auth_settings.ENDPOINT_URL}"
        # self.access_key = self.io_auth_settings.ACCESS_KEY_ID if self.io_auth_settings.ACCESS_KEY_ID else None
        # self.secret_key = self.io_auth_settings.SECRET_ACCESS_KEY if self.io_auth_settings.SECRET_ACCESS_KEY else None
        # self.use_ssl = self.io_auth_settings.USE_SSL

        #S3 specific 
        # self.bucket = self.io_auth_settings.BUCKET
        # self.service_name = self.io_auth_settings.BUCKET

        self.io_client: Optional[boto3.client] = None
        self.connect()

        self.set_interface_attributes()



    #================================================================
    # Connection Attributes


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

        self.supports_directories = False



    #================================================================
    # Connection operations

    
    def connect(self) -> bool:
        """Connect to the S3 server using MinIO client."""

        connected = self.check_if_io_connected()
        
        settings = get_settings(self.auth_parameters)

        if not connected:

            if self.io_client is not None:
                self.io_client = None

            try:
                # Extract hostname and port from endpoint_url
                # endpoint = settings.ENDPOINT_URL#.replace('http://', '').replace('https://', '')
                

                self.io_client = boto3.client(
                    # endpoint_url=settings.ENDPOINT_URL,
                    service_name="s3",
                    aws_access_key_id=settings.ACCESS_KEY_ID,
                    aws_secret_access_key=settings.SECRET_ACCESS_KEY,
                    use_ssl=settings.USE_SSL,
                    region_name=settings.REGION

                )

                # Test the connection by listing buckets
                if self.check_if_io_connected():
                    print('Connection to S3 successful.')
                    return True
                else:
                    print('Connection to S3 failed.')
                    return False
            except S3Error as e:
                print(f'Error connecting to S3: {e}')
                return False
        else:
            return True

    def check_if_io_connected(self) -> bool:
        """Check if connected to S3 by trying to list buckets."""
        

        settings = get_settings(self.auth_parameters)

        if not self.io_client:
            return False

        try:            
            # List objects in bucket with a limit of 1 to minimize data transfer
            objects = self.io_client.list_objects_v2(Bucket=settings.BUCKET, MaxKeys=1)
            return any(objects)
        except S3Error as e:
            print(f'Failed to list S3 buckets: {e}')
            return False


    def get_connection_client_parameters(self) -> dict:
        transport_params: dict[str, Any] = {
            'client': self.io_client
            # 'multipart_upload': False,
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
        
        settings = get_settings(self.auth_parameters)
        

        #Validate Destination
        bucket_name: str| None = S3PathHelper.get_path_bucketname(path=destination_path)
        object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=destination_path)

        bucket_exists: bool = self._bucket_exists(bucket_name=bucket_name)
        if not bucket_exists:
            return False

        #Process source stream
        processed_source_stream: io.BytesIO = self.process_source_stream(source_stream=source_stream,
                                                                        encrypt=encrypt, 
                                                                        decrypt=decrypt,
                                                                        compress=compress,
                                                                        decompress=decompress)

        # do it!
        try:
            result = self.io_client.put_object(Bucket=settings.BUCKET, 
                                             Key=object_name, 
                                             Body=processed_source_stream, 
                                             ContentLength=length) if self.io_client else False
            return result
        except S3Error as e:
            print(f"Error putting object: {e}")
            return False

        
    def _native_put_object_from_path(self, 
                   destination_path: UPath, 
                   source_path: UPath,
                   **kwargs            
                   ) -> bool:
        
        self.check_kwargs_for_compression_encryption("_native_put_object_from_path", **kwargs)

        settings = get_settings(self.auth_parameters)

        # Format Source
        source_path_str: str | None = PathHelper.path_to_str(path=source_path)

        #Validate Destination
        object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=destination_path)

        # do it!
        try:
            self.io_client.put_object(Bucket=settings.BUCKET, 
                                     Key=object_name, 
                                     Body=source_path_str) if self.io_client else None
            return True
        except S3Error as e:
            print(f"Error putting object from path: {e}")
            return False
        

    def _native_get_object_to_stream(self,
                   source_path: UPath, 
                   destination_stream: IO,
                   length:int,            
                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False
                   ) -> bool:

        object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=source_path)
        settings = get_settings(self.auth_parameters)


        try:
            response = self.io_client.get_object(Bucket=settings.BUCKET, Key=object_name)
            source_stream = io.BytesIO(response['Body'])
            
            self.copy_stream_to_stream(source_stream=source_stream, 
                                     destination_stream=destination_stream,
                                     encrypt=encrypt, 
                                     decrypt=decrypt, 
                                     compress=compress, 
                                     decompress=decompress)
            return True
        except S3Error as e:
            print(f"Error getting object to stream: {e}")
            return False
        

    def _native_get_object_to_path(self, 
                   source_path: UPath, 
                   destination_path: UPath,            
                    **kwargs
                   ) -> bool|Any:

        raise NotImplementedError()
        
        # self.check_kwargs_for_compression_encryption("_native_get_object_to_path", **kwargs)
        # settings = get_settings(self.auth_parameters)

        # str_destination_path: str | None = PathHelper.path_to_str(path=destination_path)
        
        # #Format S3 Source
        # object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=source_path)

        # # do it!
        # try:
        #     result = self.io_client.get_object(Bucket=settings.BUCKET, 
        #                                       Key=object_name, 
        #                                       Body=str_destination_path) if self.io_client else None

        #     #TODO: 
        #     # Write result['Body'] to the destination path
        #     FileWriter().


        #     return result
        # except S3Error as e:
        #     print(f"Error getting object to path: {e}") 
        #     return False




    #================================================================
    # Filesystem operations

    def _list_bucket_names(self) -> Optional[List]:

        if not self.io_client:
            return None

        try:
            buckets_raw = self.io_client.list_buckets()

            buckets = [bucket['Name'] for bucket in buckets_raw['Buckets']]  if buckets_raw is not None else None
            return buckets

        except S3Error as e:
            print(f'Failed to list buckets: {e}')
            return None


    def _bucket_exists(self, 
                      bucket_name: str) -> bool:

        if not self.io_client:
            return False 

        buckets = self._list_bucket_names()
        return bucket_name in buckets if buckets is not None else False



    def _find_objects(self, path: Union[str, UPath], maxkeys: Optional[int] = 999999) -> Optional[Iterator[Any]]:

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
                # We need to substring the path up to the position of the first wildcard for the prefix match
                prefix_relative_path = relative_path[:relative_path.index('*')]
            else:
                prefix_relative_path = relative_path

            try:
                objects = self.io_client.list_objects_v2(Bucket=settings.BUCKET, 
                                                        Prefix=prefix_relative_path,
                                                        MaxKeys=maxkeys
                                                        )      

                return objects if objects is not None and objects['KeyCount'] > 0 else None

            except S3Error as e:
                print(f"Error listing objects: {e}")
                return None


    def list_sources(self, path: Optional[Union[str, UPath]], **kwargs) -> Optional[List[UPath]]:
        """List available data sources in the specified path or directory."""

        u_path: UPath | None = PathHelper.format_path(path) 
        if not u_path:
            return []

        self.connect()

        if self.io_client:
            try:
                objects = self._find_objects(path=path)

                # return objects if objects is not None and objects['KeyCount'] > 0 else None

                return [UPath(obj['Key']) for obj in objects['Contents']] if objects is not None and objects['KeyCount'] > 0 else []

            except S3Error as e:
                print(f"Error listing sources: {e}")
                return []
            
    def get_size(self, path: Union[str, UPath]) -> int:
        """Get the size of the data at the specified path."""
        u_path: UPath | None = PathHelper.format_path(path=path) 
        if not u_path:
            return 0

        self.connect()
        if self.io_client:
            try:
                objects: Iterator[Any] | None = self._find_objects(path=u_path)

                object_sizes: list[int] = [obj['Size'] if obj else 0 for obj in objects['Contents']] if objects is not None and objects['KeyCount'] > 0 else []

                return sum(object_sizes)

            except S3Error as e:
                print(f"Error getting size: {e}")
                return 0
        return 0

    def get_file_raw_metadata(self, path: Union[str, UPath]) -> List[Dict]:

        """Get the file metadata of the data at the specified path."""
        u_path: UPath | None = PathHelper.format_path(path=path) 
        if not u_path:
            return []

        self.connect()

        if self.io_client:
            try:
                objects: Iterator[Any] | None = self._find_objects(path=u_path)

                object_metadata: list[Any] = [obj for obj in objects['Contents']] if objects is not None and objects['KeyCount'] > 0 else []

                return object_metadata

            except S3Error as e:
                print(f"Error getting object_metadata: {e}")
                return []

        return []

    def conform_file_metadata(self, raw_metadata: List[Dict]) -> List[FileMetadata]:
        """
        Transform raw S3 file metadata into a standardized format.
        
        Args:
            raw_metadata: List of raw metadata dictionaries from S3
            
        Returns:
            List of standardized metadata dictionaries
        """
        conformed_metadata = []
        
        for item in raw_metadata:
            # Extract the full path from the Key
            full_path = item.get('Key', '')
            
            # Extract filename and directory path
            filename = os.path.basename(full_path)
            directory = os.path.dirname(full_path)
            
            # Transform to standardized metadata format
            # Create a FileMetadata object
            conformed_item = FileMetadata(
                filename=filename,
                directory=directory,
                full_path=full_path,
                size=item.get('Size', 0),
                last_modified=item.get('LastModified'),
                etag=item.get('ETag', '').strip('"'),  # Remove quotes from ETag
                storage_class=item.get('StorageClass', ''),
                checksum=item.get('ChecksumAlgorithm', []),
                source='s3'
            )
            
            conformed_metadata.append(conformed_item)
            
        return conformed_metadata


    def get_file_metadata(self, path: Union[str, UPath]) -> List[FileMetadata]:
        """
        Get standardized file metadata for files at the specified path.
        
        Args:
            path: Path to the files
            
        Returns:
            List of standardized metadata dictionaries
        """
        # Get raw metadata
        raw_metadata = self.get_file_raw_metadata(path)
        
        # Transform to conformed metadata
        return self.conform_file_metadata(raw_metadata)

    def path_exists(self, path: Union[str, UPath]) -> bool:
        """Checks if the specified path exists."""
        u_path = PathHelper.format_path(path=path) 
        if not u_path:
            return False

        self.connect()

        try:
            objects: Iterator[Any] | None = self._find_objects(u_path, maxkeys = 1)

            if objects and objects['KeyCount'] > 0:
                return True

            # return False

            # relative_path: str | None = S3PathHelper.get_path_folders_and_filename(u_path)

            # if objects and relative_path:
            #     wildcard: bool = True if '*' in relative_path else False

            #     for obj in objects:
            #         obj_key = unquote(obj['Key'])

            #         if wildcard:
            #             if S3PathHelper.wildcard_match(pattern=relative_path, target_filename=obj_key):
            #                 return True
            #         else:
            #             if obj_key == relative_path:
            #                 return True

            return False
        except S3Error as e:
            print(f"Error checking path existence: {e}")
            return False

    def path_is_dir(self, path: Union[str, UPath]) -> bool:
        """Checks if the specified path is a directory."""
        # S3 doesn't have true directories, but we can check if there are objects with this prefix
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

            objects = self.io_client.list_objects_v2(Bucket=settings.BUCKET,
                                                Prefix=prefix)
            return any(objects)
        except S3Error as e:
            print(f"Error checking if path is directory: {e}")
            return False
    
    def path_is_file(self, path: Union[str, UPath]) -> bool:
        """Checks if the specified path is a file."""
        u_path: UPath | None = PathHelper.format_path(path) 

        settings = get_settings(self.auth_parameters)

        if not u_path:
            return False

        try:
            bucket_name = settings.BUCKET
            object_name = S3PathHelper.get_path_folders_and_filename(u_path)
            
            if not bucket_name or not object_name:
                return False

            # Try to get object stats - will raise exception if object doesn't exist
            self.io_client.stat_object(bucket_name, object_name)
            return True
        except S3Error:
            return False

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
        return False
