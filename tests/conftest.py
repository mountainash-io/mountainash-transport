"""Shared test fixtures for mountainash-transport tests."""
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator

from mountainash_transport import StorageFacade


@pytest.fixture
def temp_directory() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    try:
        yield Path(temp_dir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_file(temp_directory: Path) -> Path:
    """Create a temporary file for tests."""
    temp_file = temp_directory / "test_file.txt"
    temp_file.write_text("This is test content for file operations.\nLine 2\nLine 3")
    return temp_file


@pytest.fixture
def local_facade() -> StorageFacade:
    """Provide a local storage facade."""
    return StorageFacade.for_local()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "ssh: SSH-related tests")
    config.addinivalue_line("markers", "docker: Docker-based integration tests")
