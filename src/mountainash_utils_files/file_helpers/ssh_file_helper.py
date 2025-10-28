import os
import subprocess
from typing import Any, List, Union, IO

from upath import UPath
from smart_open import open

from mountainash_utils_files.path_helpers import PathHelper
from mountainash_settings import SettingsParameters
from ..settings.providers.ssh import SSHStorageAuthSettings

from .base_file_helper import Base_FileHelper

class SSH_FileHelper(Base_FileHelper):


    def __init__(self,
                 auth_parameters: SettingsParameters
                 ) -> None:

        # Initialize base class
        super().__init__()

        auth_settings: SSHStorageAuthSettings = SSHStorageAuthSettings.get_settings(settings_parameters=auth_parameters)

        #If using this class, you will need to configure ssh multiplexing (connection reuse)
        # Set a short time limit so that multiple files can be transferred in quick succession
        # without leaving the connection open for too long.
        # Add the following in your ~/.ssh/config file:
        # Host remote.example.com
        # ControlMaster auto
        # ControlPath ~/.ssh/cm-%r@%h:%p
        # ControlPersist 60 #60 seconds

        self.auth_parameters = auth_parameters
        self.ssh_hostname = auth_settings.HOST
        self.ssh_port = auth_settings.PORT
        self.ssh_username = auth_settings.USERNAME
        self.ssh_password = auth_settings.PASSWORD
        self.ssh_key_path = getattr(auth_settings, 'SSH_KEY_PATH', None)

        self.ssh_fwd_remoteport = getattr(auth_settings, 'SSH_FWD_REMOTEPORT', None)
        self.ssh_fwd_localport = getattr(auth_settings, 'SSH_FWD_LOCALPORT', None)

        self.requires_io_connection = False
        self.requires_ssh_connection = True

        self.supports_get_to_stream = True
        self.supports_put_from_stream = True
        self.supports_get_to_local_path = True
        self.supports_put_from_local_path = True

        self.supports_directories = True

        # Set interface attributes
        self.set_interface_attributes()

    def set_interface_attributes(self):
        """Set the interface attributes for SSH storage."""
        # Basic attributes - SSH has limited native support
        self.supports_native_get_to_stream = False
        self.supports_native_put_from_stream = False
        self.supports_native_get_to_local_path = True  # via rsync
        self.supports_native_put_from_local_path = True  # via rsync

        # Smart-open support
        self.supports_smartopen_read_stream = True
        self.supports_smartopen_write_stream = True

        # General capabilities
        self.supports_get_to_stream = True
        self.supports_get_to_path = True
        self.supports_put_from_stream = True
        self.supports_put_from_path = True

    def connect(self) -> bool:
        return self.connect_ssh()

    def check_if_io_connected(self) -> bool:
        return self.check_if_ssh_connected()

    def get_connection_client_parameters(self) -> dict:
        """Get SSH connection client parameters."""
        return {
            'hostname': self.ssh_hostname,
            'port': self.ssh_port,
            'username': self.ssh_username,
            'password': self.ssh_password,
            'key_path': self.ssh_key_path
        }




    @staticmethod
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


    @staticmethod
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


    def list_sources(self, path: Union[str, UPath], **kwargs) -> List[UPath]:
        """
        List available data sources in the specified path or directory.
        """

        # formatted_path = PathHelper.format_path(path)
        # return list(formatted_path.fs.glob(path))

        return list(UPath(path).glob(kwargs.get('pattern', '*')))

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

    def get_size(self, path: Union[str, UPath]) -> int:
        """
        Get the size of the data at the specified path.
        """
        return os.path.getsize(path)

    def path_exists(self, path: Union[str, UPath]) -> bool:
        """
        Checks if the specified path exists.

        :param path: The path to check.
        :return: True if the path exists, False otherwise.
        """
        u_path: UPath|None = PathHelper.format_path(path)

        if not u_path:
            return False

        return u_path.exists()

    def path_is_dir(self, path: Union[str, UPath]) -> bool:
        """
        Checks if the specified path exists.

        :param path: The path to check.
        :return: True if the path exists, False otherwise.
        """
        u_path: UPath|None = PathHelper.format_path(path)

        if not u_path:
            return False

        return u_path.is_dir()

    def path_is_file(self, path: Union[str, UPath]) -> bool:
        """
        Checks if the specified path exists.

        :param path: The path to check.
        :return: True if the path exists, False otherwise.
        """
        u_path: UPath|None = PathHelper.format_path(path)

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

    # Required abstract method implementations

    def _native_put_object_from_stream(self, destination_path: UPath, source_stream: Any, **kwargs) -> bool:
        """SSH doesn't support native stream operations - use smart-open fallback."""
        # This would be handled by the base class fallback mechanisms
        raise NotImplementedError("SSH uses smart-open for stream operations")

    def _native_put_object_from_path(self, destination_path: UPath, source_path: UPath, **kwargs) -> bool:
        """Put object from local path to SSH destination using rsync."""
        try:
            self.put_to_path(str(source_path), str(destination_path), self.ssh_hostname, self.ssh_username)
            return True
        except Exception:
            return False

    def _native_get_object_to_stream(self, source_path: UPath, destination_stream: Any, **kwargs) -> bool:
        """SSH doesn't support native stream operations - use smart-open fallback."""
        # This would be handled by the base class fallback mechanisms
        raise NotImplementedError("SSH uses smart-open for stream operations")

    def _native_get_object_to_path(self, source_path: UPath, destination_path: UPath, **kwargs) -> bool:
        """Get object from SSH source to local path using rsync."""
        try:
            self.get_from_path(self.ssh_hostname, str(source_path), str(destination_path), self.ssh_username)
            return True
        except Exception:
            return False
