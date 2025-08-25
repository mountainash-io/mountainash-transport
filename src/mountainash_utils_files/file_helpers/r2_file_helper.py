from typing import List, Union, IO, Optional, Dict, BinaryIO, TextIO
from upath import UPath
import io
import os

from .base_file_helper import Base_FileHelper
from mountainash_utils_files.path_helpers import PathHelper
from mountainash_utils_files.path_helpers import S3PathHelper  # We can reuse S3PathHelper since R2 uses the same format
from mountainash_settings import SettingsParameters
from ..settings.providers.r2 import R2StorageAuthSettings
from ..constants import CONST_STORAGE_PROVIDER_TYPE
from ..dataclasses import FileMetadata

from minio import Minio
from minio.error import MinioException

class R2_FileHelper(Base_FileHelper):
    """
    Cloudflare R2 File Helper implementation using Minio client.

    R2 is S3-compatible, so we can inherit much of the functionality from Base_FileHelper
    but implement it specifically for R2.
    """

    def __init__(self,
                 auth_parameters: SettingsParameters
                 ) -> None:

        super().__init__()

        self.auth_parameters = auth_parameters
        self.auth_settings: R2StorageAuthSettings = R2StorageAuthSettings.get_settings(auth_parameters)
        self.storage_provider_type = CONST_STORAGE_PROVIDER_TYPE.R2
        self.storage_system = "R2"

        self.requires_io_connection = True
        self.requires_ssh_connection = False

        self.set_interface_attributes()

        # Initialize client as None
        self.io_client = None
        self.connect()

    def set_interface_attributes(self) -> None:
        """Set the interface attributes for R2 storage."""
        # Attributes for native operations
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

        # Smart open support - explicitly set all to False as R2 is not compatible with smart_open
        self.supports_smartopen_read_stream = False
        self.supports_encrypt_smartopen_read_stream = False
        self.supports_decrypt_smartopen_read_stream = False
        self.supports_compress_smartopen_read_stream = False
        self.supports_decompress_smartopen_read_stream = False

        self.supports_smartopen_write_stream = False
        self.supports_encrypt_smartopen_write_stream = False
        self.supports_decrypt_smartopen_write_stream = False
        self.supports_compress_smartopen_write_stream = False
        self.supports_decompress_smartopen_write_stream = False

        # General support flags
        self.supports_get_to_stream = True
        self.supports_get_to_path = True
        self.supports_put_from_stream = True
        self.supports_put_from_path = True

        # Preferences
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
                # Configure Minio client for R2
                self.io_client = Minio(
                    endpoint=self.auth_settings.ENDPOINT,
                    access_key=self.auth_settings.ACCESS_KEY_ID,
                    secret_key=self.auth_settings.SECRET_ACCESS_KEY.get_secret_value(),
                    secure=self.auth_settings.USE_SSL,
                    region='auto'  # R2 uses auto region
                )

                # Test the connection
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
            # # List buckets to check connection
            # buckets = self.io_client.list_buckets()
            # return len(buckets) > 0

            # settings = get_settings(self.auth_parameters)
            # List objects with a prefix to check connection
            objects = self.io_client.list_objects(self.auth_settings.BUCKET, prefix="", recursive=False)
            # If we can list objects successfully, the connection is working
            return any(objects)


        except MinioException as e:
            print(f'Failed to check R2 connection: {e}')
            return False

    def get_connection_client_parameters(self) -> dict:
        """Get connection parameters for R2."""

        # Note: This method is primarily used for smart_open which is not compatible with R2
        # We still implement it for consistency, but it won't be used for actual streaming operations
        transport_params = {
            'client': self.io_client
        }
        return transport_params

    #================================================================
    # Native File operations implementation

    def _native_put_object_from_stream(self,
                   destination_path: UPath,
                   source_stream: IO,
                   length: int,
                   encrypt: Optional[bool] = False,
                   decrypt: Optional[bool] = False,
                   compress: Optional[bool] = False,
                   decompress: Optional[bool] = False
                   ) -> bool:
        """Put an object to R2 from a stream."""

        #Validate Destination
        bucket_name: str | None = S3PathHelper.get_path_bucketname(path=destination_path)
        object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=destination_path)

        if not bucket_name or not object_name:
            print(f"Invalid path: {destination_path}")
            return False

        bucket_exists: bool = self._bucket_exists(bucket_name=bucket_name)
        if not bucket_exists:
            print(f"Bucket does not exist: {bucket_name}")
            return False

        #Process source stream
        processed_source_stream: io.BytesIO = self.process_source_stream(source_stream=source_stream,
                                                                       encrypt=encrypt,
                                                                       decrypt=decrypt,
                                                                       compress=compress,
                                                                       decompress=decompress)

        # do it!
        try:
            self.io_client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=processed_source_stream,
                length=length
            )
            return True
        except MinioException as e:
            print(f"Error putting object to R2: {e}")
            return False

    def _native_put_object_from_path(self,
                   destination_path: UPath,
                   source_path: UPath,
                   encrypt: Optional[bool] = False,
                   decrypt: Optional[bool] = False,
                   compress: Optional[bool] = False,
                   decompress: Optional[bool] = False
                   ) -> bool:
        """Put an object to R2 from a local path."""

        self.check_kwargs_for_compression_encryption("_native_put_object_from_path",
                                                    encrypt=encrypt,
                                                    decrypt=decrypt,
                                                    compress=compress,
                                                    decompress=decompress)

        # Format Source
        source_path_str: str | None = PathHelper.path_to_str(path=source_path)
        if not source_path_str:
            print(f"Invalid source path: {source_path}")
            return False

        #Validate Destination
        bucket_name: str | None = S3PathHelper.get_path_bucketname(path=destination_path)
        object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=destination_path)

        if not bucket_name or not object_name:
            print(f"Invalid destination path: {destination_path}")
            return False

        bucket_exists: bool = self._bucket_exists(bucket_name=bucket_name)
        if not bucket_exists:
            print(f"Bucket does not exist: {bucket_name}")
            return False

        # do it!
        try:
            self.io_client.fput_object(
                bucket_name=bucket_name,
                object_name=object_name,
                file_path=source_path_str
            )
            return True
        except MinioException as e:
            print(f"Error putting object from path to R2: {e}")
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
        """Get an object from R2 to a stream."""

        #Validate Source
        bucket_name: str | None = S3PathHelper.get_path_bucketname(path=source_path)
        object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=source_path)

        if not bucket_name or not object_name:
            print(f"Invalid source path: {source_path}")
            return False

        # do it!
        try:
            response = self.io_client.get_object(
                bucket_name=bucket_name,
                object_name=object_name
            )

            # Create a BytesIO object from the response data
            source_stream = io.BytesIO()

            # Read the data from response in chunks
            for data in response.stream(32*1024):
                source_stream.write(data)

            # Reset stream position
            source_stream.seek(0)

            # Process and copy to destination stream
            self.copy_stream_to_stream(
                source_stream=source_stream,
                destination_stream=destination_stream,
                encrypt=encrypt,
                decrypt=decrypt,
                compress=compress,
                decompress=decompress
            )

            # Close the response to release resources
            response.close()
            response.release_conn()

            return True
        except MinioException as e:
            print(f"Error getting object from R2 to stream: {e}")
            return False

    def _native_get_object_to_path(self,
                   source_path: UPath,
                   destination_path: UPath,
                   encrypt: Optional[bool] = False,
                   decrypt: Optional[bool] = False,
                   compress: Optional[bool] = False,
                   decompress: Optional[bool] = False
                   ) -> bool:
        """Get an object from R2 to a local path."""

        self.check_kwargs_for_compression_encryption("_native_get_object_to_path",
                                                   encrypt=encrypt,
                                                   decrypt=decrypt,
                                                   compress=compress,
                                                   decompress=decompress)

        # Format Destination
        dest_path_str: str | None = PathHelper.path_to_str(path=destination_path)
        if not dest_path_str:
            print(f"Invalid destination path: {destination_path}")
            return False

        # Ensure parent directory exists
        parent_dir = os.path.dirname(dest_path_str)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        #Validate Source
        bucket_name: str | None = S3PathHelper.get_path_bucketname(path=source_path)
        object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=source_path)

        if not bucket_name or not object_name:
            print(f"Invalid source path: {source_path}")
            return False

        # do it!
        try:
            self.io_client.fget_object(
                bucket_name=bucket_name,
                object_name=object_name,
                file_path=dest_path_str
            )
            return True
        except MinioException as e:
            print(f"Error getting object from R2 to path: {e}")
            return False

    #================================================================
    # Stream operations - Override base class methods since smart_open is not compatible with R2

    def open_read_binarystream(self,
                               source_path: Optional[Union[str, UPath]],
                               **kwargs) -> IO|BinaryIO:
        """
        Read binary data from R2 using Minio client directly instead of smart_open.
        This overrides the base class method to provide R2-specific implementation.
        """
        self.connect()

        u_path = PathHelper.format_path(path=source_path)
        if not u_path:
            raise ValueError(f"Invalid path: {source_path}")

        bucket_name = S3PathHelper.get_path_bucketname(u_path)
        object_name = S3PathHelper.get_path_folders_and_filename(u_path)

        if not bucket_name or not object_name:
            raise ValueError(f"Invalid R2 path: {source_path}")

        try:
            # Get the object from R2
            response = self.io_client.get_object(bucket_name, object_name)

            # Create a BytesIO buffer to store the data
            buffer = io.BytesIO()

            # Read data from response in chunks and write to buffer
            for data in response.stream(32*1024):
                buffer.write(data)

            # Reset buffer position to beginning for reading
            buffer.seek(0)

            # Properly close the response to avoid resource leaks
            response.close()
            response.release_conn()

            return buffer
        except MinioException as e:
            raise IOError(f"Error reading from R2: {e}")

    def open_write_binarystream(self,
                                destination_path: Optional[Union[str, UPath]],
                                encrypt_stream: bool = False,
                                decrypt_stream: bool = False,
                                **kwargs) -> IO|BinaryIO:
        """
        Create a binary stream for writing to R2.

        Since we can't directly stream to R2 like with S3/smart_open, we return a BytesIO buffer
        that will be uploaded to R2 when closed or when put_object_from_stream is called.
        """
        self.connect()

        # Create a write buffer that will collect data to be uploaded later
        buffer = io.BytesIO()

        # Store the destination path in the buffer object for later use
        buffer.r2_destination_path = destination_path

        # Create a custom close method that uploads the data to R2
        original_close = buffer.close

        def custom_close():
            if not buffer.closed:
                # Save current position
                pos = buffer.tell()
                buffer.seek(0)

                # Get path info
                # u_path = PathHelper.format_path(path=destination_path)
                # bucket_name = S3PathHelper.get_path_bucketname(u_path)
                # object_name = S3PathHelper.get_path_folders_and_filename(u_path)

                # Upload to R2
                try:
                    self.put_object_from_stream(
                        destination_path=destination_path,
                        source_stream=buffer,
                        encrypt=encrypt_stream,
                        decrypt=decrypt_stream
                    )
                except Exception as e:
                    print(f"Error uploading to R2 during stream close: {e}")

                # Reset position
                buffer.seek(pos)

                # Call original close
                original_close()

        # Replace close method with our custom one
        buffer.close = custom_close

        return buffer

    def open_read_textstream(self,
                            source_path: Optional[Union[str, UPath]],
                            **kwargs) -> IO|TextIO:
        """
        Read text data from R2 using Minio client directly instead of smart_open.
        This overrides the base class method to provide R2-specific implementation.
        """
        binary_stream = self.open_read_binarystream(source_path, **kwargs)

        # Convert binary content to text based on encoding
        encoding = kwargs.get('encoding', 'utf-8')
        text_content = binary_stream.read().decode(encoding)

        # Create a StringIO object with the decoded content
        text_stream = io.StringIO(text_content)
        return text_stream

    def open_write_textstream(self,
                             destination_path: Optional[Union[str, UPath]],
                             **kwargs) -> IO|TextIO:
        """
        Create a text stream for writing to R2.

        Similar to the binary version, but handles text encoding.
        """
        # Create a StringIO buffer for text
        buffer = io.StringIO()

        # Store the destination path and encoding in the buffer object for later use
        buffer.r2_destination_path = destination_path
        buffer.r2_encoding = kwargs.get('encoding', 'utf-8')

        # Create a custom close method that uploads the data to R2
        original_close = buffer.close

        def custom_close():
            if not buffer.closed:
                # Get the text content
                text_content = buffer.getvalue()

                # Convert to binary with the specified encoding
                binary_data = text_content.encode(buffer.r2_encoding)
                binary_stream = io.BytesIO(binary_data)

                # Upload to R2
                try:
                    self.put_object_from_stream(
                        destination_path=destination_path,
                        source_stream=binary_stream
                    )
                except Exception as e:
                    print(f"Error uploading to R2 during text stream close: {e}")

                # Call original close
                original_close()

        # Replace close method with our custom one
        buffer.close = custom_close

        return buffer

    #================================================================
    # Helper methods for R2 operations

    def _list_bucket_names(self) -> Optional[List[str]]:
        """List all bucket names in R2."""

        if not self.io_client:
            return None

        try:
            buckets = self.io_client.list_buckets()
            return [bucket.name for bucket in buckets]
        except MinioException as e:
            print(f'Failed to list R2 buckets: {e}')
            return None

    def _bucket_exists(self, bucket_name: str) -> bool:
        """Check if a bucket exists in R2."""

        if not self.io_client:
            return False

        try:
            return self.io_client.bucket_exists(bucket_name)
        except MinioException as e:
            print(f'Error checking if bucket exists: {e}')
            return False

    def _find_objects(self, path: Union[str, UPath]) -> Optional[List[Dict]]:
        """Find objects in R2 matching the given path pattern."""

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
                objects = self.io_client.list_objects(
                    bucket_name=bucket_name,
                    prefix=prefix_relative_path,
                    recursive=True
                )

                # Convert generator to a list for easier manipulation
                result = []
                for obj in objects:
                    # Create a dictionary similar to S3 response format
                    obj_dict = {
                        'Key': obj.object_name,
                        'LastModified': obj.last_modified,
                        'ETag': obj.etag,
                        'Size': obj.size,
                        'StorageClass': 'STANDARD'  # R2 doesn't have this concept in the same way
                    }
                    result.append(obj_dict)

                return result
            except MinioException as e:
                print(f"Error listing objects: {e}")
                return None
        return None

    #================================================================
    # Filesystem operations implementation

    def list_sources(self, path: Optional[Union[str, UPath]], **kwargs) -> List[UPath]:
        """List available data sources in the specified path or directory."""

        u_path: UPath | None = PathHelper.format_path(path)
        if not u_path:
            return []

        self.connect()

        if self.io_client:
            try:
                objects = self._find_objects(path=path)

                if not objects:
                    return []

                return [UPath(obj['Key']) for obj in objects]
            except Exception as e:
                print(f"Error listing sources: {e}")
                return []
        return []

    def path_exists(self, path: Union[str, UPath], **kwargs) -> bool:
        """Check if the specified data source exists."""

        u_path = PathHelper.format_path(path=path)
        if not u_path:
            return False

        self.connect()

        try:
            bucket_name: str | None = S3PathHelper.get_path_bucketname(u_path)
            object_name: str | None = S3PathHelper.get_path_folders_and_filename(u_path)

            if not bucket_name or not object_name:
                return False

            # Check if bucket exists first
            if not self._bucket_exists(bucket_name):
                return False

            # For directories (prefixes), we need to check if objects exist with this prefix
            if object_name.endswith('/'):
                objects = self.io_client.list_objects(
                    bucket_name=bucket_name,
                    prefix=object_name,
                    recursive=False
                )
                return any(objects)

            # For files, use stat_object to check existence
            try:
                self.io_client.stat_object(bucket_name, object_name)
                return True
            except MinioException:
                # If we can't stat the object, it might not exist or there might be another issue
                # Let's try to list objects with this prefix to be sure
                objects = self._find_objects(path)
                return objects is not None and len(objects) > 0

        except MinioException as e:
            print(f"Error checking path existence: {e}")
            return False

    def get_size(self, path: Optional[Union[str, UPath]]) -> int:
        """Get the size of the data at the specified path."""

        u_path: UPath | None = PathHelper.format_path(path=path)
        if not u_path:
            return 0

        self.connect()

        if self.io_client:
            try:
                bucket_name: str | None = S3PathHelper.get_path_bucketname(u_path)
                object_name: str | None = S3PathHelper.get_path_folders_and_filename(u_path)

                if not bucket_name or not object_name:
                    return 0

                # If it's a specific object, get its size directly
                if not object_name.endswith('/') and '*' not in object_name:
                    try:
                        obj_stat = self.io_client.stat_object(bucket_name, object_name)
                        return obj_stat.size
                    except MinioException:
                        # If we can't stat the object, it might be a prefix
                        pass

                # Otherwise, sum up sizes of all matching objects
                objects = self._find_objects(u_path)
                if not objects:
                    return 0

                return sum(obj['Size'] for obj in objects)

            except MinioException as e:
                print(f"Error getting size: {e}")
                return 0
        return 0

    def get_file_raw_metadata(self, path: Union[str, UPath]) -> List[Dict]:
        """Get the file metadata of the data at the specified path."""

        objects = self._find_objects(path)
        return objects if objects else []

    def conform_file_metadata(self, raw_metadata: List[Dict]) -> List[FileMetadata]:
        """Transform raw R2 file metadata into a standardized format."""

        conformed_metadata = []

        for item in raw_metadata:
            # Extract the full path from the Key
            full_path = item.get('Key', '')

            # Extract filename and directory path
            filename = os.path.basename(full_path)
            directory = os.path.dirname(full_path)

            # Create a FileMetadata object
            conformed_item = FileMetadata(
                filename=filename,
                directory=directory,
                full_path=full_path,
                size=item.get('Size', 0),
                last_modified=item.get('LastModified'),
                etag=item.get('ETag', '').strip('"'),  # Remove quotes from ETag
                storage_class=item.get('StorageClass', ''),
                checksum=[],  # R2 doesn't provide checksum in the same way
                source='r2'
            )

            conformed_metadata.append(conformed_item)

        return conformed_metadata

    def get_file_metadata(self, path: Union[str, UPath]) -> List[FileMetadata]:
        """Get standardized file metadata for files at the specified path."""

        # Get raw metadata
        raw_metadata = self.get_file_raw_metadata(path)

        # Transform to conformed metadata
        return self.conform_file_metadata(raw_metadata)

    def path_is_dir(self, path: Union[str, UPath]) -> bool:
        """Check if the specified path is a directory (prefix in R2)."""

        u_path = PathHelper.format_path(path=path)
        if not u_path:
            return False

        try:
            bucket_name: str | None = S3PathHelper.get_path_bucketname(u_path)
            prefix: str | None = S3PathHelper.get_path_folders_and_filename(u_path)

            if not bucket_name or not prefix:
                return False

            # Ensure prefix ends with '/'
            if not prefix.endswith('/'):
                prefix += '/'

            # Check if objects exist with this prefix
            objects = self.io_client.list_objects(
                bucket_name=bucket_name,
                prefix=prefix,
                recursive=False
            )

            return any(objects)
        except MinioException as e:
            print(f"Error checking if path is directory: {e}")
            return False

    def path_is_file(self, path: Union[str, UPath]) -> bool:
        """Check if the specified path is a file (object in R2)."""

        u_path: UPath | None = PathHelper.format_path(path)
        if not u_path:
            return False

        try:
            bucket_name: str | None = S3PathHelper.get_path_bucketname(u_path)
            object_name: str | None = S3PathHelper.get_path_folders_and_filename(u_path)

            if not bucket_name or not object_name:
                return False

            # Try to get object stats - will raise exception if object doesn't exist
            self.io_client.stat_object(bucket_name, object_name)
            return True
        except MinioException:
            return False

    def create_directory(self, path: Optional[Union[str, UPath]]) -> bool:
        """Create a directory (prefix) in R2."""

        u_path: UPath | None = PathHelper.format_path(path)
        if not u_path:
            return False

        try:
            bucket_name: str | None = S3PathHelper.get_path_bucketname(u_path)
            prefix: str | None = S3PathHelper.get_path_folders_and_filename(u_path)

            if not bucket_name or not prefix:
                return False

            # Ensure the prefix ends with a slash
            if not prefix.endswith('/'):
                prefix += '/'

            # In R2 (like S3), directories are just prefixes, created by adding an empty object with that prefix
            self.io_client.put_object(
                bucket_name=bucket_name,
                object_name=prefix,
                data=io.BytesIO(b''),
                length=0
            )

            return True
        except MinioException as e:
            print(f"Error creating directory: {e}")
            return False
