"""
Shared test fixtures and configuration for mountainash-utils-files tests.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator
from unittest.mock import Mock, patch

from mountainash_settings import SettingsParameters
from mountainash_utils_files.settings.providers import LocalStorageAuthSettings, SSHStorageAuthSettings
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE


@pytest.fixture
def local_auth_params() -> SettingsParameters:
    """Provide local storage authentication parameters."""
    return SettingsParameters.create(
        namespace="local",
        settings_class=LocalStorageAuthSettings
    )


@pytest.fixture
def temp_directory() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    try:
        yield Path(temp_dir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_file(temp_directory: Path, sample_text_content: str) -> Path:
    """Create a temporary file for tests."""
    temp_file = temp_directory / "test_file.txt"
    temp_file.write_text(sample_text_content)
    return temp_file


@pytest.fixture
def sample_text_content() -> str:
    """Provide sample text content for file operations."""
    return "This is test content for file operations.\nLine 2\nLine 3"


@pytest.fixture
def sample_json_content() -> dict:
    """Provide sample JSON content for file operations."""
    return {
        "key1": "value1",
        "key2": {"nested": "value"},
        "key3": [1, 2, 3]
    }


@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing."""
    with patch('boto3.client') as mock_client:
        mock_s3 = Mock()
        mock_client.return_value = mock_s3
        yield mock_s3


@pytest.fixture
def mock_sftp_client():
    """Mock SFTP client for testing."""
    with patch('paramiko.SFTPClient') as mock_client:
        mock_sftp = Mock()
        mock_client.from_transport.return_value = mock_sftp
        yield mock_sftp


@pytest.fixture(scope="session")
def storage_systems():
    """Provide list of storage systems for parametrized tests."""
    return [
        CONST_STORAGE_PROVIDER_TYPE.LOCAL,
        CONST_STORAGE_PROVIDER_TYPE.S3,
        CONST_STORAGE_PROVIDER_TYPE.SFTP,
        CONST_STORAGE_PROVIDER_TYPE.SSH,
        CONST_STORAGE_PROVIDER_TYPE.GCS,
        CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
    ]


@pytest.fixture
def s3_auth_params() -> SettingsParameters:
    """Provide S3 storage authentication parameters."""
    from mountainash_settings.settings.auth.storage.providers.s3 import S3StorageAuthSettings

    return SettingsParameters.create(
        namespace="s3_test",
        settings_class=S3StorageAuthSettings,
        kwargs={
            "AWS_ACCESS_KEY_ID": "test_access_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret_key",
            "AWS_DEFAULT_REGION": "us-east-1",
            "S3_ENDPOINT_URL": None
        }
    )


@pytest.fixture
def ssh_auth_params() -> SettingsParameters:
    """Provide SSH storage authentication parameters."""
    return SettingsParameters.create(
        namespace="ssh_test",
        settings_class=SSHStorageAuthSettings,
        kwargs={
            "HOST": "localhost",
            "PORT": 22,
            "USERNAME": "testuser",
            "PASSWORD": "testpassword123",
            "AUTH_METHOD": "password",
            "STRICT_HOST_KEY_CHECKING": False
        }
    )


@pytest.fixture
def ssh_auth_params_with_key(temp_directory: Path) -> SettingsParameters:
    """Provide SSH storage auth parameters with key authentication."""
    # Create a mock SSH key file
    key_file = temp_directory / "test_ssh_key"
    key_file.write_text("-----BEGIN RSA PRIVATE KEY-----\nMOCK_KEY_CONTENT\n-----END RSA PRIVATE KEY-----")

    return SettingsParameters.create(
        namespace="ssh_test_key",
        settings_class=SSHStorageAuthSettings,
        kwargs={
            "HOST": "localhost",
            "PORT": 22,
            "USERNAME": "testuser",
            "PRIVATE_KEY_PATH": str(key_file),
            "AUTH_METHOD": "key",
            "STRICT_HOST_KEY_CHECKING": False
        }
    )


@pytest.fixture
def mock_ssh_client():
    """Mock SSH client for testing."""
    with patch('paramiko.SSHClient') as mock_client_class:
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.getpeername.return_value = ("192.168.1.1", 22)
        mock_client.get_transport.return_value = mock_transport
        mock_client.connect = Mock()
        mock_client.close = Mock()
        mock_client_class.return_value = mock_client
        yield mock_client


# Pytest configuration
pytest_plugins = ["pytest_asyncio"]


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "ssh: SSH-related tests")
    config.addinivalue_line("markers", "docker: Docker-based integration tests")
