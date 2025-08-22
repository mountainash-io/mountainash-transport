# Updates to local_file_helper.py

import os
import stat
import datetime
from typing import Any, List, Union, IO, Optional, Dict
from upath import UPath
import shutil
import hashlib
from pathlib import Path

from .base_file_helper import Base_FileHelper
from mountainash_utils_files.path_helpers import PathHelper
from mountainash_settings import SettingsParameters
from ..constants import CONST_STORAGE_PROVIDER_TYPE
from ..dataclasses import FileMetadata

from ..settings.providers import LocalStorageAuthSettings

class Local_FileHelper(Base_FileHelper):
    """
    Local filesystem implementation of the Base_FileHelper interface.
    Handles file operations on the local filesystem.
    """

    def __init__(self,
                 auth_parameters: Optional[SettingsParameters] = None,
                 ) -> None:
        """
        Initialize the Local_FileHelper.

        Args:
            auth_parameters: Settings parameters for authentication
        """
        # Initialize base class
        super().__init__()

        self.auth_parameters = auth_parameters
        self.storage_provider_type = CONST_STORAGE_PROVIDER_TYPE.LOCAL
        self.storage_system = "LOCAL"

        # Get settings for local storage
        if auth_parameters is not None:
            self.io_settings = LocalStorageAuthSettings.get_settings(auth_parameters)

        # Local filesystem doesn't need special connections
        self.requires_io_connection = False
        self.requires_ssh_connection = False

        self.io_client = None
        self.ssh_client = None

        self.set_interface_attributes()

    def set_interface_attributes(self):
        """Set the interface attributes for local storage."""
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

        self.supports_native_get_to_native_path = True
        self.supports_encrypt_native_get_to_native_path = True
        self.supports_decrypt_native_get_to_native_path = True
        self.supports_compress_native_get_to_native_path = True
        self.supports_decompress_native_get_to_native_path = True

        self.supports_native_put_from_native_path = True
        self.supports_encrypt_native_put_from_native_path = True
        self.supports_decrypt_native_put_from_native_path = True
        self.supports_compress_native_put_from_native_path = True
        self.supports_decompress_native_put_from_native_path = True

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

        self.supports_polars_native_read_parquet = True
        self.supports_polars_stream_read_parquet = True
        self.supports_decrypt_polars_read_parquet = True
        self.supports_decompress_polars_read_parquet = True
        self.supports_pyarrow_write_parquet = True
        self.supports_encrypt_pyarrow_write_parquet = True
        self.supports_compress_pyarrow_write_parquet = True

        self.supports_directories = True

    #================================================================
    # Connection operations - simple for local storage

    def connect(self) -> bool:
        """Connect to the local filesystem (always returns True)."""
        return True

    def check_if_io_connected(self) -> bool:
        """Check if connected to the local filesystem (always returns True)."""
        return True

    def get_connection_client_parameters(self) -> dict:
        """Get connection client parameters (empty for local filesystem)."""
        client_parameters: dict[Any,Any] = {}
        return client_parameters

    #================================================================
    # File operations

    def _native_put_object_from_stream(self,
                   destination_path: UPath,
                   source_stream: IO,
                   length: int,
                   encrypt: Optional[bool] = False,
                   decrypt: Optional[bool] = False,
                   compress: Optional[bool] = False,
                   decompress: Optional[bool] = False
                   ) -> bool|Any:
        """Put an object to local filesystem from a stream."""

        # Ensure parent directory exists
        self.prepare_path_parent(destination_path)

        with self.open_write_binarystream(destination_path=destination_path) as destination_stream:
            self.copy_stream_to_stream(
                source_stream=source_stream,
                destination_stream=destination_stream,
                encrypt=encrypt,
                decrypt=decrypt,
                compress=compress,
                decompress=decompress
            )

        return True

    def _native_put_object_from_path(self,
                   destination_path: UPath,
                   source_path: UPath,
                   **kwargs
                   ) -> bool:
        """Put an object to local filesystem from a local path."""

        self.check_kwargs_for_compression_encryption("_native_put_object_from_path", **kwargs)

        # Ensure parent directory exists
        self.prepare_path_parent(destination_path)

        try:
            shutil.copyfile(src=source_path, dst=destination_path)
            return True
        except Exception as e:
            print(f"Error copying file from {source_path} to {destination_path}: {e}")
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
        """Get an object from local filesystem to a stream."""

        try:
            with self.open_read_binarystream(source_path=source_path) as source_stream:
                self.copy_stream_to_stream(
                    source_stream=source_stream,
                    destination_stream=destination_stream,
                    encrypt=encrypt,
                    decrypt=decrypt,
                    compress=compress,
                    decompress=decompress
                )
            return True
        except Exception as e:
            print(f"Error getting object from {source_path} to stream: {e}")
            return False

    def _native_get_object_to_path(self,
                   source_path: UPath,
                   destination_path: UPath,
                   **kwargs
                   ) -> bool|Any:
        """Get an object from local filesystem to a local path."""

        self.check_kwargs_for_compression_encryption("_native_get_object_to_path", **kwargs)

        # Ensure parent directory exists
        self.prepare_path_parent(destination_path)

        try:
            shutil.copyfile(src=source_path, dst=destination_path)
            return True
        except Exception as e:
            print(f"Error copying file from {source_path} to {destination_path}: {e}")
            return False

    #================================================================
    # Stream operations - Basic implementations

    def read_from_binarystream(self, source_path: Union[UPath,str], destination_stream: Any, **kwargs) -> bool:
        """Read data from a local file to a binary stream."""
        try:
            u_path = PathHelper.format_path(source_path)
            if not u_path or not u_path.exists():
                return False

            with open(u_path, 'rb') as source_file:
                shutil.copyfileobj(source_file, destination_stream)
            return True
        except Exception as e:
            print(f"Error reading from binary stream: {e}")
            return False

    def write_to_binarystream(self, destination_path: Union[UPath,str], source_stream: Any, **kwargs) -> bool:
        """Write data from a binary stream to a local file."""
        try:
            u_path = PathHelper.format_path(destination_path)
            if not u_path:
                return False

            # Ensure parent directory exists
            self.prepare_path_parent(u_path)

            with open(u_path, 'wb') as destination_file:
                shutil.copyfileobj(source_stream, destination_file)
            return True
        except Exception as e:
            print(f"Error writing to binary stream: {e}")
            return False

    #================================================================
    # Filesystem operations

    def list_sources(self, path: Optional[Union[str, UPath]], pattern: Optional[str] = "*",
                    recursive: bool = True, include_files: bool = True, include_dirs: bool = False, **kwargs) -> List[UPath]:
            """
            List available data sources in the specified path or directory.

            Args:
                path: Path to list sources from
                pattern: Glob pattern to match (default: "*")
                recursive: Whether to list files recursively (default: True)
                include_files: Whether to include files in the results (default: True)
                include_dirs: Whether to include directories in the results (default: True)

            Returns:
                List of paths as strings
            """
            u_path: UPath|None = PathHelper.format_path(path)

            if not u_path or not u_path.exists():
                return []

            if u_path.is_file():
                return [str(u_path)] if include_files else []

            try:
                # Choose glob function based on recursive flag
                glob_func = u_path.rglob if recursive else u_path.glob

                # Get all paths matching the pattern
                all_paths = list(glob_func(pattern))

                # Filter based on include_files and include_dirs flags
                filtered_paths = []
                for p in all_paths:
                    if p.is_file() and include_files:
                        filtered_paths.append(UPath(p))
                    elif p.is_dir() and include_dirs:
                        filtered_paths.append(UPath(p))

                return filtered_paths
            except Exception as e:
                print(f"Error listing sources: {e}")
                return []

    def get_size(self, path: Optional[Union[str, UPath]]) -> int:
        """
        Get the size of the data at the specified path.

        Args:
            path: Path to get size for

        Returns:
            Size in bytes or 0 if path doesn't exist
        """
        u_path: UPath|None = PathHelper.format_path(path)

        if not u_path or not u_path.exists():
            return 0

        try:
            if u_path.is_file():
                return os.path.getsize(u_path)
            elif u_path.is_dir():
                # For directories, sum up sizes of all contained files
                total_size = 0
                for dirpath, _, filenames in os.walk(u_path):
                    for filename in filenames:
                        file_path = os.path.join(dirpath, filename)
                        total_size += os.path.getsize(file_path)
                return total_size
            return 0
        except Exception as e:
            print(f"Error getting size: {e}")
            return 0

    def calculate_checksum(self, path: Optional[Union[str, UPath]], algorithm: str = 'sha256') -> Optional[str]:
        """
        Calculate the checksum of the data at the specified path.

        Args:
            path: Path to calculate checksum for
            algorithm: Hash algorithm to use (default: sha256)

        Returns:
            Checksum string or None if path doesn't exist
        """
        u_path: UPath|None = PathHelper.format_path(path)

        if not u_path or not u_path.exists() or not u_path.is_file():
            return None

        try:
            hash_alg = hashlib.new(algorithm)
            with open(u_path, 'rb') as file:
                for chunk in iter(lambda: file.read(4096), b""):
                    hash_alg.update(chunk)
            return hash_alg.hexdigest()
        except Exception as e:
            print(f"Error calculating checksum: {e}")
            return None

    def get_file_raw_metadata(self, path: Union[str, UPath]) -> List[Dict]:
        """
        Get the raw file metadata of the data at the specified path.

        Args:
            path: Path to get metadata for

        Returns:
            List of raw metadata dictionaries
        """
        u_path: UPath|None = PathHelper.format_path(path)

        if not u_path:
            return []

        results = []

        try:
            if u_path.exists():
                if u_path.is_file():
                    # Get metadata for a single file
                    stat_info = os.stat(u_path)

                    metadata = {
                        'path': str(u_path),
                        'size': stat_info.st_size,
                        'last_modified': datetime.datetime.fromtimestamp(stat_info.st_mtime),
                        'created': datetime.datetime.fromtimestamp(stat_info.st_ctime),
                        'is_dir': False,
                        'permissions': stat_info.st_mode,
                        'uid': stat_info.st_uid,
                        'gid': stat_info.st_gid
                    }
                    results.append(metadata)

                elif u_path.is_dir():
                    # Get metadata for all files in directory
                    for entry in u_path.glob('*'):
                        stat_info = os.stat(entry)

                        metadata = {
                            'path': str(entry),
                            'size': stat_info.st_size,
                            'last_modified': datetime.datetime.fromtimestamp(stat_info.st_mtime),
                            'created': datetime.datetime.fromtimestamp(stat_info.st_ctime),
                            'is_dir': entry.is_dir(),
                            'permissions': stat_info.st_mode,
                            'uid': stat_info.st_uid,
                            'gid': stat_info.st_gid
                        }
                        results.append(metadata)

            return results
        except Exception as e:
            print(f"Error getting file metadata: {e}")
            return []

    def conform_file_metadata(self, raw_metadata: List[Dict]) -> List[FileMetadata]:
        """
        Transform raw local file metadata into a standardized format.

        Args:
            raw_metadata: List of raw metadata dictionaries

        Returns:
            List of FileMetadata objects
        """
        conformed_metadata = []

        for item in raw_metadata:
            # Extract path components
            full_path = item.get('path', '')
            path_obj = Path(full_path)
            filename = path_obj.name
            directory = str(path_obj.parent)

            # Convert permissions to string representation similar to ls -l
            permissions = item.get('permissions', 0)
            permission_str = ''
            if item.get('is_dir', False):
                permission_str += 'd'
            else:
                permission_str += '-'

            permission_str += 'r' if permissions & stat.S_IRUSR else '-'
            permission_str += 'w' if permissions & stat.S_IWUSR else '-'
            permission_str += 'x' if permissions & stat.S_IXUSR else '-'
            permission_str += 'r' if permissions & stat.S_IRGRP else '-'
            permission_str += 'w' if permissions & stat.S_IWGRP else '-'
            permission_str += 'x' if permissions & stat.S_IXGRP else '-'
            permission_str += 'r' if permissions & stat.S_IROTH else '-'
            permission_str += 'w' if permissions & stat.S_IWOTH else '-'
            permission_str += 'x' if permissions & stat.S_IXOTH else '-'

            # Create a FileMetadata object
            conformed_item = FileMetadata(
                filename=filename,
                directory=directory,
                full_path=full_path,
                size=item.get('size', 0),
                last_modified=item.get('last_modified'),
                etag=None,  # Local files don't have ETags
                storage_class=None,  # No storage class for local files
                checksum=None,  # Would need to calculate separately
                source='local',
                additional={
                    'permissions': permission_str,
                    'created': item.get('created'),
                    'uid': item.get('uid'),
                    'gid': item.get('gid'),
                    'is_dir': item.get('is_dir', False)
                }
            )

            conformed_metadata.append(conformed_item)

        return conformed_metadata

    def get_file_metadata(self, path: Union[str, UPath]) -> List[FileMetadata]:
        """
        Get standardized file metadata for files at the specified path.

        Args:
            path: Path to get metadata for

        Returns:
            List of FileMetadata objects
        """
        # Get raw metadata
        raw_metadata = self.get_file_raw_metadata(path)

        # Transform to conformed metadata
        return self.conform_file_metadata(raw_metadata)

    def path_exists(self, path: Optional[Union[str, UPath]]) -> bool:
        """
        Checks if the specified path exists.

        Args:
            path: Path to check

        Returns:
            True if path exists, False otherwise
        """
        u_path: UPath|None = PathHelper.format_path(path)

        if not u_path:
            return False

        return u_path.exists()

    def path_is_dir(self, path: Optional[Union[str, UPath]]) -> bool:
        """
        Checks if the specified path is a directory.

        Args:
            path: Path to check

        Returns:
            True if path is a directory, False otherwise
        """
        u_path: UPath|None = PathHelper.format_path(path)

        if not u_path:
            return False

        return u_path.is_dir()

    def path_is_file(self, path: Optional[Union[str, UPath]]) -> bool:
        """
        Checks if the specified path is a file.

        Args:
            path: Path to check

        Returns:
            True if path is a file, False otherwise
        """
        u_path: UPath|None = PathHelper.format_path(path)

        if not u_path:
            return False

        return u_path.is_file()

    def create_directory(self, path: Optional[Union[str, UPath]]) -> bool:
        """
        Creates a directory if it does not exist.

        Args:
            path: Directory path to create

        Returns:
            True if the directory was created or already exists, False otherwise
        """
        u_path: Optional[UPath] = PathHelper.format_path(path)

        if not u_path:
            print(f"Error creating local directory: Invalid path {path}")
            return False

        try:
            u_path.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as e:
            print(f"Error creating local directory: {u_path} - {e}")
            return False

    def prepare_path_parent(self, path: Union[str, UPath]) -> bool:
        """
        Creates the parent directory of a path if it doesn't exist.

        Args:
            path: Path whose parent directory should be created

        Returns:
            True if the parent directory exists or was created, False otherwise
        """
        u_path = PathHelper.format_path(path)

        if not u_path:
            return False

        parent_dir = u_path.parent

        try:
            parent_dir.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as e:
            print(f"Error creating parent directory {parent_dir}: {e}")
            return False

    def delete_file(self, path: Union[str, UPath]) -> bool:
        """
        Delete a file at the specified path.

        Args:
            path: Path to the file to delete

        Returns:
            True if file was deleted, False otherwise
        """
        u_path = PathHelper.format_path(path)

        if not u_path or not u_path.exists() or not u_path.is_file():
            return False

        try:
            os.remove(u_path)
            return True
        except OSError as e:
            print(f"Error deleting file {u_path}: {e}")
            return False

    def delete_directory(self, path: Union[str, UPath], recursive: bool = False) -> bool:
        """
        Delete a directory at the specified path.

        Args:
            path: Path to the directory to delete
            recursive: If True, recursively delete contents

        Returns:
            True if directory was deleted, False otherwise
        """
        u_path = PathHelper.format_path(path)

        if not u_path or not u_path.exists() or not u_path.is_dir():
            return False

        try:
            if recursive:
                shutil.rmtree(u_path)
            else:
                os.rmdir(u_path)  # Will only work if directory is empty
            return True
        except OSError as e:
            print(f"Error deleting directory {u_path}: {e}")
            return False

    def rename(self, source_path: Union[str, UPath], destination_path: Union[str, UPath]) -> bool:
        """
        Rename a file or directory.

        Args:
            source_path: Current path
            destination_path: New path

        Returns:
            True if rename was successful, False otherwise
        """
        src_path = PathHelper.format_path(source_path)
        dst_path = PathHelper.format_path(destination_path)

        if not src_path or not dst_path or not src_path.exists():
            return False

        try:
            # Ensure parent directory of destination exists
            self.prepare_path_parent(dst_path)

            # Perform the rename
            os.rename(src_path, dst_path)
            return True
        except OSError as e:
            print(f"Error renaming {src_path} to {dst_path}: {e}")
            return False
