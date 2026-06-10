"""HTTPConnection behavioral tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import httpx

from mountainash_transport._core.auth.strategies import (
    AuthStrategy,
    BearerTokenStrategy,
    NoAuthStrategy,
)
from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.http import HTTPConnection


FAKE_HTTP_KWARGS: dict = {"timeout": 30, "follow_redirects": True}


class TestHTTPConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        conn = HTTPConnection(FAKE_HTTP_KWARGS, NoAuthStrategy())
        assert isinstance(conn, ConnectionProtocol)


class TestHTTPConnectionLifecycle:
    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_connect_creates_client(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        conn = HTTPConnection(FAKE_HTTP_KWARGS, NoAuthStrategy())
        result = conn.connect()

        mock_client_cls.assert_called_once_with(timeout=30, follow_redirects=True)
        assert conn.client is mock_client
        assert conn.is_connected is True
        assert result is conn

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_disconnect_closes_client(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        conn = HTTPConnection(FAKE_HTTP_KWARGS, NoAuthStrategy())
        conn.connect()
        conn.disconnect()

        mock_client.close.assert_called_once()
        assert conn.client is None
        assert conn.is_connected is False

    def test_not_connected_initially(self):
        conn = HTTPConnection(FAKE_HTTP_KWARGS, NoAuthStrategy())
        assert conn.client is None
        assert conn.is_connected is False

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_disconnect_when_not_connected_is_noop(self, mock_client_cls):
        conn = HTTPConnection(FAKE_HTTP_KWARGS, NoAuthStrategy())
        conn.disconnect()  # should not raise

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_context_manager(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        conn = HTTPConnection(FAKE_HTTP_KWARGS, NoAuthStrategy())
        with conn:
            conn.connect()
            assert conn.is_connected is True
        mock_client.close.assert_called_once()


class TestHTTPConnectionAuth:
    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_bearer_token_injected(self, mock_client_cls):
        strategy = BearerTokenStrategy("my-token")
        conn = HTTPConnection(FAKE_HTTP_KWARGS, strategy)
        conn.connect()

        call_kwargs = mock_client_cls.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer my-token"
        assert call_kwargs["timeout"] == 30

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_no_auth_no_headers(self, mock_client_cls):
        conn = HTTPConnection(FAKE_HTTP_KWARGS, NoAuthStrategy())
        conn.connect()

        call_kwargs = mock_client_cls.call_args[1]
        assert "headers" not in call_kwargs or "Authorization" not in call_kwargs.get("headers", {})


class TestHTTPConnectionErrorWrapping:
    """Spec requires raw httpx exceptions mapped at the connection boundary."""

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_timeout_wrapped_as_connection_timeout_error(self, mock_client_cls):
        from mountainash_transport.connections.errors import ConnectionTimeoutError

        mock_client_cls.side_effect = httpx.TimeoutException("timed out")
        conn = HTTPConnection(FAKE_HTTP_KWARGS, NoAuthStrategy())
        with pytest.raises(ConnectionTimeoutError):
            conn.connect()

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_connect_error_wrapped_as_transport_connection_error(self, mock_client_cls):
        from mountainash_transport.connections.errors import TransportConnectionError

        mock_client_cls.side_effect = httpx.ConnectError("refused")
        conn = HTTPConnection(FAKE_HTTP_KWARGS, NoAuthStrategy())
        with pytest.raises(TransportConnectionError):
            conn.connect()
