"""
Tests for SSH_FileHelper - SSH-based file operations.
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from typing import Any

from mountainash_utils_files.file_helpers.ssh_file_helper import SSH_FileHelper
from mountainash_utils_files.file_helpers.base_file_helper import Base_FileHelper
from mountainash_settings import SettingsParameters
from mountainash_settings.settings.auth.storage.providers.ssh import SSHStorageAuthSettings


@pytest.mark.unit
@pytest.mark.ssh
class TestSSH_FileHelper:
    """Unit tests for SSH_FileHelper."""

    def test_ssh_helper_initialization(self, ssh_auth_params):
        """Test SSH_FileHelper can be initialized with auth parameters."""
        helper = SSH_FileHelper(ssh_auth_params)
        
        assert isinstance(helper, SSH_FileHelper)
        assert isinstance(helper, Base_FileHelper)
        assert helper.ssh_hostname == "localhost"
        assert helper.ssh_port == 22
        assert helper.ssh_username == "testuser"
        assert helper.ssh_password == "testpassword123"
        assert helper.requires_ssh_connection is True
        assert helper.requires_io_connection is False

    def test_ssh_helper_supports_expected_operations(self, ssh_auth_params):
        """Test SSH_FileHelper declares support for expected operations."""
        helper = SSH_FileHelper(ssh_auth_params)
        
        assert helper.supports_get_to_stream is True
        assert helper.supports_put_from_stream is True
        assert helper.supports_get_to_local_path is True
        assert helper.supports_put_from_local_path is True
        assert helper.supports_directories is True

    def test_connect_delegates_to_connect_ssh(self, ssh_auth_params):
        """Test connect method delegates to connect_ssh."""
        helper = SSH_FileHelper(ssh_auth_params)
        
        with patch.object(helper, 'connect_ssh', return_value=True) as mock_connect_ssh:
            result = helper.connect()
            
            assert result is True
            mock_connect_ssh.assert_called_once()

    def test_check_if_io_connected_delegates_to_ssh(self, ssh_auth_params):
        """Test check_if_io_connected delegates to check_if_ssh_connected."""
        helper = SSH_FileHelper(ssh_auth_params)
        
        with patch.object(helper, 'check_if_ssh_connected', return_value=True) as mock_check_ssh:
            result = helper.check_if_io_connected()
            
            assert result is True
            mock_check_ssh.assert_called_once()

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.subprocess.run')
    def test_put_to_path_uses_rsync(self, mock_subprocess_run, ssh_auth_params):
        """Test put_to_path uses rsync for file transfer."""
        mock_result = Mock()
        mock_result.stdout = "Transfer successful"
        mock_subprocess_run.return_value = mock_result
        
        # This is a static method, so we can test it directly
        SSH_FileHelper.put_to_path("/local/file.txt", "/remote/file.txt", "testhost", "testuser")
        
        import subprocess
        mock_subprocess_run.assert_called_once_with(
            ["rsync", "-avz", "-e", "ssh", "/local/file.txt", "testuser@testhost:/remote/file.txt"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.subprocess.run')
    def test_get_from_path_uses_rsync(self, mock_subprocess_run, ssh_auth_params):
        """Test get_from_path uses rsync for file retrieval."""
        mock_result = Mock()
        mock_result.stdout = "Transfer successful"
        mock_subprocess_run.return_value = mock_result
        
        # This is a static method, so we can test it directly
        SSH_FileHelper.get_from_path("testhost", "/remote/file.txt", "/local/file.txt", "testuser")
        
        import subprocess
        mock_subprocess_run.assert_called_once_with(
            ["rsync", "-avz", "-e", "ssh", "testuser@testhost:/remote/file.txt", "/local/file.txt"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.open')
    def test_read_data_opens_file_correctly(self, mock_open, ssh_auth_params):
        """Test read_data opens and reads file with smart_open."""
        mock_file = Mock()
        mock_file.read.return_value = "test content"
        mock_open.return_value.__enter__.return_value = mock_file
        
        result = SSH_FileHelper.read_data("ssh://user@host/path/file.txt")
        
        assert result == "test content"
        mock_open.assert_called_once_with("ssh://user@host/path/file.txt", "r")
        mock_file.read.assert_called_once()

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.open')
    def test_read_data_with_binary_mode(self, mock_open, ssh_auth_params):
        """Test read_data with binary mode."""
        mock_file = Mock()
        mock_file.read.return_value = b"binary content"
        mock_open.return_value.__enter__.return_value = mock_file
        
        result = SSH_FileHelper.read_data("ssh://user@host/path/file.bin", mode="rb")
        
        assert result == b"binary content"
        mock_open.assert_called_once_with("ssh://user@host/path/file.bin", "rb")

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.open')
    def test_write_data_opens_file_correctly(self, mock_open, ssh_auth_params):
        """Test write_data opens and writes file with smart_open."""
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        SSH_FileHelper.write_data("ssh://user@host/path/file.txt", "test content")
        
        mock_open.assert_called_once_with("ssh://user@host/path/file.txt", "w")
        mock_file.write.assert_called_once_with("test content")

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.open')
    def test_write_data_with_binary_mode(self, mock_open, ssh_auth_params):
        """Test write_data with binary mode."""
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        SSH_FileHelper.write_data("ssh://user@host/path/file.bin", b"binary content", mode="wb")
        
        mock_open.assert_called_once_with("ssh://user@host/path/file.bin", "wb")
        mock_file.write.assert_called_once_with(b"binary content")

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.UPath')
    def test_list_sources_uses_upath_glob(self, mock_upath_class, ssh_auth_params):
        """Test list_sources uses UPath glob functionality."""
        helper = SSH_FileHelper(ssh_auth_params)
        
        mock_path = Mock()
        mock_path.glob.return_value = [Path("file1.txt"), Path("file2.txt")]
        mock_upath_class.return_value = mock_path
        
        result = helper.list_sources("ssh://user@host/path/")
        
        assert result == [Path("file1.txt"), Path("file2.txt")]
        mock_upath_class.assert_called_once_with("ssh://user@host/path/")
        mock_path.glob.assert_called_once_with("*")

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.UPath')
    def test_list_sources_with_pattern(self, mock_upath_class, ssh_auth_params):
        """Test list_sources with custom pattern."""
        helper = SSH_FileHelper(ssh_auth_params)
        
        mock_path = Mock()
        mock_path.glob.return_value = [Path("data1.txt"), Path("data2.txt")]
        mock_upath_class.return_value = mock_path
        
        result = helper.list_sources("ssh://user@host/path/", pattern="data*.txt")
        
        assert result == [Path("data1.txt"), Path("data2.txt")]
        mock_path.glob.assert_called_once_with("data*.txt")

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.os.path.getsize')
    def test_get_size_uses_os_getsize(self, mock_getsize, ssh_auth_params):
        """Test get_size uses os.path.getsize."""
        helper = SSH_FileHelper(ssh_auth_params)
        mock_getsize.return_value = 1024
        
        result = helper.get_size("/path/to/file.txt")
        
        assert result == 1024
        mock_getsize.assert_called_once_with("/path/to/file.txt")

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.PathHelper.format_path')
    def test_path_exists_with_valid_path(self, mock_format_path, ssh_auth_params):
        """Test path_exists returns True for existing path."""
        helper = SSH_FileHelper(ssh_auth_params)
        
        mock_upath = Mock()
        mock_upath.exists.return_value = True
        mock_format_path.return_value = mock_upath
        
        result = helper.path_exists("ssh://user@host/path/file.txt")
        
        assert result is True
        mock_format_path.assert_called_once_with("ssh://user@host/path/file.txt")
        mock_upath.exists.assert_called_once()

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.PathHelper.format_path')
    def test_path_exists_with_none_path(self, mock_format_path, ssh_auth_params):
        """Test path_exists returns False when PathHelper returns None."""
        helper = SSH_FileHelper(ssh_auth_params)
        mock_format_path.return_value = None
        
        result = helper.path_exists("invalid://path")
        
        assert result is False
        mock_format_path.assert_called_once_with("invalid://path")

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.PathHelper.format_path')
    def test_path_is_dir_with_directory(self, mock_format_path, ssh_auth_params):
        """Test path_is_dir returns True for directory."""
        helper = SSH_FileHelper(ssh_auth_params)
        
        mock_upath = Mock()
        mock_upath.is_dir.return_value = True
        mock_format_path.return_value = mock_upath
        
        result = helper.path_is_dir("ssh://user@host/path/directory/")
        
        assert result is True
        mock_format_path.assert_called_once_with("ssh://user@host/path/directory/")
        mock_upath.is_dir.assert_called_once()

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.PathHelper.format_path')
    def test_path_is_file_with_file(self, mock_format_path, ssh_auth_params):
        """Test path_is_file returns True for file."""
        helper = SSH_FileHelper(ssh_auth_params)
        
        mock_upath = Mock()
        mock_upath.is_file.return_value = True
        mock_format_path.return_value = mock_upath
        
        result = helper.path_is_file("ssh://user@host/path/file.txt")
        
        assert result is True
        mock_format_path.assert_called_once_with("ssh://user@host/path/file.txt")
        mock_upath.is_file.assert_called_once()

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.os.makedirs')
    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.PathHelper.format_path')
    def test_create_directory_creates_directory(self, mock_format_path, mock_makedirs, ssh_auth_params):
        """Test create_directory creates directory when it doesn't exist."""
        helper = SSH_FileHelper(ssh_auth_params)
        
        mock_upath = Mock()
        mock_upath.exists.return_value = False
        mock_upath.path = "/remote/new/directory"
        mock_format_path.return_value = mock_upath
        
        result = helper.create_directory("ssh://user@host/remote/new/directory")
        
        assert result is True
        mock_format_path.assert_called_once_with("ssh://user@host/remote/new/directory")
        mock_upath.exists.assert_called_once()
        mock_makedirs.assert_called_once_with(name="/remote/new/directory", exist_ok=True)

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.PathHelper.format_path')
    def test_create_directory_with_existing_directory(self, mock_format_path, ssh_auth_params):
        """Test create_directory with existing directory."""
        helper = SSH_FileHelper(ssh_auth_params)
        
        mock_upath = Mock()
        mock_upath.exists.return_value = True
        mock_format_path.return_value = mock_upath
        
        result = helper.create_directory("ssh://user@host/remote/existing/directory")
        
        assert result is True
        mock_format_path.assert_called_once()
        mock_upath.exists.assert_called_once()


