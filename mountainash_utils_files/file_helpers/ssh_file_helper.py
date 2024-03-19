import os
import hashlib
from typing import Any, List, Union, IO
from upath import UPath
import subprocess

from smart_open import open
from .base_file_helper import Base_FileHelper

from mountainash_utils_files import PathHelper
from mountainash_settings import SettingsParameters, get_auth_settings, AuthSettings

class SSH_FileHelper(Base_FileHelper):


    def __init__(self, 
                 auth_parameters: SettingsParameters
                 ) -> None:

        auth_settings: AuthSettings = get_auth_settings(auth_settings_parameters=auth_parameters)

        #If using this class, you will need to configure ssh multiplexing (connection reuse)
        # Set a short time limit so that multiple files can be transferred in quick succession
        # without leaving the connection open for too long. 
        # Add the following in your ~/.ssh/config file:
        # Host remote.example.com
        # ControlMaster auto
        # ControlPath ~/.ssh/cm-%r@%h:%p
        # ControlPersist 60 #60 seconds



        """Initialize the SFTPManager object"""
        self.ssh_hostname =     auth_settings.HOST
        self.ssh_port =         auth_settings.PORT
        self.ssh_username =     auth_settings.USERNAME
        self.ssh_password =     auth_settings.PASSWORD
        self.ssh_key_path = auth_settings.SSH_KEY_PATH

        self.ssh_fwd_remoteport =  auth_settings.SSH_FWD_REMOTEPORT
        self.ssh_fwd_localport =   auth_settings.SSH_FWD_LOCALPORT

        self.requires_io_connection = False
        self.requires_ssh_connection = True

        self.supports_get_to_stream = True
        self.supports_put_from_stream = True
        self.supports_get_to_local_path = True
        self.supports_put_from_local_path = True


    def connect(self) -> bool:
        return self.connect_ssh()


    
    def check_if_io_connected(self) -> bool:
        return self.check_if_ssh_connected()




    def put_to_path(local_path, remote_path, remote_host, username):
        command = [
            "rsync",
            "-avz",
            "-e", "ssh",
            local_path,
            f"{username}@{remote_host}:{remote_path}"
        ]
        
        try:
            result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print("Successfully pushed to remote path:")
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print("Failed to push to remote path:")
            print(e.stderr)


    def get_from_path(remote_host, remote_path, local_path, username):
        command = [
            "rsync",
            "-avz",
            "-e", "ssh",
            f"{username}@{remote_host}:{remote_path}",
            local_path
        ]
        
        try:
            result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print("Successfully pulled from remote path:")
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print("Failed to pull from remote path:")
            print(e.stderr)



    @classmethod
    def read_data(cls, source_path: Union[str, UPath], **kwargs) -> Any:
        """
        Read data from the specified source.
        """
        mode = kwargs.get('mode', 'r')  # Default mode is text; use 'rb' for binary
        with open(source_path, mode) as file:
            return file.read()

    @classmethod
    def write_data(cls, destination_path: Union[str, UPath], data: Any, **kwargs):
        """
        Write data to the specified destination.
        """
        mode = kwargs.get('mode', 'w')  # Default mode is text; use 'wb' for binary
        with open(destination_path, mode) as file:
            file.write(data)

    @classmethod
    def copy_to(cls, destination_path: Union[str, UPath], source_file: IO):
        pass

    @classmethod
    def copy_from(cls, source_path: Union[str, UPath]) -> None:
        pass


    @classmethod
    def list_sources(cls, path: Union[str, UPath] = "", **kwargs) -> List[str]:
        """
        List available data sources in the specified path or directory.
        """

        # formatted_path = PathHelper.format_path(path) 
        # return list(formatted_path.fs.glob(path))
            
        return [str(p) for p in UPath(path).glob(kwargs.get('pattern', '*'))]

    @classmethod
    def calculate_checksum(cls, path: Union[str, UPath], algorithm: str = 'sha256') -> None:
        """
        Calculate the checksum of the data at the specified path.
        """
        pass
        # hash_alg = hashlib.new(algorithm)
        # with open(path, 'rb') as file:
        #     for chunk in iter(lambda: file.read(4096), b""):
        #         hash_alg.update(chunk)
        # return hash_alg.hexdigest()

    @classmethod
    def get_size(cls, path: Union[str, UPath]) -> int:
        """
        Get the size of the data at the specified path.
        """
        return os.path.getsize(path)

    @classmethod
    def path_exists(cls,  path: Union[str, UPath]) -> bool:
        """
        Checks if the specified path exists.

        :param path: The path to check.
        :return: True if the path exists, False otherwise.
        """
        u_path: UPath|None = PathHelper.format_path(path)    

        if not u_path:
            return False
        
        return u_path.exists()

    @classmethod
    def path_is_dir(cls,  path: Union[str, UPath]) -> bool:
        """
        Checks if the specified path exists.

        :param path: The path to check.
        :return: True if the path exists, False otherwise.
        """
        u_path: UPath|None = PathHelper.format_path(path)        

        if not u_path:
            return False
        
        return u_path.is_dir()
    
    @classmethod
    def path_is_file(cls,  path: Union[str, UPath]) -> bool:
        """
        Checks if the specified path exists.

        :param path: The path to check.
        :return: True if the path exists, False otherwise.
        """
        u_path: UPath|None = PathHelper.format_path(path)        

        if not u_path:
            return False

        return u_path.is_file()    


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
        u_path: UPath|None = PathHelper.format_path(path)

        if not u_path:
            return False

        try:
            if not u_path.exists():
                #can I use smart open to create a folder?
                os.makedirs(name=u_path.path, exist_ok=True)

        except OSError:
            print(f"Error creating local directory: {u_path.path}")
            return False
        
        return True