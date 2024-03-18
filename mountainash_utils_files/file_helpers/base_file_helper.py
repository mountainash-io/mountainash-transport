from abc import ABC, abstractmethod
from typing import Any, List, Union, Optional, Iterable, IO, BinaryIO, TextIO
from upath import UPath
import shutil
import io 
from functools import lru_cache
from smart_open import open
from upath import UPath
from paramiko import SSHClient, AutoAddPolicy
from gnupg import GPG 
import gzip
import polars
import pyarrow.parquet as pq

from mountainash_acdrs.utils.path_utils.path_utils import PathUtils
from mountainash_acdrs.utils import DataclassUtils
from mountainash_acdrs.constants import CONST_STORAGESYSTEM

from mountainash_acdrs.settings import SettingsParameters, AuthSettings, get_auth_settings

class Base_FileHelper(ABC):

    storage_system: str
    auth_parameters: SettingsParameters
    auth_settings: AuthSettings

    io_hostname: str
    io_port: int
    io_username: str
    io_password: str
    io_keypath: str|UPath

    ssh_hostname: str
    ssh_port: int
    ssh_fwd_remoteport: int
    ssh_fwd_localport: int
    ssh_username: str
    ssh_password: str
    ssh_keypath: str|UPath

    io_client: Optional[Any]
    ssh_client: Optional[Any]

    compression_type: str
    encryption_type: str

    gpg_home: str
    gpg_key_id: str
    gpg_key_file: str|UPath
    gpg_client: GPG

    #Controls initialsation of the storage system
    requires_io_connection: bool
    requires_ssh_connection: bool

    #Features control rule-based dispatch when analysing ourec and destination paths across storage types
    enable_encrypt_on_write: bool
    enable_decrypt_on_read: bool


    supports_native_get_to_stream: bool
    supports_native_put_from_stream: bool
    supports_native_get_to_local_path: bool
    supports_native_put_from_local_path: bool
    supports_native_get_to_native_path: bool
    supports_native_put_from_native_path: bool

    supports_encrypt_native_get_to_stream: bool
    supports_encrypt_native_put_from_stream: bool
    supports_encrypt_native_get_to_local_path: bool
    supports_encrypt_native_put_from_local_path: bool
    supports_encrypt_native_get_to_native_path: bool
    supports_encrypt_native_put_from_native_path: bool

    supports_decrypt_native_get_to_stream: bool
    supports_decrypt_native_put_from_stream: bool
    supports_decrypt_native_get_to_local_path: bool
    supports_decrypt_native_put_from_local_path: bool
    supports_decrypt_native_get_to_native_path: bool
    supports_decrypt_native_put_from_native_path: bool

    supports_compress_native_get_to_stream: bool
    supports_compress_native_put_from_stream: bool
    supports_compress_native_get_to_local_path: bool
    supports_compress_native_put_from_local_path: bool
    supports_compress_native_get_to_native_path: bool
    supports_compress_native_put_from_native_path: bool

    supports_decompress_native_get_to_stream: bool
    supports_decompress_native_put_from_stream: bool
    supports_decompress_native_get_to_local_path: bool
    supports_decompress_native_put_from_local_path: bool
    supports_decompress_native_get_to_native_path: bool
    supports_decompress_native_put_from_native_path: bool

    supports_smartopen_read_stream: bool
    supports_encrypt_smartopen_read_stream: bool
    supports_decrypt_smartopen_read_stream: bool
    supports_compress_smartopen_read_stream: bool
    supports_decompress_smartopen_read_stream: bool

    supports_smartopen_write_stream: bool
    supports_encrypt_smartopen_write_stream: bool
    supports_decrypt_smartopen_write_stream: bool
    supports_compress_smartopen_write_stream: bool
    supports_decompress_smartopen_write_stream: bool

    supports_get_to_stream: bool
    supports_get_to_path: bool
    supports_put_from_stream: bool
    supports_put_from_path: bool


    supports_polars_native_read_parquet: bool
    supports_polars_stream_read_parquet: bool
    supports_decrypt_polars_read_parquet: bool
    supports_decompress_polars_read_parquet: bool
    supports_pyarrow_write_parquet: bool
    supports_encrypt_pyarrow_write_parquet: bool
    supports_compress_pyarrow_write_parquet: bool

    prefer_native_on_get: bool
    prefer_smartopen_on_get: bool
    prefer_native_on_put: bool
    prefer_smartopen_on_put: bool

    def __init__(self, 
                 auth_parameters: SettingsParameters,
                 ) -> None:

        self.io_auth_parameters = auth_parameters
        self.io_auth_settings: AuthSettings = get_auth_settings(auth_settings_parameters=auth_parameters)
        self.storage_system = self.io_auth_settings.STORAGE_SYSTEM

        self.compression_type = self.io_auth_settings.COMPRESSION_TYPE
        self.encryption_type = self.io_auth_settings.ENCRYPTION_TYPE


        if self.io_auth_settings.STORAGE_SYSTEM not in DataclassUtils.get_enum_values_set(enumclass=CONST_STORAGESYSTEM):
            raise ValueError(f"Invalid storage system: {self.io_auth_settings.STORAGE_SYSTEM}. Check your auth settings value STORAGE_SYSTEM. Valid values are: {DataclassUtils.get_enum_values_set(CONST_STORAGESYSTEM)}")

        # if self.io_auth_settings.ENCRYPTION_TYPE and self.io_auth_settings.ENCRYPTION_TYPE not in DataclassUtils.get_enum_values_set(enumclass=CONST_ENCRYPTION_TYPE):
        #     raise ValueError(f"Invalid storage system: {self.io_auth_settings.ENCRYPTION_TYPE}. Check your auth settings value ENCRYPTION_TYPE. Valid values are: {DataclassUtils.get_enum_values_set(CONST_ENCRYPTION_TYPE)}")

        # if self.io_auth_settings.COMPRESSION_TYPE and self.io_auth_settings.COMPRESSION_TYPE not in DataclassUtils.get_enum_values_set(enumclass=CONST_COMPRESSION_TYPE):
        #     raise ValueError(f"Invalid storage system: {self.io_auth_settings.COMPRESSION_TYPE}. Check your auth settings value COMPRESSION_TYPE. Valid values are: {DataclassUtils.get_enum_values_set(CONST_COMPRESSION_TYPE)}")


        self.requires_io_connection = False
        self.requires_ssh_connection = False

        self.io_client = None
        self.ssh_client = None


    #================================================================
    # IO Connection operations


    @abstractmethod
    def connect(self) -> bool:
        return True
    
    @abstractmethod
    def check_if_io_connected(self) -> bool:
        return True
    
    @abstractmethod
    def get_connection_client_parameters(self) -> dict:
        return {}


    #================================================================
    # Attributes for rule-based function dispatch


    @abstractmethod
    def set_interface_attributes(self) -> None:
        pass


    def get_interface_attributes(self, role: Optional[str] = None) -> dict[str, bool]:

        if  role:
            role = f"{role}_"

        if not role:
            role = ""
        

        file_feature_attributes = {

            #Native method support
            f"{role}supports_native_get_to_stream":                 self.supports_native_get_to_stream ,
            f"{role}supports_native_put_from_stream":               self.supports_native_put_from_stream ,
            f"{role}supports_native_get_to_local_path":             self.supports_native_get_to_local_path,
            f"{role}supports_native_put_from_local_path":           self.supports_native_put_from_local_path,
            f"{role}supports_native_get_to_native_path":            self.supports_native_get_to_native_path,
            f"{role}supports_native_put_from_native_path":          self.supports_native_put_from_native_path,

            f"{role}supports_encrypt_native_get_to_stream":         self.supports_encrypt_native_get_to_stream ,
            f"{role}supports_encrypt_native_put_from_stream":       self.supports_encrypt_native_put_from_stream ,
            f"{role}supports_encrypt_native_get_to_local_path":     self.supports_encrypt_native_get_to_local_path,
            f"{role}supports_encrypt_native_put_from_local_path":   self.supports_encrypt_native_put_from_local_path,
            f"{role}supports_encrypt_native_get_to_native_path":    self.supports_encrypt_native_get_to_native_path,
            f"{role}supports_encrypt_native_put_from_native_path":  self.supports_encrypt_native_put_from_native_path,

            f"{role}supports_decrypt_native_get_to_stream":         self.supports_decrypt_native_get_to_stream ,
            f"{role}supports_decrypt_native_put_from_stream":       self.supports_decrypt_native_put_from_stream ,
            f"{role}supports_decrypt_native_get_to_local_path":     self.supports_decrypt_native_get_to_local_path,
            f"{role}supports_decrypt_native_put_from_local_path":   self.supports_decrypt_native_put_from_local_path,
            f"{role}supports_decrypt_native_get_to_native_path":    self.supports_decrypt_native_get_to_native_path,
            f"{role}supports_decrypt_native_put_from_native_path":  self.supports_decrypt_native_put_from_native_path,

            f"{role}supports_compress_native_get_to_stream":        self.supports_compress_native_get_to_stream ,
            f"{role}supports_compress_native_put_from_stream":      self.supports_compress_native_put_from_stream ,
            f"{role}supports_compress_native_get_to_local_path":    self.supports_compress_native_get_to_local_path,
            f"{role}supports_compress_native_put_from_local_path":  self.supports_compress_native_put_from_local_path,
            f"{role}supports_compress_native_get_to_native_path":   self.supports_compress_native_get_to_native_path,
            f"{role}supports_compress_native_put_from_native_path": self.supports_compress_native_put_from_native_path,

            f"{role}supports_decompress_native_get_to_stream":          self.supports_decompress_native_get_to_stream ,
            f"{role}supports_decompress_native_put_from_stream":        self.supports_decompress_native_put_from_stream ,
            f"{role}supports_decompress_native_get_to_local_path":      self.supports_decompress_native_get_to_local_path,
            f"{role}supports_decompress_native_put_from_local_path":    self.supports_decompress_native_put_from_local_path,
            f"{role}supports_decompress_native_get_to_native_path":     self.supports_decompress_native_get_to_native_path,
            f"{role}supports_decompress_native_put_from_native_path":   self.supports_decompress_native_put_from_native_path,

            #Smart open support
            f"{role}supports_smartopen_read_stream":               self.supports_smartopen_read_stream,
            f"{role}supports_encrypt_smartopen_read_stream":       self.supports_encrypt_smartopen_read_stream,
            f"{role}supports_decrypt_smartopen_read_stream":       self.supports_decrypt_smartopen_read_stream,
            f"{role}supports_compress_smartopen_read_stream":      self.supports_compress_smartopen_read_stream,
            f"{role}supports_decompress_smartopen_read_stream":    self.supports_decompress_smartopen_read_stream,

            f"{role}supports_smartopen_write_stream":              self.supports_smartopen_write_stream,
            f"{role}supports_encrypt_smartopen_write_stream":      self.supports_encrypt_smartopen_write_stream,
            f"{role}supports_decrypt_smartopen_write_stream":      self.supports_decrypt_smartopen_write_stream,
            f"{role}supports_compress_smartopen_write_stream":     self.supports_compress_smartopen_write_stream,
            f"{role}supports_decompress_smartopen_write_stream":   self.supports_decompress_smartopen_write_stream,

            #Polars support
            f"{role}supports_polars_read_parquet":               self.supports_polars_native_read_parquet,             


            #Preferences for tie-breaks
            f"{role}prefer_native_on_read":        self.prefer_native_on_get,
            f"{role}prefer_smartopen_on_read":     self.prefer_smartopen_on_put,
            f"{role}prefer_native_on_write":       self.prefer_native_on_get,
            f"{role}prefer_smartopen_on_write":    self.prefer_smartopen_on_get,

        }
        return file_feature_attributes


    def get_interface_attributes_transposed(self, role: Optional[str] = None) -> List[dict[str, bool]]:

        if  role:
            role = f"{role}_"

        if not role:
            role = ""
        

        file_feature_attributes = [
            {
                f"{role}storage_system": self.storage_system,
                f"{role}method": "native_get_to_stream",

                f"{role}supports_native_get":       True,
                f"{role}supports_to_stream":        self.supports_native_get_to_stream,
                f"{role}supports_to_local_path":    self.supports_native_get_to_local_path,
                f"{role}supports_to_native_path":   self.supports_native_get_to_native_path,
                f"{role}supports_native_put":         False,
                f"{role}supports_from_stream":        False,
                f"{role}supports_from_local_path":    False,
                f"{role}supports_from_native_path":   True,

                f"{role}supports_encrypt":      self.supports_encrypt_native_get_to_stream,
                f"{role}supports_decrypt":      self.supports_decrypt_native_get_to_stream,
                f"{role}supports_compress":     self.supports_compress_native_get_to_stream,
                f"{role}supports_decompress":   self.supports_decompress_native_get_to_stream,
            },
            {
                f"{role}storage_system": self.storage_system,
                f"{role}method": "native_get_to_path",


                f"{role}supports_native_get":       True,
                f"{role}supports_to_stream":        False,
                f"{role}supports_to_local_path":    self.supports_native_get_to_local_path,
                f"{role}supports_to_native_path":   self.supports_native_get_to_native_path,
                f"{role}supports_native_put":         False,
                f"{role}supports_from_stream":        False,
                f"{role}supports_from_local_path":    False,
                f"{role}supports_from_native_path":   True,


                f"{role}supports_encrypt":      self.supports_encrypt_native_get_to_native_path or self.supports_encrypt_native_get_to_local_path,
                f"{role}supports_decrypt":      self.supports_decrypt_native_get_to_native_path or self.supports_decrypt_native_get_to_local_path,
                f"{role}supports_compress":     self.supports_compress_native_get_to_native_path or self.supports_compress_native_get_to_local_path,
                f"{role}supports_decompress":   self.supports_decompress_native_get_to_native_path or self.supports_decompress_native_get_to_local_path,

            },
            {
                f"{role}storage_system": self.storage_system,
                f"{role}method": "native_put_from_stream",

                f"{role}supports_native_get":       False,
                f"{role}supports_to_stream":        False,
                f"{role}supports_to_local_path":    None,
                f"{role}supports_to_native_path":   True,
                f"{role}supports_native_put":         self.supports_native_put_from_stream,
                f"{role}supports_from_stream":        self.supports_native_put_from_stream,
                f"{role}supports_from_local_path":    False,
                f"{role}supports_from_native_path":   False,


                f"{role}supports_encrypt":      self.supports_encrypt_native_put_from_stream,
                f"{role}supports_decrypt":      self.supports_decrypt_native_put_from_stream,
                f"{role}supports_compress":     self.supports_compress_native_put_from_stream,
                f"{role}supports_decompress":   self.supports_decompress_native_put_from_stream,

            },
            {
                f"{role}storage_system": self.storage_system,
                f"{role}method": "native_put_from_path",

                f"{role}supports_native_get":       False,
                f"{role}supports_to_stream":        False,
                f"{role}supports_to_local_path":    None,
                f"{role}supports_to_native_path":   True,
                f"{role}supports_native_put":         self.supports_native_put_from_local_path or self.supports_native_put_from_native_path,
                f"{role}supports_from_stream":        False,
                f"{role}supports_from_local_path":    self.supports_native_put_from_local_path,
                f"{role}supports_from_native_path":   self.supports_native_put_from_native_path,

                f"{role}supports_encrypt":      self.supports_encrypt_native_put_from_local_path    or self.supports_encrypt_native_put_from_native_path,   
                f"{role}supports_decrypt":      self.supports_decrypt_native_put_from_local_path    or self.supports_decrypt_native_put_from_native_path ,  
                f"{role}supports_compress":     self.supports_compress_native_put_from_local_path   or self.supports_compress_native_put_from_native_path , 
                f"{role}supports_decompress":   self.supports_decompress_native_put_from_local_path or self.supports_decompress_native_put_from_native_path,

            },
            {
                f"{role}storage_system": self.storage_system,
                f"{role}method": "smartopen_read_stream",

                f"{role}supports_native_get":       False,
                f"{role}supports_to_stream":        False,
                f"{role}supports_to_local_path":    None,
                f"{role}supports_to_native_path":   True,
                f"{role}supports_native_put":         self.supports_native_put_from_local_path or self.supports_native_put_from_native_path,
                f"{role}supports_from_stream":        False,
                f"{role}supports_from_local_path":    self.supports_native_put_from_local_path,
                f"{role}supports_from_native_path":   self.supports_native_put_from_native_path,

                f"{role}supports_encrypt":      self.supports_encrypt_native_get_to_stream,
                f"{role}supports_decrypt":      self.supports_decrypt_native_get_to_stream,
                f"{role}supports_compress":     self.supports_compress_native_get_to_stream,
                f"{role}supports_decompress":   self.supports_decompress_native_get_to_stream,

 
            },
            {
                f"{role}storage_system": self.storage_system,
                f"{role}method": "smartopen_write_stream",

                f"{role}supports_native_get":       False,
                f"{role}supports_to_stream":        self.supports_smartopen_write_stream,
                f"{role}supports_to_local_path":    self.supports_smartopen_write_stream,
                f"{role}supports_to_native_path":   False,
                f"{role}supports_native_put":         False,
                f"{role}supports_from_stream":        self.supports_smartopen_read_stream,
                f"{role}supports_from_local_path":    self.supports_native_put_from_local_path,
                f"{role}supports_from_native_path":   self.supports_native_put_from_native_path,

                f"{role}supports_encrypt":      self.supports_encrypt_native_get_to_stream,
                f"{role}supports_decrypt":      self.supports_decrypt_native_get_to_stream,
                f"{role}supports_compress":     self.supports_compress_native_get_to_stream,
                f"{role}supports_decompress":   self.supports_decompress_native_get_to_stream,

            },


        ]
        return file_feature_attributes



    #================================================================
    # SSH Connection operations

    def connect_ssh(self):
        """Connect to the SFTP server"""

        connected: bool = self.check_if_ssh_connected()
        
        if not connected:

            if self.ssh_client is not None:
                self.ssh_client.close()

            self.ssh_client = SSHClient()
            self.ssh_client.set_missing_host_key_policy(AutoAddPolicy())
            #set crypto policy
            #self.ssh_client.get_transport().set_ciphers('aes128-cbc')

            #TODO: Validate that the keypath exists

            if self.ssh_keypath is not None:

                u_ssh_keypath: UPath | None = PathUtils.format_path(self.ssh_keypath)
                ssh_keypath_str: str | None = PathUtils.path_to_str(u_ssh_keypath)

                self.ssh_client.connect(hostname=self.ssh_hostname, port=self.ssh_port, 
                                        username=self.ssh_username, password=self.ssh_password, 
                                        key_filename=ssh_keypath_str)
            else:
                self.ssh_client.connect(hostname=self.ssh_hostname, port=self.ssh_port, 
                                        username=self.ssh_username, password=self.ssh_password)

            # Forward the remote port to the local port
            if self.ssh_fwd_remoteport is not None and self.ssh_fwd_localport is not None:

                transport = self.ssh_client.get_transport()
                reverse_tunnel = transport.open_channel('direct-tcpip', 
                                                        ('127.0.0.1', self.ssh_fwd_localport), 
                                                        ('localhost', self.ssh_fwd_remoteport))
        
        return self.check_if_ssh_connected()


    def check_if_ssh_connected(self):
        """Check if the SFTP server is connected"""

        connected = True

        if self.ssh_client is None:
            connected = False
        else:
            try:
                transport = self.ssh_client.get_transport()
                peername: Any | None = transport.getpeername()  if transport else None  
                connected: bool =  peername is not None

            except OSError:
                connected =  False
            
        return connected

    #================================================================
    # GZip Compression operations


    def check_kwargs_for_compression_encryption(self, calling_function_name: str, **kwargs) -> None:

        compress: bool = kwargs.get('compress', False)
        encrypt: bool = kwargs.get('compress', False)
        decompress: bool = kwargs.get('compress', False)
        decrypt: bool = kwargs.get('compress', False)

        if compress or encrypt or decompress or decrypt:
            raise Exception(f"{calling_function_name}(): Compression and encryption operations are not supported for this operation.")


    def compress_data(self, source_data: bytes) -> Optional[bytes]:
        if not source_data:
            return None

        output = io.BytesIO()
        with gzip.GzipFile(fileobj=output, mode='wb') as gz:
            gz.write(source_data)
        return output.getvalue()

    def decompress_data(self, source_data: bytes) -> Optional[bytes]:
        if not source_data:
            return None

        input_data = io.BytesIO(source_data)
        with gzip.GzipFile(fileobj=input_data, mode='rb') as gz:
            return gz.read()

    def compress_stream(self, source_stream: IO, **kwargs) -> io.BytesIO:

        if not source_stream:
            raise ValueError("Source stream is None")
        
        destination_stream = io.BytesIO()
        source_stream.seek(0)

        print(f"Compressing stream: {source_stream}")

        #Note that smartopen suppports compression natively!


        # Compress the data from source_stream and write it to destination_stream
        with gzip.GzipFile(fileobj=destination_stream, mode='wb', **kwargs) as gzip_file:
            while True:
                block = source_stream.read(1024)  # Read in blocks of 1KB
                if not block:
                    break  # End of file
                gzip_file.write(block)

        source_stream.seek(0)
        destination_stream.seek(0)
        
        return destination_stream

    def decompress_stream(self, source_stream: IO, **kwargs) -> io.BytesIO:

        if not source_stream:
            raise ValueError("Source stream is None")

       
        destination_stream = io.BytesIO()
        source_stream.seek(0)

        print(f"Decompressing stream: {source_stream}")


        # Decompress the data from source_stream and write it to destination_stream
        with gzip.GzipFile(fileobj=source_stream, mode='rb', **kwargs) as gzip_file:
            while True:
                block = gzip_file.read(1024)  # Read in blocks of 1KB
                if not block:
                    break  # End of file
                destination_stream.write(block)

        source_stream.seek(0)
        destination_stream.seek(0)

        return destination_stream


    #================================================================
    # GPG Connection operations

    def init_gpg(self):

        self.gpg_client = GPG(homedir=self.gpg_home)
        self.import_gpg_keys()

        if not self.gpg_client:
            raise ValueError("GPG client initialization failed")


    def import_gpg_keys(self):

        if self.gpg_key_file and self.gpg_client:
            u_gpg_key_file: UPath | None = PathUtils.format_path(path=self.gpg_key_file)
            str_gpg_key_file = PathUtils.path_to_str(path=u_gpg_key_file)

            #May need more options than just a local file
            with open(uri=str_gpg_key_file, mode='rb') as file:
                self.gpg_client.import_keys(key_data=file.read())



    #================================================================
    # GPG Data and File operations

    def encrypt_data(self, source_data: Any|io.BytesIO) -> Optional[Any]:

        if not self.gpg_client:
            self.init_gpg()
        
        if not self.gpg_client:
            return None       
        
        if not source_data:
            return None
        
        return self.gpg_client.encrypt(data=source_data, recipients=[self.gpg_key_id])

    def decrypt_data(self, source_data: Any|io.BytesIO) -> Optional[Any]:

        if not self.gpg_client:
            self.init_gpg()        
        if not self.gpg_client:
            return None              
        if not source_data:
            return None
        
        return self.gpg_client.decrypt(message=source_data)


    def encrypt_stream(self, source_stream: IO, **kwargs) -> io.BytesIO:
        
        if not source_stream:
            raise ValueError("Source stream is None")
        
        if not self.gpg_client:
            self.init_gpg()
        
        destination_stream = io.BytesIO()
        source_stream.seek(0)
        
        try:

            print(f"Encrypting stream: {source_stream}")

            self.gpg_client.encrypt(data=source_stream, recipients=[self.gpg_key_id], output=destination_stream)

            source_stream.seek(0)
            destination_stream.seek(0)  

        except Exception as e:
            print(f"Error during encryption: {e}")
        
        return destination_stream



    def decrypt_stream(self, source_stream: IO, **kwargs) -> io.BytesIO:
       

        if not source_stream:
            raise ValueError("Source stream is None")
           
        if not self.gpg_client:
            self.init_gpg()
        
        destination_stream = io.BytesIO()
        source_stream.seek(0)

        try:
            print(f"Decrypting stream: {source_stream}")
            self.gpg_client.decrypt(message=source_stream, output=destination_stream)

            source_stream.seek(0)
            destination_stream.seek(0)
            
        except Exception as e:
            print(f"Error during decryption: {e}")

        return destination_stream



    #================================================================
    # Stream operations
    def _get_smartopen_stream_generator(self, 
                                        path: Optional[Union[str, UPath]], 
                                        mode: str, 
                                        encrypt_stream: bool = False,
                                        decrypt_stream: bool = False,                                               
                                        **kwargs) -> IO|TextIO|BinaryIO:
        """
        Open stream for reading or writing data.
        """
        valid_modes = set(['w', 'r', 'wb', 'rb'])

        # mode: str|None = str(kwargs.get('mode'))
        
        if not mode:
            raise ValueError("Mode not specified")
        
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode: {mode}")

        u_path: UPath|None = PathUtils.format_path(path=path)
        
        if not u_path:
            raise ValueError("Invalid path")

        if encrypt_stream and decrypt_stream:
            raise ValueError("Cannot encrypt and decrypt at the same time")

        #Open the raw stream       
        stream: TextIO|BinaryIO = open(uri=u_path, mode=mode, **kwargs)


        # if encrypt_stream:
        #     self.encrypt_stream(source_stream=stream)  # Return the encrypted stream

        # if decrypt_stream:
        #     self.decrypt_stream(source_stream=stream)  # Return the encrypted stream


        return stream


    def open_read_binarystream(self, 
                               source_path: Optional[Union[str, UPath]], 
                                **kwargs) -> IO|BinaryIO:
        """
        Read data from the specified source.
        """

        print(f"{self.storage_system}: open_read_binarystream: {source_path}")

        self.connect()

        mode = 'rb'
        stream: IO =  self._get_smartopen_stream_generator(path=source_path, 
                                                    mode=mode,
                                                    transport_params=self.get_connection_client_parameters())
    
        return stream

    def open_write_binarystream(self, 
                                destination_path: Optional[Union[str, UPath]],
                                encrypt_stream: bool = False,
                                decrypt_stream: bool = False,
                                  **kwargs) -> IO|BinaryIO:
        """
        Write data to the specified destination.
        """
        print(f"{self.storage_system}: open_write_binarystream: {destination_path}")

        self.connect()
        mode = 'wb'
        stream: IO =  self._get_smartopen_stream_generator(path=destination_path, 
                                                    mode=mode,
                                                    transport_params=self.get_connection_client_parameters())

        return stream



    def open_read_textstream(self, 
                             source_path: Optional[Union[str, UPath]],                              
                             **kwargs) -> IO|TextIO:
        """
        Read data from the specified source.
        """
        print(f"{self.storage_system}: open_read_textstream: {source_path}")
        
        self.connect()
        mode = 'r'
        return self._get_smartopen_stream_generator(path=source_path, 
                                                    mode=mode,
                                                    transport_params=self.get_connection_client_parameters())

    def open_write_textstream(self, 
                              destination_path: Optional[Union[str, UPath]], 
                              **kwargs) -> IO|TextIO:
        """
        Write data to the specified destination.
        """
        print(f"{self.storage_system}: open_write_textstream: {destination_path}")

        self.connect()
        mode = 'w'


        return self._get_smartopen_stream_generator(path=destination_path, 
                                                    mode=mode,
                                                    transport_params=self.get_connection_client_parameters())




    #================================================================
    # System-specific File operations

    @abstractmethod
    def _native_put_object_from_stream(self,
                   destination_path: UPath, 
                   source_stream: IO, 
                   length: int,            
                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False) -> bool:
        pass
        
    @abstractmethod
    def _native_put_object_from_path(self, 
                   destination_path: UPath, 
                   source_path: UPath, 
                   **kwargs             
                   ) -> bool:
        pass
        

    @abstractmethod
    def _native_get_object_to_stream(self,
                   source_path: UPath, 
                   destination_stream: IO, 
                   length: int,           
                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False
                   ) -> bool:
        pass
        

    @abstractmethod
    def _native_get_object_to_path(self, 
                   source_path: UPath, 
                   destination_path: UPath,            
                    **kwargs  
                   ) -> bool:
        pass



    def process_source_stream(self,
                    source_stream: IO, 
                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False
                    ) -> io.BytesIO:
        
        if not source_stream:
            raise ValueError("Source stream is None")
        
        # We can only go forwards (compress and/or encrypt) or backwards (decrypt then decompress)
        if compress or encrypt:   

            # Forward Path
            if compress and encrypt:
                compressed_stream: IO = self.compress_stream(source_stream=source_stream)
                encrypted_stream: IO = self.encrypt_stream(source_stream=compressed_stream)
                return encrypted_stream

            elif compress:
                compressed_stream = self.compress_stream(source_stream=source_stream)
                return compressed_stream

            elif encrypt:
                encrypted_stream = self.encrypt_stream(source_stream=source_stream)
                return encrypted_stream

        elif decompress or decrypt:                        
            # Backwards Path
            if decompress and decrypt:
                decrypted_stream = self.decrypt_stream(source_stream=source_stream)
                decompressed_stream = self.decompress_stream(source_stream=decrypted_stream)
                return decompressed_stream
            elif decrypt:
                decrypted_stream = self.decrypt_stream(source_stream=source_stream)
                return decrypted_stream

            elif decompress:
                decompressed_stream = self.decompress_stream(source_stream=source_stream)
                return decompressed_stream

        else:

            if compress or encrypt or decompress or decrypt:
                raise Exception("An invalid combination of compression and encryption operations was requested. ")

        destination_stream = io.BytesIO()
        destination_stream.write(source_stream.read())
        destination_stream.seek(0)

        return destination_stream         


    def copy_stream_to_stream(self,
                   source_stream: IO|io.BytesIO, 
                   destination_stream: IO|io.BytesIO,            
                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False
                    ) -> bool:
      

        processed_stream = self.process_source_stream(source_stream=source_stream,
                                                        encrypt=encrypt,
                                                        decrypt=decrypt,
                                                        compress=compress,
                                                        decompress=decompress,
                                                        )

        destination_stream.write(processed_stream.read())        

        return True

    #================================================================
    # Generic File operations


    def put_object_from_stream(self,
                   destination_path: Optional[Union[str, UPath]], 
                   source_stream: IO, 
                   length: int,
                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False
                   ) -> bool|Any:

        self.connect()

        #Format S3 Destination
        u_destination_path: UPath | None = PathUtils.format_path(path=destination_path)

        if self.io_client and source_stream and u_destination_path:

            try:

                                                                   


                put_object = self._native_put_object_from_stream(destination_path=u_destination_path, 
                                                           source_stream=source_stream, 
                                                           length=length,  
                                                           encrypt=encrypt, 
                                                           decrypt=decrypt,
                                                           compress=compress,
                                                           decompress=decompress)
                                                           

                # #Validate Destination
                # bucket_name: str| None = S3PathUtils.get_path_bucketname(path=u_destination_path)
                # object_name: str | None = S3PathUtils.get_path_folders_and_filename(path=u_destination_path)

                # bucket_exists: bool = self._bucket_exists(bucket_name=bucket_name)
                # if not bucket_exists:
                #     return False

                # #MiniIO Client
                # stream_data = source_stream.read(length)
                # bytes_io_stream = io.BytesIO(stream_data)
                # put_object: Any = self.io_client.put_object(bucket_name=bucket_name, object_name=object_name, data=bytes_io_stream, length=length)

                # return put_object

            except Exception as e:
                raise ValueError(f"Error writing to stream: {e}")
        else:
            return False

    def put_object_from_path(self, 
                   destination_path: Optional[Union[str, UPath]], 
                   source_path: Optional[Union[str, UPath]],
                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False,                   
                   ) -> bool:

        if compress or encrypt or decompress or decrypt:
            raise Exception("put_object_from_path(): Compression and encryption operations are not supported for this operation.")


        #This can only be used if the source interface is local or the same as the destination

        self.connect()

        #Format S3 Destination
        u_destination_path = PathUtils.format_path(path=destination_path)
        u_source_path: UPath | None = PathUtils.format_path(path=source_path)

        #Format Source

        #Validate Destintion

        #Validate source
        if not u_source_path:
            return False

        # source_exists = DataStorageFacade.path_exists(path=u_source_path)

        #Do it!
        if self.io_client and u_destination_path and u_source_path:

            try:

                return self._native_put_object_from_path(destination_path=u_destination_path, 
                                                         source_path=u_source_path,  
                                                           encrypt=encrypt, 
                                                           decrypt=decrypt,
                                                           compress=compress,
                                                           decompress=decompress)

                # # Format Source
                # source_path_str: str | None = PathUtils.path_to_str(path=u_source_path)

                # #validate Destination
                # bucket_name: str| None = S3PathUtils.get_path_bucketname(path=u_destination_path)
                # object_name: str | None = S3PathUtils.get_path_folders_and_filename(path=u_destination_path)
                # bucket_exists: bool = self._bucket_exists(bucket_name=bucket_name)
                # if not bucket_exists:
                #     return False


                # #MiniIO Client
                # self.io_client.fput_object(bucket_name=bucket_name, object_name=object_name, file_path=source_path_str)
                
                # return True

            except Exception as e:
                raise ValueError(f"Error writing to stream: {e}")
        else:
            return False


    def get_object_to_stream(self,
                   source_path: Optional[Union[str, UPath]], 
                   destination_stream: IO,
                   length: int,
                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False,                   
                   ) -> bool:

        self.connect()

        #Format Source
        u_source_path = PathUtils.format_path(path=source_path)

        #Validate source
        if not u_source_path:
            return False

        source_exists = self.path_exists(path=u_source_path)

        if not source_exists:
            print(f"get_object_to_stream(): Source does not exist: {u_source_path}")
            return False

        #Do it!        
        if self.io_client and u_source_path and source_exists and destination_stream:

            try:

                return self._native_get_object_to_stream(source_path=u_source_path, 
                                                         destination_stream=destination_stream, 
                                                         length=length,  
                                                           encrypt=encrypt, 
                                                           decrypt=decrypt,
                                                           compress=compress,
                                                           decompress=decompress)

                # bucket_name: str| None = S3PathUtils.get_path_bucketname(path=u_source_path)
                # object_name: str | None = S3PathUtils.get_path_folders_and_filename(path=u_source_path)

                # get_obj = self.io_client.get_object(bucket_name=bucket_name, object_name=object_name, length=self.get_size(path=u_source_path))

                # #MiniIO Client
                # source_stream = self.open_read_binarystream(source_path=source_path)
                # source_file_size = self.get_size(path=u_source_path)

                # stream_data = source_stream.read(source_file_size)
                # bytes_io_stream = io.BytesIO(stream_data)

                # # with self.open_read_binarystream(source_path=source_path) as source_stream:

                # #     stream_data = source_stream.read()
                # #     bytes_io_stream = io.BytesIO(stream_data)

                # destination_stream.write(bytes_io_stream)
                
                # return True

            except Exception as e:
                raise ValueError(f"Error writing to stream: {e}")
        else:
            return False

    def get_object_to_path(self, 
                   source_path: Optional[Union[str, UPath]], 
                   destination_path: Optional[Union[str, UPath]],
                    encrypt: bool = False,
                    decrypt: bool = False,
                    compress: bool = False,
                    decompress: bool = False,                   
                   ) -> bool|Any:

        #This can only be used if the destination interface is local or the same as the source

        if compress or encrypt or decompress or decrypt:
            raise Exception("put_object_from_path(): Compression and encryption operations are not supported for this operation.")

        self.connect()

        #Format Paths
        u_destination_path: UPath | None = PathUtils.format_path(path=destination_path)
        u_source_path: UPath | None = PathUtils.format_path(path=source_path)
 
        #Validate source        
        if not u_source_path:
            return False

        source_exists = self.path_exists(path=u_source_path)
        if not source_exists:
            print(f"get_object_to_path(): Source does not exist: {u_source_path}")
            return False

        if self.io_client and source_exists and u_destination_path:

            try:

                return self._native_get_object_to_path(source_path=u_source_path, 
                                                       destination_path=u_destination_path,  
                                                           encrypt=encrypt, 
                                                           decrypt=decrypt,
                                                           compress=compress,
                                                           decompress=decompress)

                # str_destination_path: str | None = PathUtils.path_to_str(path=u_destination_path)
                
                # #Format S3 Source
                # bucket_name: str| None = S3PathUtils.get_path_bucketname(path=u_source_path)
                # object_name: str | None = S3PathUtils.get_path_folders_and_filename(path=u_source_path)

                # #MiniIO Client
                # fget:  Any = self.io_client.fget_object(bucket_name=bucket_name, object_name=object_name, file_path=str_destination_path)

                # return fget

            except Exception as e:
                raise ValueError(f"Error writing to path: {e}")
        else:
            return False






    # @abstractmethod
    # def read_from_binarystream(self, source_path: Union[UPath,str], destination_stream: Any, **kwargs) -> bool:
    #     pass

    # @abstractmethod
    # def write_to_binarystream(self, destination_path: Union[UPath,str], source_stream: Any, **kwargs) -> bool:
    #     pass

    def prepare_path_parent(self, path: Optional[Union[str, UPath]]) -> bool:
        """
        Get the parent directory of the specified path.
        """
        u_path: UPath|None = PathUtils.format_path(path=path)

        if not u_path:
            return False
        
        parent: UPath = u_path.parent

        if not parent.exists():
            created = self.create_directory(path=parent)

        return self.path_parent_exists(parent)

    def path_parent_exists(self, path: Optional[Union[str, UPath]]) -> bool:
        """
        Get the parent directory of the specified path.
        """
        u_path: UPath|None = PathUtils.format_path(path=path)

        if not u_path:
            return False

        return self.path_exists(path=u_path.parent)        


    # @abstractmethod
    # def open_read_stream(cls, source_path: Optional[Union[str, UPath]], **kwargs) -> Iterable:
    #     """
    #     Read data from the specified source.

    #     :param source: The identifier for the data source (e.g., a file path, database table, or query).
    #     :param kwargs: Additional arguments specific to the storage system.
    #     :return: Data in an appropriate format for the storage system.
    #     """
    #     pass

    # @abstractmethod
    # def open_write_stream(cls, destination_path: Optional[Union[str, UPath]], data: Any, **kwargs) -> None:
    #     """
    #     Write data to the specified destination.

    #     :param destination: The identifier for the data destination.
    #     :param data: The data to write.
    #     :param kwargs: Additional arguments specific to the storage system.
    #     """
    #     pass


    @abstractmethod
    def list_sources(self, path: Optional[Union[str, UPath]] = "", **kwargs) -> List[str]:
        """
        List available data sources in the specified path or directory.

        :param path: The path or directory to list data sources from.
        :param kwargs: Additional arguments specific to the storage system.
        :return: A list of identifiers for the available data sources.
        """
        pass


    @abstractmethod
    def path_exists(self, path: Optional[Union[str, UPath]], **kwargs) -> bool:
        """
        Check if the specified data source exists.

        :param source: The identifier for the data source.
        :param kwargs: Additional arguments specific to the storage system.
        :return: True if the data source exists, False otherwise.
        """
        pass

    @abstractmethod
    def calculate_checksum(self, path: Optional[Union[str, UPath]], algorithm: str = 'sha256') -> str:
        """
        Calculate the checksum of the data at the specified path.

        :param path: The path to the data.
        :param algorithm: The hashing algorithm to use (e.g., 'md5', 'sha1', 'sha256').
        :return: The calculated checksum as a hexadecimal string.
        """
        pass

    @abstractmethod
    def get_size(self, path: Optional[Union[str, UPath]]) -> int:
        """
        Get the size of the data at the specified path.

        :param path: The path to the data.
        :return: The size of the data in bytes.
        """
        pass

    @abstractmethod
    def path_is_dir(self, path: Optional[Union[str, UPath]]) -> bool:
        pass

    @abstractmethod
    def path_is_file(self, path: Optional[Union[str, UPath]]) -> bool:
        pass

    @abstractmethod
    def create_directory(cls, path: Optional[Union[str, UPath]]) -> bool :
        pass



    @classmethod
    def count_sources(cls, path: Optional[Union[str, UPath]], **kwargs) -> int:
        """
        List available data sources in the specified path or directory.

        :param path: The path or directory to list data sources from.
        :param kwargs: Additional arguments specific to the storage system.
        :return: A list of identifiers for the available data sources.
        """
        return len(cls.list_sources(path=path, **kwargs))
    

    @classmethod
    def format_path_as_string(cls, path: Optional[Union[str, UPath]]) -> Optional[str]:
        """
        Format the path as a string.

        :param path: The path to format.
        :return: The formatted path as a string.
        """
        return PathUtils.path_to_str(path=path)
