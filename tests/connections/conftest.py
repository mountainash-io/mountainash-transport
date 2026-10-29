"""Shared fixtures for connection tests."""

from __future__ import annotations

import pytest

from mountainash_settings.secrets import MemorySecretStore


@pytest.fixture
def memory_backend():
    with MemorySecretStore() as store:
        yield store
