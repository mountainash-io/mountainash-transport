"""
Tests for file_interface module - Main API for unified file operations.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from mountainash_utils_files.file_interface import FileInterface
from mountainash_utils_files.file_helpers import Base_FileHelper
from mountainash_settings import SettingsParameters
from mountainash_utils_files.constants import CONST_STORAGESYSTEM


class TestFileInterface:
    """Test FileInterface main API class."""

    def test_resolve_storage_object_with_existing_object(self, local_auth_params):
        """Test resolve_storage_object returns provided object when given."""
        # Use real storage helper instead of mock
        from mountainash_utils_files.file_helpers import Local_FileHelper
        real_storage = Local_FileHelper(auth_parameters=local_auth_params)

        result = FileInterface.resolve_storage_object(obj_storage=real_storage)

        assert result is real_storage
        assert isinstance(result, Base_FileHelper)

    def test_resolve_storage_object_with_auth_parameters(self, local_auth_params):
        """Test resolve_storage_object creates storage interface from auth parameters."""
        result = FileInterface.resolve_storage_object(auth_parameters=local_auth_params)

        assert result is not None
        assert isinstance(result, Base_FileHelper)
        # Test that it's actually functional
        assert hasattr(result, 'path_exists')
        assert hasattr(result, 'get_size')

    def test_resolve_storage_object_no_parameters_raises_error(self):
        """Test resolve_storage_object raises ValueError when no parameters provided."""
        with pytest.raises(ValueError, match="No settings provided"):
            FileInterface.resolve_storage_object()

    def test_copy_path_to_path_local_to_local_success(self, local_auth_params, temp_directory, sample_text_content):
        """Test successful local to local file copy operation."""
        # Create source file
        source_file = temp_directory / "source_file.txt"
        source_file.write_text(sample_text_content)

        # Create destination path
        dest_file = temp_directory / "dest_file.txt"

        result = FileInterface.copy_path_to_path(
            source_path=str(source_file),
            destination_path=str(dest_file),
            source_auth_settings_parameters=local_auth_params,
            destination_auth_settings_parameters=local_auth_params
        )

        assert result is True
        assert dest_file.exists()
        assert dest_file.read_text() == sample_text_content

    def test_copy_path_to_path_missing_source_file(self, local_auth_params, temp_directory):
        """Test copy_path_to_path handles missing source file appropriately."""
        non_existent_source = temp_directory / "does_not_exist.txt"
        dest_file = temp_directory / "dest.txt"

        # Should either return False or raise appropriate exception
        try:
            result = FileInterface.copy_path_to_path(
                source_path=str(non_existent_source),
                destination_path=str(dest_file),
                source_auth_settings_parameters=local_auth_params,
                destination_auth_settings_parameters=local_auth_params
            )
            # If no exception, result should be False
            assert result is False
        except (FileNotFoundError, ValueError, OSError):
            # This is also acceptable behavior
            pass

    def test_copy_path_to_path_invalid_destination_directory(self, local_auth_params, temp_directory, sample_text_content):
        """Test copy_path_to_path handles invalid destination directory."""
        # Create source file
        source_file = temp_directory / "source.txt"
        source_file.write_text(sample_text_content)

        # Try to copy to invalid destination
        invalid_dest = "/root/protected/cannot_write_here.txt"  # Likely protected path

        # Should handle gracefully - either return False or raise appropriate exception
        try:
            result = FileInterface.copy_path_to_path(
                source_path=str(source_file),
                destination_path=invalid_dest,
                source_auth_settings_parameters=local_auth_params,
                destination_auth_settings_parameters=local_auth_params
            )
            # If no exception, should return False for failure
            assert result is False
        except (PermissionError, OSError, ValueError):
            # This is also acceptable behavior
            pass


@pytest.mark.unit
class TestFileInterfaceStaticMethods:
    """Test FileInterface static method functionality."""

    def test_path_exists_with_auth_parameters(self, local_auth_params, temp_file):
        """Test path_exists method with auth parameters."""
        result = FileInterface.path_exists(
            auth_parameters=local_auth_params,
            path=str(temp_file)
        )
        assert result is True

        # Test with non-existent file
        result_false = FileInterface.path_exists(
            auth_parameters=local_auth_params,
            path="/does/not/exist.txt"
        )
        assert result_false is False

    def test_get_size_with_auth_parameters(self, local_auth_params, temp_file, sample_text_content):
        """Test get_size method with auth parameters."""
        result = FileInterface.get_size(
            auth_parameters=local_auth_params,
            path=str(temp_file)
        )
        assert result == len(sample_text_content)
        assert isinstance(result, int)
        assert result > 0

    def test_list_sources_with_auth_parameters(self, local_auth_params, temp_directory):
        """Test list_sources method with auth parameters."""
        # Create test files
        (temp_directory / "file1.txt").write_text("content1")
        (temp_directory / "file2.txt").write_text("content2")
        (temp_directory / "file3.txt").write_text("content3")

        result = FileInterface.list_sources(
            auth_parameters=local_auth_params,
            path=str(temp_directory)
        )

        assert result is not None
        result_list = list(result) if result else []
        assert len(result_list) >= 3  # Should contain our test files

        # Convert to strings to check filenames
        file_names = [str(f) for f in result_list]
        assert any("file1.txt" in name for name in file_names)
        assert any("file2.txt" in name for name in file_names)
        assert any("file3.txt" in name for name in file_names)


@pytest.mark.integration
class TestFileInterfaceIntegration:
    """Integration tests for FileInterface with real file operations."""

    def test_local_file_operations_integration(self, local_auth_params, temp_directory, sample_text_content):
        """Test FileInterface with local file operations."""
        test_file = temp_directory / "integration_test.txt"
        test_file.write_text(sample_text_content)

        # Test path exists
        if hasattr(FileInterface, 'path_exists'):
            exists = FileInterface.path_exists(
                auth_parameters=local_auth_params,
                path=str(test_file)
            )
            assert exists is True

        # Test get size
        if hasattr(FileInterface, 'get_size'):
            size = FileInterface.get_size(
                auth_parameters=local_auth_params,
                path=str(test_file)
            )
            assert size == len(sample_text_content)

    def test_directory_listing_integration(self, local_auth_params, temp_directory):
        """Test directory listing functionality."""
        # Create test files
        (temp_directory / "file1.txt").write_text("content1")
        (temp_directory / "file2.txt").write_text("content2")

        if hasattr(FileInterface, 'list_sources'):
            files = FileInterface.list_sources(
                auth_parameters=local_auth_params,
                path=str(temp_directory)
            )

            # Files should be in the listing
            file_names = [str(f) for f in files] if files else []
            assert any("file1.txt" in name for name in file_names)
            assert any("file2.txt" in name for name in file_names)


@pytest.mark.performance
class TestFileInterfacePerformance:
    """Performance tests for FileInterface operations."""

    @pytest.mark.slow
    def test_large_file_handling_performance(self, local_auth_params, temp_directory):
        """Test performance with larger files."""
        # Create a moderately large test file
        large_content = "test content\n" * 1000
        large_file = temp_directory / "large_test.txt"
        large_file.write_text(large_content)

        import time
        start_time = time.time()

        # Test path exists performance
        exists = FileInterface.path_exists(
            auth_parameters=local_auth_params,
            path=str(large_file)
        )

        # Test get size performance
        size = FileInterface.get_size(
            auth_parameters=local_auth_params,
            path=str(large_file)
        )

        end_time = time.time()

        # Should complete within reasonable time (1 second)
        assert end_time - start_time < 1.0
        assert exists is True
        assert size == len(large_content)
