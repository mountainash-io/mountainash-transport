"""Tests for create_connection() factory."""
from __future__ import annotations

from unittest.mock import patch

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
