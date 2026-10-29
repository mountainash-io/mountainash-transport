"""Isolate example subprocesses from host configuration."""

import os

import pytest


@pytest.fixture
def example_environment() -> dict[str, str]:
    """Drop inputs that could change example output; keep subprocess coverage settings."""
    environment = {
        key: value for key, value in os.environ.items()
        if key.upper() not in {
            "MOUNTAINASH_PROFILES_CONFIG", "PYTHONPATH", "PYTHONHOME",
            "PYTHONOPTIMIZE", "PYTEST_ADDOPTS", "PYTEST_PLUGINS",
        }
        and not key.upper().startswith(("AWS_", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"))
    }
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return environment
