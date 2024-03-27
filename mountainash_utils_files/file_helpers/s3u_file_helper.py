from typing import Any, List, Optional

from minio import Minio
from minio.error import S3Error

from mountainash_settings import SettingsParameters
from .s3_file_helper import S3_FileHelper


class S3U_FileHelper(S3_FileHelper):

    def __init__(self, 
                 auth_parameters: SettingsParameters
                 ) -> None:
        
        super().__init__(auth_parameters)

        self.requires_io_connection = True
        self.requires_ssh_connection = False

        """Initialize the S3 object"""
        # self.hostname =     self.auth_settings.HOST
        # self.port =         self.auth_settings.PORT
        # self.username =     self.auth_settings.USERNAME
        # self.password =     self.auth_settings.PASSWORD
        # self.ssh_keypath =  self.auth_settings.KEY_PATH

        self.endpoint = f"{self.io_auth_settings.HOST}:{self.io_auth_settings.PORT}"
        self.access_key = self.io_auth_settings.USERNAME
        self.secret_key = self.io_auth_settings.PASSWORD
        self.access_token = self.io_auth_settings.TOKEN

        #S3 specific 
        self.bucket =     self.io_auth_settings.STORAGE_NAMESPACE
        self.service_name =     's3'

        if not self.io_auth_settings.STORAGE_NAMESPACE:
            raise ValueError(f"Invalid S3 bucket name: {self.io_auth_settings.STORAGE_NAMESPACE}")

        self.io_client: Optional[Any] = None
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


    #================================================================
    # Connection operations

    
    def connect(self) -> bool:
        """Connect to the S3 server using MinIO client."""

        connected = self.check_if_io_connected()
        
        if not connected:

            if self.io_client is not None:
                self.io_client = None

            try:
            
                # Create a MinIO client with the S3 endpoint, access key, and secret key.
                self.io_client = Minio(
                    endpoint=self.endpoint,
                    access_key=self.access_key,
                    secret_key=self.secret_key,
                    secure=False  # Use secure=True if you are connecting over HTTPS.
                )

                # Test the connection by listing buckets
                if self.check_if_io_connected():
                    print('Connection to Minio S3 successful.')
                    return True
                else:
                    print('Connection to Minio S3 failed.')
                    return False
            except (S3Error) as e:
                print(f'Error connecting to Minio S3: {e}')
                return False
        else:
            return True

    def check_if_io_connected(self) -> bool:
        """Check if connected to S3 by trying to list buckets."""
        
        if not self.io_client:
            return False

        try:
            
            buckets = self.io_client.list_buckets()
            # If we can list any bucket successfully, the connection is successful
            return any(buckets)
        except S3Error as e:
            print(f'Failed to list S3 buckets: {e}')
            return False

    def get_connection_client_parameters(self) -> dict:


        transport_params: dict[str, Minio | Any | None] = {
            'client':  self.io_client
        }

        return transport_params





    #================================================================
    # Stream operations
    # - Inherited from Base_FileHelper:
    # - open_read_binarystream
    # - open_write_binarystream
    # - open_read_textstream
    # - open_write_textstream

    # def open_read_binarystream(self, source_path: Optional[Union[str, UPath]], **kwargs) -> IO[Any]:
    #     """
    #     Read data from the specified source.
    #     """

    #     print(f"{self.storage_system}: open_read_binarystream: {source_path}")

    #     self.connect()

    #     mode = 'rb'
    #     return self._get_smartopen_stream_generator(path=source_path, mode=mode, transport_params=self.get_connection_client_parameters())
    

    # def open_write_binarystream(self, destination_path: Optional[Union[str, UPath]], **kwargs) -> IO[Any]:
    #     """
    #     Write data to the specified destination.
    #     """
    #     print(f"{self.storage_system}: open_write_binarystream: {destination_path}")

    #     self.connect()
    #     mode = 'wb'
    #     return self._get_smartopen_stream_generator(path=destination_path, mode=mode, transport_params=self.get_connection_client_parameters())

    # def open_read_textstream(self, source_path: Optional[Union[str, UPath]], **kwargs) -> IO[Any]:
    #     """
    #     Read data from the specified source.
    #     """
    #     print(f"{self.storage_system}: open_read_textstream: {source_path}")
        
    #     self.connect()
    #     mode = 'rb'
    #     return self._get_smartopen_stream_generator(path=source_path, mode=mode)#, transport_params=self.transport_params)
    

    # def open_write_textstream(self, destination_path: Optional[Union[str, UPath]], **kwargs) -> IO[Any]:
    #     """
    #     Write data to the specified destination.
    #     """
    #     print(f"{self.storage_system}: open_write_textstream: {destination_path}")

    #     self.connect()
    #     mode = 'wb'
    #     return self._get_smartopen_stream_generator(path=destination_path, mode=mode)#, transport_params=self.transport_params)


    #================================================================
    # File operations


    # def put_object_from_stream(self,
    #                destination_path: Optional[Union[str, UPath]], 
    #                source_stream: io.BytesIO, 
    #                length: int) -> bool|Any:

    #     self.connect()

    #     #Format S3 Destination
    #     u_destination_path: UPath | None = PathHelper.format_path(path=destination_path)
    #     bucket_name: str| None = S3PathHelper.get_path_bucketname(path=u_destination_path)
    #     object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=u_destination_path)

    #     if self.io_client and bucket_name and object_name:

    #         try:

    #             #MiniIO Client
    #             stream_data = source_stream.read(length)
    #             bytes_io_stream = io.BytesIO(stream_data)
    #             put_object: Any = self.io_client.put_object(bucket_name=bucket_name, object_name=object_name, data=bytes_io_stream, length=length)


    #             return put_object

    #         except Exception as e:
    #             raise ValueError(f"Error writing to stream: {e}")
    #     else:
    #         return False

    # def put_object_from_path(self, 
    #                destination_path: Optional[Union[str, UPath]], 
    #                source_path: Optional[Union[str, UPath]]
    #                ) -> bool:

    #     self.connect()

    #     #Format S3 Destination
    #     u_destination_path = PathHelper.format_path(path=destination_path)
    #     bucket_name: str| None = S3PathHelper.get_path_bucketname(path=u_destination_path)
    #     object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=u_destination_path)

    #     #Format Source
    #     u_source_path: UPath | None = PathHelper.format_path(path=source_path)
    #     source_path_str: str | None = PathHelper.path_to_str(path=u_source_path)

    #     #Validate Destintion
    #     bucket_exists: bool = self._bucket_exists(bucket_name=bucket_name)
    #     if not bucket_exists:
    #         return False

    #     #Validate source
    #     if not u_source_path:
    #         return False

    #     # source_exists = FileHelperFacade.path_exists(path=u_source_path)

    #     #Do it!
    #     if self.io_client and bucket_name and bucket_exists and object_name and source_path_str:

    #         try:
    #             #MiniIO Client
    #             self.io_client.fput_object(bucket_name=bucket_name, object_name=object_name, file_path=source_path_str)
                
    #             return True

    #         except Exception as e:
    #             raise ValueError(f"Error writing to stream: {e}")
    #     else:
    #         return False


    # def get_object_to_stream(self,
    #                source_path: Optional[Union[str, UPath]], 
    #                destination_stream: io.BytesIO) -> bool:

    #     self.connect()

    #     #Format S3 Source
    #     u_source_path = PathHelper.format_path(path=source_path)
    #     bucket_name: str| None = S3PathHelper.get_path_bucketname(path=u_source_path)
    #     object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=u_source_path)

    #     #Validate source
    #     if not u_source_path:
    #         return False

    #     source_exists = self.path_exists(path=u_source_path)

    #     if not source_exists:
    #         print(f"get_object_to_stream(): Source does not exist: {u_source_path}")
    #         return False

    #     #Do it!        
    #     if self.io_client and bucket_name and object_name:

    #         try:

    #             # get_obj = self.io_client.get_object(bucket_name=bucket_name, object_name=object_name, length=self.get_size(path=u_source_path))

    #             #MiniIO Client
    #             source_stream = self.open_read_binarystream(source_path=source_path)
    #             source_file_size = self.get_size(path=u_source_path)

    #             stream_data = source_stream.read(source_file_size)
    #             bytes_io_stream = io.BytesIO(stream_data)

    #             # with self.open_read_binarystream(source_path=source_path) as source_stream:

    #             #     stream_data = source_stream.read()
    #             #     bytes_io_stream = io.BytesIO(stream_data)

    #             destination_stream.write(bytes_io_stream)
                
    #             return True

    #         except Exception as e:
    #             raise ValueError(f"Error writing to stream: {e}")
    #     else:
    #         return False

    # def get_object_to_path(self, 
    #                source_path: Optional[Union[str, UPath]], 
    #                destination_path: Optional[Union[str, UPath]]
    #                ) -> bool|Any:

    #     self.connect()

    #     #Format Destination
    #     u_destination_path: UPath | None = PathHelper.format_path(path=destination_path)
    #     destination_path_str: str | None = PathHelper.path_to_str(path=u_destination_path)

    #     #Format S3 Source
    #     u_source_path: str | None = PathHelper.path_to_str(path=source_path)
    #     bucket_name: str| None = S3PathHelper.get_path_bucketname(path=u_source_path)
    #     object_name: str | None = S3PathHelper.get_path_folders_and_filename(path=u_source_path)

    #     #Validate source        
    #     if not u_source_path:
    #         return False

    #     source_exists = self.path_exists(path=u_source_path)

    #     if not source_exists:
    #         print(f"get_object_to_path(): Source does not exist: {u_source_path}")
    #         return False


    #     if self.io_client and bucket_name and object_name and destination_path_str:

    #         try:

    #             #MiniIO Client
    #             fget:  Any = self.io_client.fget_object(bucket_name=bucket_name, object_name=object_name, file_path=destination_path_str)

    #             return fget

    #         except Exception as e:
    #             raise ValueError(f"Error writing to path: {e}")
    #     else:
    #         return False




    # # def read_from_binarystream(self, source_path: Union[UPath,str], destination_stream: Any, **kwargs) -> bool:
    # #     self.connect()
    # #     return True

    # # def write_to_binarystream(self, destination_path: Union[UPath,str], source_stream: Any, **kwargs) -> bool:
    # #     self.connect()
    # #     return True

    # # def read_from_binarystream(self, source_path: Union[UPath,str], destination_stream: Any, **kwargs) -> bool:

    # #     source_bucket: str | None = S3PathHelper.get_path_bucketname(source_path)
    # #     source_folders_and_filename: str | None = S3PathHelper.get_path_folders_and_filename(source_path)

    # #     if not source_bucket or not source_folders_and_filename:            
    # #         raise ValueError(f"Invalid source path: {source_path}")
        
    # #     self.connect()

    # #     if self.io_client:            
    # #         try:
    # #             self.io_client.fget_object(bucket_name=source_bucket, object_name=source_folders_and_filename, file_path=destination_stream)

    # #         except Exception as e:
    # #             raise ValueError(f"Error writing to stream: {e}")
        
    # #     return True



    # # def write_to_binarystream(self, destination_path: Union[UPath,str], source_stream: Any, **kwargs) -> bool:

    # #     destination_path_str = self.format_path_as_string(path=destination_path)

    # #     destination_bucket: str | None = S3PathHelper.get_path_bucketname(destination_path)
    # #     destination_folders_and_filename: str | None = S3PathHelper.get_path_folders_and_filename(destination_path)

    # #     self.connect()

    # #     if not destination_bucket or not destination_folders_and_filename:
    # #         raise ValueError(f"Invalid destination path: {destination_path_str}")
            
    # #     if self.io_client:
    # #         try:
    # #             self.io_client.put_object(destination_bucket, destination_folders_and_filename, data=source_stream, length=-1)
    # #         except Exception as e:
    # #             raise ValueError(f"Error writing to stream: {e}")
        
    # #     return True


    # # @classmethod
    # # def read_data(cls, source_path: Union[str, UPath], **kwargs) -> Any:
    # #     """
    # #     Read data from the specified source.
    # #     """
    # #     mode = kwargs.get('mode', 'r')  # Default mode is text; use 'rb' for binary
    # #     with open(source_path, mode) as file:
    # #         return file.read()

    # # @classmethod
    # # def write_data(cls, destination_path: Union[str, UPath], data: Any, **kwargs):
    # #     """
    # #     Write data to the specified destination.
    # #     """
    # #     mode = kwargs.get('mode', 'w')  # Default mode is text; use 'wb' for binary
    # #     with open(destination_path, mode) as file:
    # #         file.write(data)

    # # @classmethod
    # # def copy_to(cls, destination_path: Union[str, UPath], source_file: IO):
    # #     pass

    # # @classmethod
    # # def copy_from(cls, source_path: Union[str, UPath]) -> IO:
    # #     pass

    # #================================================================
    # # Filesystem operations

    # def _bucket_exists(self, 
    #                   bucket_name: Optional[str]=None, 
    #                   path: Optional[Union[str, UPath]]=None) -> bool:

    #     if not self.io_client:
    #         return False

    #     if bucket_name:
    #         u_bucket_name = bucket_name
    #     elif path:
    #         u_path = S3PathHelper.format_path(path)
    #         u_bucket_name = S3PathHelper.get_path_bucketname(u_path)


    #     try:

    #         #MiniIO Client
    #         buckets = self.io_client.list_buckets()
    #         # If we can list any bucket successfully, the connection is successful

    #         return  u_bucket_name in buckets
    #     except S3Error as e:
    #         print(f'Failed to list S3 buckets: {e}')
    #         return False



    # def _find_objects(self, path: Union[str, UPath]) -> Optional[Iterator[Any]]:


    #     u_path = PathHelper.format_path(path) 
    #     if not u_path:
    #         return None
        
    #     self.connect()

    #     if self.io_client:

    #         bucket_name: str | None = S3PathHelper.get_path_bucketname(u_path)
    #         if not bucket_name:
    #             return None
            
    #         relative_path: str | None = S3PathHelper.get_path_folders_and_filename(u_path)

    #         if not relative_path:
    #             return None

    #         wildcard: bool = True if '*' in relative_path else False

    #         if wildcard:
    #             # We need to substring the path up to the position of the first wildcard
    #             prefix_relative_path = relative_path[:relative_path.index('*')]
    #         else:
    #             prefix_relative_path = relative_path

    #         objects: Iterator[Any] = self.io_client.list_objects(bucket_name=bucket_name, prefix=prefix_relative_path, recursive=True)

    #         return objects


    # def list_sources(self, path: Optional[Union[str, UPath]], **kwargs) -> Optional[List[str|None]]:
    #     """
    #     List available data sources in the specified path or directory.
    #     """
    #     u_path: UPath | None = PathHelper.format_path(path) 
    #     if not u_path:
    #         return []
                
    #     self.connect()
    #     if self.io_client:
    #         return [obj.object_name for obj in self.io_client.list_objects(bucket_name=u_path.root, prefix=u_path.path, recursive=True)]
            
    # @classmethod
    # def calculate_checksum(cls, path: Union[str, UPath], algorithm: str = 'sha256') -> None:
    #     """
    #     Calculate the checksum of the data at the specified path.
    #     """
    #     pass
    #     # hash_alg = hashlib.new(algorithm)
    #     # with open(path, 'rb') as file:
    #     #     for chunk in iter(lambda: file.read(4096), b""):
    #     #         hash_alg.update(chunk)
    #     # return hash_alg.hexdigest()




    # def get_size(self, path: Union[str, UPath]) -> int:
    #     """
    #     Get the size of the data at the specified path.
    #     """

    #     u_path: UPath | None = PathHelper.format_path(path=path) 

    #     if not u_path:
    #         return 0

    #     self.connect()
    #     if self.io_client:

    #         objects: Iterator[Any] | None = self._find_objects(path=u_path)
            
    #         object_sizes: list[int] = [ obj.size if obj else 0 for obj in objects ] if objects else []

    #         return sum( object_sizes )
        
    #     return 0


        

    # def path_exists(self,  path: Union[str, UPath]) -> bool:
    #     """
    #     Checks if the specified path exists.

    #     :param path: The path to check.
    #     :return: True if the path exists, False otherwise.
    #     """


    #     u_path = PathHelper.format_path(path=path) 
    #     if not u_path:
    #         return False
        

    #     self.connect()

    #     objects: Iterator[Any] | None = self._find_objects(path)
    #     relative_path: str | None = S3PathHelper.get_path_folders_and_filename(u_path)

    #     if objects and relative_path:

    #         wildcard: bool = True if '*' in relative_path else False

    #         for obj in objects:
    #             # Extract object key and ensure it's unquoted for comparison
    #             obj_key = unquote(obj.object_name if hasattr(obj, 'object_name') else obj.key)

    #             if wildcard:
    #                 # Use regex match for wildcard patterns
    #                 return S3PathHelper.wildcard_match(pattern=relative_path, target_filename=obj_key)
    #             else:
    #                 # Direct comparison for exact matches
    #                 if obj_key == relative_path:
    #                     return True

    #     return False



    # def path_is_dir(self,  path: Union[str, UPath]) -> bool:
    #     """
    #     Checks if the specified path exists.

    #     :param path: The path to check.
    #     :return: True if the path exists, False otherwise.
    #     """
    #     return False
    
    # def path_is_file(self,  path: Union[str, UPath]) -> bool:
    #     """
    #     Checks if the specified path exists.

    #     :param path: The path to check.
    #     :return: True if the path exists, False otherwise.
    #     """

    #     u_path: UPath | None = PathHelper.format_path(path) 
    #     if not u_path:
    #         return False

    #     return self.path_exists(path)        

    # @classmethod
    # def create_directory(
    #     cls, 
    #     path: Union[str, UPath]
    #     ) -> bool:
    #     """Creates a directory if it does not exist.

    #     Args:
    #         directory: The path of the directory to create.

    #     Returns:
    #         True if the directory was created or already exists, False otherwise.

    #     Example:
    #         fs = FilesystemInterface('local')
    #         created = fs.create_directory('data')
    #     """
    #     return False