@pytest.mark.unit
@pytest.mark.ssh
class TestSSH_FileHelperErrorHandling:
    """Test SSH_FileHelper error handling scenarios."""

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.subprocess.run')
    def test_put_to_path_handles_subprocess_error(self, mock_subprocess_run):
        """Test put_to_path handles subprocess errors gracefully."""
        from subprocess import CalledProcessError
        
        mock_subprocess_run.side_effect = CalledProcessError(
            returncode=1, 
            cmd=["rsync"],
            stderr="Permission denied"
        )
        
        # Should not raise exception - method handles errors internally
        SSH_FileHelper.put_to_path("/local/file.txt", "/remote/file.txt", "testhost", "testuser")
        
        mock_subprocess_run.assert_called_once()

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.subprocess.run')
    def test_get_from_path_handles_subprocess_error(self, mock_subprocess_run):
        """Test get_from_path handles subprocess errors gracefully."""
        from subprocess import CalledProcessError
        
        mock_subprocess_run.side_effect = CalledProcessError(
            returncode=1,
            cmd=["rsync"], 
            stderr="Connection refused"
        )
        
        # Should not raise exception - method handles errors internally
        SSH_FileHelper.get_from_path("testhost", "/remote/file.txt", "/local/file.txt", "testuser")
        
        mock_subprocess_run.assert_called_once()

    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.os.makedirs')
    @patch('mountainash_utils_files.file_helpers.ssh_file_helper.PathHelper.format_path')
    def test_create_directory_handles_os_error(self, mock_format_path, mock_makedirs, ssh_auth_params):
        """Test create_directory handles OS errors gracefully."""
        helper = SSH_FileHelper(ssh_auth_params)
        
        mock_upath = Mock()
        mock_upath.exists.return_value = False
        mock_upath.path = "/remote/protected/directory"
        mock_format_path.return_value = mock_upath
        
        mock_makedirs.side_effect = OSError("Permission denied")
        
        result = helper.create_directory("ssh://user@host/remote/protected/directory")
        
        assert result is False


@pytest.mark.integration
@pytest.mark.ssh
class TestSSH_FileHelperImplCompleteness:
    """Test SSH_FileHelper implementation completeness against Base_FileHelper contract."""

    def test_ssh_helper_implements_required_abstract_methods(self, ssh_auth_params):
        """Test that SSH_FileHelper implements all required abstract methods."""
        # Should be able to instantiate without TypeError
        helper = SSH_FileHelper(ssh_auth_params)
        
        # Check that key abstract methods exist
        assert hasattr(helper, 'connect')
        assert hasattr(helper, 'check_if_io_connected')
        assert hasattr(helper, 'path_exists')
        assert hasattr(helper, 'get_size')
        assert hasattr(helper, 'path_is_dir')
        assert hasattr(helper, 'path_is_file')
        assert hasattr(helper, 'create_directory')
        assert hasattr(helper, 'list_sources')