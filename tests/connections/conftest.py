"""Shared fixtures for connection tests."""
from __future__ import annotations

import typing as t
from contextlib import contextmanager

import pytest

from mountainash_settings.secrets.registry import (
    clear_secrets_registry,
    register_secrets_backend,
)


class InMemoryBackend:
    """Minimal SecretsBackend for testing."""

    def __init__(self):
        self._store: dict[str, dict[str, t.Any]] = {}

    def get(self, key: str) -> dict[str, t.Any] | None:
        return self._store.get(key)

    def set(self, key: str, data: dict[str, t.Any]) -> None:
        self._store[key] = data

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    @contextmanager
    def transaction(self, key: str):
        yield


@pytest.fixture(autouse=True)
def clean_secrets_registry():
    clear_secrets_registry()
    yield
    clear_secrets_registry()


@pytest.fixture
def memory_backend():
    b = InMemoryBackend()
    register_secrets_backend("test_mem", b)
    return b
