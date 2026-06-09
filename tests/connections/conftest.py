"""Shared fixtures for connection tests."""
from __future__ import annotations

import typing as t
from contextlib import contextmanager

import pytest

from mountainash_settings.secrets.registry import (
    clear_secrets_registry,
    register_secrets_backend,
)


class FakeOAuth2Spec:
    """Duck-types ProfileSpec for OAuth2 flow tests."""
    name = "testprovider"

    def __init__(self, metadata=None):
        self._metadata = metadata or {
            "authorize_url": "https://auth.example.com/authorize",
            "token_url": "https://auth.example.com/token",
        }

    @property
    def metadata(self):
        return self._metadata


class FakeOAuth1Spec:
    """Duck-types ProfileSpec for OAuth1 flow tests."""
    name = "testprovider_oauth1"

    def __init__(self, metadata=None):
        self._metadata = metadata or {
            "request_token_url": "https://auth.example.com/oauth/request_token",
            "authorize_url": "https://auth.example.com/oauth/authorize",
            "access_token_url": "https://auth.example.com/oauth/access_token",
        }

    @property
    def metadata(self):
        return self._metadata


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


class FakeOAuth2Auth:
    """Duck-types OAuth2Auth for mixin tests."""
    CLIENT_ID = "cid"
    CLIENT_SECRET = property(lambda self: type("S", (), {"get_secret_value": lambda s: "csec"})())
    SCOPE = "read"
    SETTINGS_SOURCE_SECRETS_PROVIDER = "test_mem"

    def persist_key(self):
        return "test.oauth2"


class FakeOAuth1Auth:
    """Duck-types OAuth1Auth for mixin tests."""
    CONSUMER_KEY = "consumer_key"
    CONSUMER_SECRET = property(lambda self: type("S", (), {"get_secret_value": lambda s: "consumer_secret"})())
    SETTINGS_SOURCE_SECRETS_PROVIDER = "test_mem"

    def persist_key(self):
        return "test.oauth1"


@pytest.fixture
def fake_oauth2_spec():
    return FakeOAuth2Spec()


@pytest.fixture
def fake_oauth1_spec():
    return FakeOAuth1Spec()


@pytest.fixture
def fake_oauth2_auth():
    return FakeOAuth2Auth()


@pytest.fixture
def fake_oauth1_auth():
    return FakeOAuth1Auth()


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
