"""Tests for create_connection() factory."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mountainash_transport.connections import create_connection
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.connections.null import NullConnection
from mountainash_transport._core.protocols import ConnectionProtocol


class FakeHTTPProfile:
    class __spec__:
        provider_type = "http"

    def to_handler_kwargs(self) -> dict:
        return {"timeout": 30}

    def get_connection_url(self) -> str:
        return "https://example.com"


class FakeLocalProfile:
    class __spec__:
        provider_type = "local"

    def to_handler_kwargs(self) -> dict:
        return {}

    def get_connection_url(self) -> str:
        return "/tmp"


class TestCreateConnection:
    def test_returns_connection_protocol(self):
        conn = create_connection(FakeHTTPProfile())
        assert isinstance(conn, ConnectionProtocol)

    def test_http_profile_returns_http_connection(self):
        conn = create_connection(FakeHTTPProfile())
        assert isinstance(conn, HTTPConnection)

    def test_local_profile_returns_null_connection(self):
        conn = create_connection(FakeLocalProfile())
        assert isinstance(conn, NullConnection)

    def test_no_auth_defaults_to_no_auth_strategy(self):
        conn = create_connection(FakeHTTPProfile())
        assert isinstance(conn, HTTPConnection)

    def test_bearer_auth(self):
        from mountainash_auth_client import TokenAuth
        conn = create_connection(FakeHTTPProfile(), auth_profile=TokenAuth(TOKEN="tok"))
        assert isinstance(conn, HTTPConnection)

    def test_oauth2_returns_oauth2_connection(self):
        from mountainash_auth_client import OAuth2AuthCodeAuth
        from mountainash_transport.connections.oauth2.connection import OAuth2Connection
        auth = OAuth2AuthCodeAuth(
            CLIENT_ID="cid",
            CLIENT_SECRET="csec",
            SCOPE="read",
            SETTINGS_SOURCE_SECRETS_PROVIDER="test",
        )
        conn = create_connection(FakeHTTPProfile(), auth_profile=auth)
        assert isinstance(conn, OAuth2Connection)


from mountainash_transport.connections.sftp import SFTPConnection
from mountainash_transport.connections.tunnel import TunnelledConnection


class FakeSFTPProfile:
    class __spec__:
        provider_type = "sftp"

    def to_handler_kwargs(self) -> dict:
        return {
            "hostname": "example.com",
            "port": 22,
            "username": "user",
            "_post_connect": {"host_key_policy": "auto_add"},
        }

    def get_connection_url(self) -> str:
        return "sftp://user@example.com:22"


class TestCreateConnectionSFTP:
    def test_sftp_profile_returns_sftp_connection(self):
        from mountainash_auth_client import PasswordAuth
        conn = create_connection(
            FakeSFTPProfile(), auth_profile=PasswordAuth(USERNAME="u", PASSWORD="p")
        )
        assert isinstance(conn, SFTPConnection)

    def test_sftp_profile_no_auth_returns_sftp_connection(self):
        conn = create_connection(FakeSFTPProfile())
        assert isinstance(conn, SFTPConnection)


class TestCreateTunnelledConnection:
    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_factory_creates_tunnelled_connection(self, mock_forwarder):
        from mountainash_transport.connections import create_tunnelled_connection

        mock_server = MagicMock()
        mock_server.server_address = ("127.0.0.1", 54321)
        mock_forwarder.return_value = mock_server

        conn = create_tunnelled_connection(
            bastion_profile=FakeSFTPProfile(),
            bastion_auth=None,
            target_profile=FakeHTTPProfile(),
            target_auth=None,
            remote_host="internal.api",
            remote_port=8080,
        )
        assert isinstance(conn, TunnelledConnection)
