"""OAuth1Connection behavioral tests."""
from __future__ import annotations

import typing as t
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.oauth1.connection import OAuth1Connection

from mountainash_settings.secrets.registry import (
    clear_secrets_registry,
    register_secrets_backend,
)


class InMemoryBackend:
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


class FakeOAuth1Spec:
    name = "testprovider_oauth1"

    @property
    def metadata(self):
        return {
            "request_token_url": "https://auth.example.com/oauth/request_token",
            "authorize_url": "https://auth.example.com/oauth/authorize",
            "access_token_url": "https://auth.example.com/oauth/access_token",
        }


class FakeProfile:
    __spec__ = FakeOAuth1Spec()

    def to_handler_kwargs(self, auth_profile=None) -> dict:
        return {"timeout": 30}

    def get_connection_url(self) -> str:
        return "https://api.example.com"


class FakeOAuth1Auth:
    CONSUMER_KEY = "consumer_key"
    CONSUMER_SECRET = property(lambda self: type("S", (), {"get_secret_value": lambda s: "consumer_secret"})())
    SETTINGS_SOURCE_SECRETS_PROVIDER = "test_mem"

    def persist_key(self):
        return "test.oauth1"


@pytest.fixture(autouse=True)
def clean_secrets():
    clear_secrets_registry()
    yield
    clear_secrets_registry()


@pytest.fixture
def memory_backend():
    b = InMemoryBackend()
    register_secrets_backend("test_mem", b)
    return b


class TestOAuth1ConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        conn = OAuth1Connection(FakeProfile(), FakeOAuth1Auth())
        assert isinstance(conn, ConnectionProtocol)


class TestOAuth1ConnectionLifecycle:
    def test_not_connected_initially(self):
        conn = OAuth1Connection(FakeProfile(), FakeOAuth1Auth())
        assert conn.client is None
        assert conn.is_connected is False

    def test_connect_raises_when_no_token_and_not_auto(self, memory_backend):
        conn = OAuth1Connection(FakeProfile(), FakeOAuth1Auth())
        with pytest.raises(AuthorizationRequired):
            conn.connect()

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_connect_with_stored_tokens(self, mock_client_cls, memory_backend):
        import sys
        mock_oauth1_module = MagicMock()
        mock_oauth1_module.OAuth1Auth = MagicMock()
        sys.modules["authlib.integrations.httpx_client.oauth1_client"] = mock_oauth1_module
        try:
            memory_backend.set("test.oauth1", {
                "oauth_token": "stored-tok",
                "oauth_token_secret": "stored-secret",
            })
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client

            conn = OAuth1Connection(FakeProfile(), FakeOAuth1Auth())
            result = conn.connect()

            assert result is conn
            assert conn.is_connected is True
            assert conn.client is mock_client
            call_kwargs = mock_client_cls.call_args[1]
            assert "auth" in call_kwargs
        finally:
            sys.modules.pop("authlib.integrations.httpx_client.oauth1_client", None)

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_disconnect_closes_inner(self, mock_client_cls, memory_backend):
        import sys
        mock_oauth1_module = MagicMock()
        mock_oauth1_module.OAuth1Auth = MagicMock()
        sys.modules["authlib.integrations.httpx_client.oauth1_client"] = mock_oauth1_module
        try:
            memory_backend.set("test.oauth1", {
                "oauth_token": "tok",
                "oauth_token_secret": "sec",
            })
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client

            conn = OAuth1Connection(FakeProfile(), FakeOAuth1Auth())
            conn.connect()
            conn.disconnect()

            mock_client.close.assert_called_once()
            assert conn.is_connected is False
        finally:
            sys.modules.pop("authlib.integrations.httpx_client.oauth1_client", None)
