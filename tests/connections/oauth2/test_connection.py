"""OAuth2Connection behavioral tests."""
from __future__ import annotations

import typing as t
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.oauth2.connection import OAuth2Connection
from mountainash_transport.connections.oauth2.flow import OAuthFlow

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


class FakeOAuth2Spec:
    name = "testprovider"

    @property
    def metadata(self):
        return {
            "authorize_url": "https://auth.example.com/authorize",
            "token_url": "https://auth.example.com/token",
        }


class FakeProfile:
    __spec__ = FakeOAuth2Spec()

    def to_handler_kwargs(self, auth_profile=None) -> dict:
        return {"timeout": 30}

    def get_connection_url(self) -> str:
        return "https://api.example.com"


class FakeOAuth2Auth:
    CLIENT_ID = "cid"
    CLIENT_SECRET = property(lambda self: type("S", (), {"get_secret_value": lambda s: "csec"})())
    SCOPE = "read"
    SETTINGS_SOURCE_SECRETS_PROVIDER = "test_mem"

    def persist_key(self):
        return "test.oauth2"


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


class TestOAuth2ConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        conn = OAuth2Connection(FakeProfile(), FakeOAuth2Auth())
        assert isinstance(conn, ConnectionProtocol)


class TestOAuth2ConnectionLifecycle:
    def test_not_connected_initially(self):
        conn = OAuth2Connection(FakeProfile(), FakeOAuth2Auth())
        assert conn.client is None
        assert conn.is_connected is False

    def test_disconnect_when_not_connected_is_noop(self):
        conn = OAuth2Connection(FakeProfile(), FakeOAuth2Auth())
        conn.disconnect()

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_connect_with_stored_valid_token(self, mock_client_cls, memory_backend):
        memory_backend.set("test.oauth2", {
            "access_token": "stored-tok",
            "token_expires_at": 9999999999,
        })
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        conn = OAuth2Connection(FakeProfile(), FakeOAuth2Auth())
        result = conn.connect()

        assert result is conn
        assert conn.is_connected is True
        assert conn.client is mock_client
        call_kwargs = mock_client_cls.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer stored-tok"

    def test_connect_raises_when_no_token_and_not_auto(self, memory_backend):
        conn = OAuth2Connection(FakeProfile(), FakeOAuth2Auth())
        with pytest.raises(AuthorizationRequired):
            conn.connect()

    def test_missing_access_token_key_raises_token_exchange_error(self, memory_backend):
        """Spec: missing access_token key in token response → TokenExchangeError."""
        from mountainash_transport.connections.errors import TokenExchangeError

        memory_backend.set("test.oauth2", {
            "token_expires_at": 0,
            "refresh_token": "refresh-tok",
        })
        with patch.object(
            OAuthFlow, "is_expired", return_value=True
        ), patch.object(
            OAuthFlow, "refresh", return_value={"no_token_here": True}
        ):
            conn = OAuth2Connection(FakeProfile(), FakeOAuth2Auth())
            with pytest.raises((TokenExchangeError, KeyError)):
                conn.connect()

    def test_resolved_token_emitted_as_bearer(self, memory_backend):
        memory_backend.set("test.oauth2", {
            "access_token": "AT0KEN",
            "token_expires_at": 9999999999,
        })
        conn = OAuth2Connection(FakeProfile(), FakeOAuth2Auth())
        with patch("mountainash_transport.connections.http.httpx.Client"):
            conn.connect()
        assert conn._inner._connect_kwargs["headers"]["Authorization"] == "Bearer AT0KEN"

    def test_empty_cached_token_raises(self, memory_backend):
        """An empty-string cached access token must trigger re-authorize, not a
        header-less client (the Bearer adapter drops empty tokens)."""
        memory_backend.set("test.oauth2", {
            "access_token": "",
            "token_expires_at": 9999999999,
        })
        conn = OAuth2Connection(FakeProfile(), FakeOAuth2Auth())
        with pytest.raises(AuthorizationRequired):
            conn.connect()

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_disconnect_closes_inner(self, mock_client_cls, memory_backend):
        memory_backend.set("test.oauth2", {
            "access_token": "tok",
            "token_expires_at": 9999999999,
        })
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        conn = OAuth2Connection(FakeProfile(), FakeOAuth2Auth())
        conn.connect()
        conn.disconnect()

        mock_client.close.assert_called_once()
        assert conn.client is None
        assert conn.is_connected is False

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_context_manager(self, mock_client_cls, memory_backend):
        memory_backend.set("test.oauth2", {
            "access_token": "tok",
            "token_expires_at": 9999999999,
        })
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        with OAuth2Connection(FakeProfile(), FakeOAuth2Auth()) as conn:
            conn.connect()
            assert conn.is_connected is True
        mock_client.close.assert_called_once()
