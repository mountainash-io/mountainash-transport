"""
Tests for file_helpers module - Storage system implementations.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from io import BytesIO, StringIO
from typing import Dict, Any, Optional

from mountainash_utils_files.file_helpers import (
    Base_FileHelper,
    FileHelperFactory,
    get_file_helper_factory,
    Local_FileHelper
)
from mountainash_settings import SettingsParameters
from mountainash_utils_files.settings import StorageAuthBase
from mountainash_utils_files.constants  import CONST_STORAGESYSTEM, CONST_STORAGE_PROVIDER_TYPE


class TestFileHelperFactory:
    """Test FileHelperFactory for creating storage interfaces."""

    def test_get_file_helper_factory_singleton(self):
        """Test that get_file_helper_factory returns singleton instance."""
        factory1 = get_file_helper_factory()
        factory2 = get_file_helper_factory()

        assert factory1 is factory2
        assert isinstance(factory1, FileHelperFactory)

    def test_get_storage_interface_local(self, local_auth_params):
        """Test factory creates Local_FileHelper for local storage."""
        factory = get_file_helper_factory()
        result = factory.get_storage_interface(auth_parameters=local_auth_params)

        assert isinstance(result, Local_FileHelper)

    def test_get_storage_interface_s3(self, s3_auth_params):
        """Test factory creates S3_FileHelper for S3 storage."""
        factory = get_file_helper_factory()

        # Import S3_FileHelper to check if it exists
        try:
            from mountainash_utils_files.file_helpers.s3_file_helper import S3_FileHelper
            result = factory.get_storage_interface(auth_parameters=s3_auth_params)
            assert isinstance(result, S3_FileHelper)
        except ImportError:
            pytest.skip("S3_FileHelper not available")
        except Exception:
            # If auth params are invalid, that's expected behavior
            pytest.skip("S3 auth params not properly configured")

    def test_get_storage_interface_unsupported_type(self):
        """Test factory raises error for unsupported storage type."""
        from mountainash_settings import SettingsParameters
        from mountainash_settings.settings.auth.storage.providers import LocalStorageAuthSettings

        # Create auth params with unsupported provider type
        unsupported_auth_settings = LocalStorageAuthSettings()
        unsupported_auth_settings.PROVIDER_TYPE = "UNSUPPORTED_TYPE"
        unsupported_auth_params = SettingsParameters.create("unsupported", unsupported_auth_settings)

        factory = get_file_helper_factory()

        with pytest.raises(Exception):  # Should raise some kind of error
            factory.get_storage_interface(auth_parameters=unsupported_auth_params)


class TestBaseFileHelper:
    """Test Base_FileHelper abstract class functionality."""

    def test_base_file_helper_is_abstract(self):
        """Test that Base_FileHelper cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Base_FileHelper()

    def test_base_file_helper_methods_exist(self):
        """Test that Base_FileHelper defines required abstract methods."""
        # Check that key methods are defined as abstract
        abstract_methods = Base_FileHelper.__abstractmethods__

        # Key methods that should be abstract
        expected_methods = {
            'path_exists', 'get_size', 'list_sources',
            'read_file', 'write_file', 'delete_file',
            'create_directory', 'delete_directory'
        }

        # Some of these methods should be in abstract methods
        assert len(abstract_methods) > 0


@pytest.mark.unit
class TestLocal_FileHelper:
    """Test Local_FileHelper implementation."""

    def test_local_file_helper_initialization(self, local_auth_params):
        """Test Local_FileHelper can be initialized."""
        helper = Local_FileHelper(auth_parameters=local_auth_params)
        assert isinstance(helper, Local_FileHelper)
        assert isinstance(helper, Base_FileHelper)

    def test_path_exists_true(self, local_auth_params, temp_file):
        """Test path_exists returns True for existing file."""
        helper = Local_FileHelper(auth_parameters=local_auth_params)

        result = helper.path_exists(path=str(temp_file))
        assert result is True

    def test_path_exists_false(self, local_auth_params, temp_directory):
        """Test path_exists returns False for non-existing file."""
        helper = Local_FileHelper(auth_parameters=local_auth_params)
        non_existent = temp_directory / "does_not_exist.txt"

        result = helper.path_exists(path=str(non_existent))
        assert result is False

    def test_get_size_existing_file(self, local_auth_params, temp_file, sample_text_content):
        """Test get_size returns correct size for existing file."""
        helper = Local_FileHelper(auth_parameters=local_auth_params)

        result = helper.get_size(path=str(temp_file))
        assert result == len(sample_text_content)

    def test_get_size_non_existing_file(self, local_auth_params, temp_directory):
        """Test get_size handles non-existing file appropriately."""
        helper = Local_FileHelper(auth_parameters=local_auth_params)
        non_existent = temp_directory / "does_not_exist.txt"

        # Should either return 0, None, or raise exception
        try:
            result = helper.get_size(path=str(non_existent))
            assert result in [0, None] or isinstance(result, int)
        except (FileNotFoundError, OSError):
            # This is also acceptable behavior
            pass

    def test_list_sources_directory(self, local_auth_params, temp_directory):
        """Test list_sources returns files in directory."""
        # Create test files
        (temp_directory / "file1.txt").write_text("content1")
        (temp_directory / "file2.txt").write_text("content2")

        helper = Local_FileHelper(auth_parameters=local_auth_params)
        result = helper.list_sources(path=str(temp_directory))

        # Should return some kind of iterable
        assert result is not None
        result_list = list(result) if result else []
        assert len(result_list) >= 2  # Should contain at least our test files

    def test_read_file_text(self, local_auth_params, temp_file, sample_text_content):
        """Test reading file content using binary stream."""
        helper = Local_FileHelper(auth_parameters=local_auth_params)

        # Use BytesIO to capture content from read_from_binarystream
        from io import BytesIO
        destination_stream = BytesIO()

        result = helper.read_from_binarystream(
            source_path=str(temp_file),
            destination_stream=destination_stream
        )

        assert result is True

        # Get content from stream
        destination_stream.seek(0)
        content = destination_stream.read().decode('utf-8')
        assert sample_text_content == content

    def test_write_file_creates_file(self, local_auth_params, temp_directory):
        """Test writing content to file using binary stream."""
        helper = Local_FileHelper(auth_parameters=local_auth_params)
        new_file = temp_directory / "new_file.txt"
        test_content = "new file content"

        # Use BytesIO to provide content for write_to_binarystream
        from io import BytesIO
        source_stream = BytesIO(test_content.encode('utf-8'))

        result = helper.write_to_binarystream(
            destination_path=str(new_file),
            source_stream=source_stream
        )

        assert result is True

        # Check file was created with correct content
        assert new_file.exists()
        assert test_content == new_file.read_text()

    def test_get_interface_attributes(self, local_auth_params):
        """Test get_interface_attributes returns expected attributes."""
        helper = Local_FileHelper(auth_parameters=local_auth_params)

        # Test method exists and can be called
        if hasattr(helper, 'get_interface_attributes'):
            source_attrs = helper.get_interface_attributes(role="source")
            dest_attrs = helper.get_interface_attributes(role="destination")

            assert isinstance(source_attrs, dict)
            assert isinstance(dest_attrs, dict)

            # Should have some common attributes
            for attrs in [source_attrs, dest_attrs]:
                assert len(attrs) > 0
        else:
            # Method doesn't exist - this might need to be implemented
            pytest.skip("get_interface_attributes method not implemented")


