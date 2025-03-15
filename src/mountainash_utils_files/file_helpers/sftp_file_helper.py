import os
import io
from typing import Any, List, Union, IO, Optional

from upath import UPath
from paramiko import SFTPClient, SSHClient,  SFTPAttributes

from mountainash_utils_files.path_helpers import PathHelper
from mountainash_settings import SettingsParameters

from .base_file_helper import Base_FileHelper

# from mountainash_acdrs.utils.data_storage.data_storage_functions import get_data_storage_factory, get_data_storage_object



class SFTP_FileHelper(Base_FileHelper):

    io_client:   Optional[SFTPClient] 
    ssh_client:  Optional[SSHClient]

    def __init__(self, 
                 auth_parameters: SettingsParameters
                 ) -> None:

        super().__init__(auth_parameters)

        self.requires_io_connection = True
        self.requires_ssh_connection = True

        """Initialize the SFTPManager object"""
        self.ssh_hostname =         self.io_auth_settings.HOST
        self.ssh_port =             self.io_auth_settings.PORT
        self.ssh_username =         self.io_auth_settings.USERNAME
        self.ssh_password =         self.io_auth_settings.PASSWORD
        self.ssh_keypath =          self.io_auth_settings.SSH_KEY_PATH
        self.ssh_fwd_remoteport =   self.io_auth_settings.SSH_FWD_REMOTEPORT
        self.ssh_fwd_localport =    self.io_auth_settings.SSH_FWD_LOCALPORT

        self.io_client = None
        self.ssh_client = None 

        self.connect()

        self.set_interface_attributes()


    def set_interface_attributes(self) -> None:
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

        self.supports_directories = True



    def connect(self) -> bool:
        """Connect to the SFTP server"""

        connected: bool = self.check_if_io_connected()
        
        if not connected:

            if self.ssh_client is not None:
                self.ssh_client.close()

            self.connect_ssh()

            # self.ssh_client = SSHClient()
            # self.ssh_client.set_missing_host_key_policy(AutoAddPolicy())

            # #TODO: Validate that the keypath exists

            # if self.ssh_keypath is not None:
            #     u_ssh_keypath: UPath | None = PathHelper.format_path(self.ssh_keypath)
            #     ssh_keypath_str: str | None = PathHelper.path_to_str(u_ssh_keypath)

            #     self.ssh_client.connect(hostname=self.hostname, port=self.port, username=self.username, password=self.password, key_filename=ssh_keypath_str)
            # else:
            #     self.ssh_client.connect(hostname=self.hostname, port=self.port, username=self.username, password=self.password)
                
            self.io_client = self.ssh_client.open_sftp() if self.ssh_client else None

            print(f'Connecting to SFTP: {self.ssh_hostname}')

            connected = self.check_if_io_connected()

            if not connected:
                print(f'Connection Failed: {self.ssh_hostname}')
            else:
                print(f'Connection Successful: {self.ssh_hostname}')

        return connected

    def check_if_io_connected(self):
        """Check if the SFTP server is connected"""

        connected = True

        if not self.io_client:
            connected = False
        else:
            try:
                self.io_client.listdir(path="/")
            except OSError:
                connected =  False
            
        return connected


    def get_connection_client_parameters(self) -> dict:
        return {}


    # def read_from_binarystream(self, source_path: Union[UPath,str], destination_stream: Any, **kwargs) -> bool:

    #     source_path_str = self.format_path_as_string(path=source_path)
    #     if not source_path_str:
    #         raise ValueError(f"Invalid source path: {source_path_str}")
    #     try:
    #         self.io_client.getfo(source_path_str, destination_stream, prefetch=True)
    #     except Exception as e:
    #         raise ValueError(f"Error writing to stream: {e}")
        
    #     return True



    # def write_to_binarystream(self, destination_path: Union[UPath,str], source_stream: Any, **kwargs) -> bool:
    #     destination_path_str = self.format_path_as_string(path=destination_path)
    #     if not destination_path_str:
    #         raise ValueError(f"Invalid source path: {destination_path_str}")
    #     try:
    #         self.io_client.putfo(source_stream, destination_path_str, confirm=True)
    #     except Exception as e:
    #         raise ValueError(f"Error writing to stream: {e}")
        
    #     return True


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

        str_destination_path: str | None = PathHelper.path_to_str(path=destination_path)
        if not str_destination_path:
            return False
        
        if not self.io_client:
            return False

        processed_source_stream: io.BytesIO = self.process_source_stream(source_stream=source_stream,
                                                                        encrypt=encrypt, 
                                                                        decrypt=decrypt,
                                                                        compress=compress,
                                                                        decompress=decompress)


        # do it!
        put_object: Any = self.io_client.putfo( fl=processed_source_stream, 
                                               remotepath=str_destination_path, 
                                               file_size=length ) 

        return put_object

    def _native_put_object_from_path(self, 
                   destination_path: UPath, 
                   source_path: UPath,            
                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False
                   ) -> bool:

        if compress or encrypt or decompress or decrypt:
            raise Exception("put_object_from_path(): Compression and encryption operations are not supported for this operation.")

        if not self.io_client:
            return False


        str_destination_path: str | None = PathHelper.path_to_str(path=destination_path)
        str_source_path: str | None = PathHelper.path_to_str(path=source_path)

        if not str_destination_path:
            return False
        if not str_source_path:
            return False

        # do it!
        #TODO: log some of the stats of the put method
        self.io_client.put(localpath=str_source_path, remotepath=str_destination_path)

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


        if not self.io_client:
            return False

        str_source_path: str | None = PathHelper.path_to_str(path=source_path)

        if not str_source_path:
            return False

        #Read to a temporary stream
        with io.BytesIO() as temp_stream:

            self.io_client.getfo(remotepath=str_source_path, fl=temp_stream)

            self.copy_stream_to_stream(source_stream=temp_stream, 
                                       destination_stream=destination_stream,
                                       encrypt=encrypt, 
                                        decrypt=decrypt,
                                        compress=compress,
                                        decompress=decompress)

        return True        



    def _native_get_object_to_path(self, 
                   source_path: UPath, 
                   destination_path: UPath,            
                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False
                   ) -> bool|Any:

        if compress or encrypt or decompress or decrypt:
            raise Exception("put_object_from_path(): Compression and encryption operations are not supported for this operation.")


        if not self.io_client:
            return False


        str_source_path: str | None = PathHelper.path_to_str(path=source_path)
        str_destination_path: str | None = PathHelper.path_to_str(path=destination_path)

        if not str_source_path:
            return False
        if not str_destination_path:
            return False

        # do it!
        fget:  Any = self.io_client.get(remotepath=str_destination_path, localpath=str_source_path)

        return fget
        


    # def put_object_from_stream(self,
    #                destination_path: Optional[Union[str, UPath]], 
    #                source_stream: IO[Any], 
    #                length: int) -> bool|Any:

    #     self.connect()

    #     #Format S3 Destination
    #     u_destination_path: UPath | None = PathHelper.format_path(path=destination_path)

    #     if self.io_client:

    #         try:

    #             str_destination_path: str | None = PathHelper.path_to_str(path=u_destination_path)
    #             if not str_destination_path:
    #                 return False

    #             put_object: Any = self.io_client.putfo( fl=source_stream, remotepath=str_destination_path, file_size=length )

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
    #     str_destination_path: str | None = PathHelper.path_to_str(path=u_destination_path)

    #     #Format Source
    #     u_source_path: UPath | None = PathHelper.format_path(path=source_path)
    #     str_source_path: str | None = PathHelper.path_to_str(path=u_source_path)

    #     source_exists: bool = self.path_exists(path=u_source_path) if u_source_path else False

    #     #Validate source
    #     if not u_source_path:
    #         return False


    #     #Do it!
    #     if self.io_client and source_exists and str_source_path and str_destination_path:

    #         try:
    #             #MiniIO Client
    #             self.io_client.put(localpath=str_source_path, remotepath=str_destination_path)
                
    #             return True

    #         except Exception as e:
    #             raise ValueError(f"Error writing to stream: {e}")
    #     else:
    #         return False


    # def get_object_to_stream(self,
    #                source_path: Optional[Union[str, UPath]], 
    #                destination_stream: IO[Any]) -> bool:

    #     self.connect()

    #     #Format S3 Source
    #     u_source_path = PathHelper.format_path(path=source_path)
    #     str_source_path = PathHelper.path_to_str(path=u_source_path)

    #     #Validate source
    #     if not u_source_path:
    #         return False

    #     source_exists = self.path_exists(path=u_source_path)
    #     # source_filesize = self.get_size(path=u_source_path)

    #     if not source_exists:
    #         print(f"get_object_to_stream(): Source does not exist: {u_source_path}")
    #         return False

    #     #Do it!        
    #     if self.io_client and source_exists and str_source_path and destination_stream:

    #         try:

    #             # get_obj = self.io_client.get_object(bucket_name=bucket_name, object_name=object_name, length=self.get_size(path=u_source_path))

    #             #MiniIO Client
    #             # source_stream = self.open_read_binarystream(source_path=source_path)
    #             # source_file_size = self.get_size(path=u_source_path)

    #             # stream_data = source_stream.read(source_file_size)
    #             # bytes_io_stream = io.BytesIO(stream_data)

    #             # with self.open_read_binarystream(source_path=source_path) as source_stream:

    #             #     stream_data = source_stream.read()
    #             #     bytes_io_stream = io.BytesIO(stream_data)

    #             fget:  Any = self.io_client.getfo(remotepath=str_source_path, fl=destination_stream)


    #             # destination_stream.write(bytes_io_stream)
                
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
    #     str_destination_path: str | None = PathHelper.path_to_str(path=u_destination_path)

    #     #Format S3 Source
    #     u_source_path: str | None = PathHelper.path_to_str(path=source_path)

    #     #Validate source        
    #     if not u_source_path:
    #         return False

    #     source_exists = self.path_exists(path=u_source_path)

    #     if not source_exists:
    #         print(f"get_object_to_path(): Source does not exist: {u_source_path}")
    #         return False


    #     if self.io_client and source_exists and str_destination_path and u_source_path:

    #         try:

    #             #MiniIO Client
    #             fget:  Any = self.io_client.get(remotepath=str_destination_path, localpath=u_source_path)

    #             return fget

    #         except Exception as e:
    #             raise ValueError(f"Error writing to path: {e}")
    #     else:
    #         return False


    #================================================================
    # Filesystem operations



    def list_sources(self, path: Union[str, UPath] = "", **kwargs) -> List[str]:
        """
        List available data sources in the specified path or directory.
        """

        # formatted_path = PathHelper.format_path(path) 
        # return list(formatted_path.fs.glob(path))
        path_str: str | None = self.format_path_as_string(path=path)
        if not path_str:
            return []

        if self.connect():
            #sftp_client.chdir(remote_directory_path)
            directory_items = self.io_client.listdir(path_str) if self.io_client else []
            return directory_items
        else:
            return []


    def calculate_checksum(self, path: Union[str, UPath], algorithm: str = 'sha256') -> None:
        """
        Calculate the checksum of the data at the specified path.
        """
        pass
        # hash_alg = hashlib.new(algorithm)
        # with open(path, 'rb') as file:
        #     for chunk in iter(lambda: file.read(4096), b""):
        #         hash_alg.update(chunk)
        # return hash_alg.hexdigest()
    
    def get_size(self, path: Union[str, UPath]) -> int:
        """
        Get the size of the data at the specified path.
        """

        path_str = self.format_path_as_string(path=path)
        
        if not path_str or not self.connect():
            return 0

        try:
            stats: None|SFTPAttributes = self.io_client.stat(path_str)  if self.io_client else None
            if stats and stats.st_size is not None:
                return stats.st_size
        except IOError:
            pass

        return 0


    def path_exists(self, path: Union[str, UPath]) -> bool:
        """
        Checks if the specified path exists.

        :param path: The path to check.
        :return: True if the path exists, False otherwise.
        """

        path_str = self.format_path_as_string(path=path)
        
        if not path_str or not self.connect():
            return False

        try:
            self.io_client.stat(path_str)  if self.io_client else None
        except IOError:
            return False
        else:
            return True



    def path_is_dir(self,  path: Union[str, UPath]) -> bool:
        """
        Checks if the specified path exists.

        :param path: The path to check.
        :return: True if the path exists, False otherwise.
        """
        u_path: UPath|None = PathHelper.format_path(path=path)        

        if not u_path:
            return False

        return u_path.is_dir()
    
    def path_is_file(self,  path: Union[str, UPath]) -> bool:
        """
        Checks if the specified path exists.

        :param path: The path to check.
        :return: True if the path exists, False otherwise.
        """
        u_path: UPath|None = PathHelper.format_path(path=path)        

        if not u_path:
            return False

        return u_path.is_file()    

    def create_directory(
        self, 
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
        u_path: UPath|None = PathHelper.format_path(path=path)

        if not u_path:
            print(f"Error creating local directory: {path}")
            return False


        try:
            if not u_path.exists():
                #can I use smart open to create a folder?
                os.makedirs(name=u_path.path, exist_ok=True)

        except OSError:
            print(f"Error creating local directory: {u_path.path}")
            return False
        
        return True