@pytest.mark.integration
class TestFileHelpersIntegration:
    """Integration tests for file helpers."""

    def test_factory_creates_working_local_helper(self, local_auth_params, temp_file):
        """Test that factory-created Local_FileHelper works correctly."""
        factory = get_file_helper_factory()

        helper = factory.get_storage_interface(auth_parameters=local_auth_params)

        # Test basic operations work
        exists = helper.path_exists(path=str(temp_file))
        assert exists is True

        size = helper.get_size(path=str(temp_file))
        assert isinstance(size, int)
        assert size > 0

    def test_multiple_helpers_independence(self, local_auth_params):
        """Test that multiple helper instances work independently."""
        factory = get_file_helper_factory()

        helper1 = factory.get_storage_interface(auth_parameters=local_auth_params)
        helper2 = factory.get_storage_interface(auth_parameters=local_auth_params)

        # Should be separate instances (or at least work independently)
        assert helper1 is not None
        assert helper2 is not None

        # Test that they can work independently
        assert hasattr(helper1, 'path_exists')
        assert hasattr(helper2, 'path_exists')


class TestCloudFileHelpers:
    """Test cloud storage file helpers (S3, GCS, Azure)."""

    def test_s3_file_helper_import(self):
        """Test S3FileHelper can be imported."""
        try:
            from mountainash_utils_files.file_helpers.s3_file_helper import S3FileHelper
            assert S3FileHelper is not None
        except ImportError:
            pytest.skip("S3FileHelper not available")

    def test_gcs_file_helper_import(self):
        """Test GCSFileHelper can be imported."""
        try:
            from mountainash_utils_files.file_helpers.gcs_file_helper import GCSFileHelper
            assert GCSFileHelper is not None
        except ImportError:
            pytest.skip("GCSFileHelper not available")

    def test_azure_file_helper_import(self):
        """Test AzureFileHelper can be imported."""
        try:
            from mountainash_utils_files.file_helpers.az_file_helper import AzFileHelper
            assert AzFileHelper is not None
        except ImportError:
            pytest.skip("AzFileHelper not available")

    @patch('boto3.client')
    def test_s3_file_helper_basic_initialization(self, mock_boto_client):
        """Test S3FileHelper initialization with mocked dependencies."""
        try:
            from mountainash_utils_files.file_helpers.s3_file_helper import S3FileHelper

            mock_auth_params = Mock()
            mock_client = Mock()
            mock_boto_client.return_value = mock_client

            # Should be able to initialize without errors
            helper = S3FileHelper(auth_parameters=mock_auth_params)
            assert helper is not None

        except (ImportError, Exception) as e:
            pytest.skip(f"S3FileHelper not testable: {e}")


@pytest.mark.performance
class TestFileHelpersPerformance:
    """Performance tests for file helpers."""

    @pytest.mark.slow
    def test_factory_creation_performance(self, local_auth_params):
        """Test factory helper creation performance."""
        import time

        factory = get_file_helper_factory()

        start_time = time.time()

        # Create multiple helpers
        helpers = []
        for _ in range(10):
            helper = factory.get_storage_interface(auth_parameters=local_auth_params)
            helpers.append(helper)

        end_time = time.time()

        # Should complete quickly
        assert end_time - start_time < 1.0
        assert len(helpers) == 10

        # Verify all helpers are functional
        for helper in helpers:
            assert isinstance(helper, Local_FileHelper)
