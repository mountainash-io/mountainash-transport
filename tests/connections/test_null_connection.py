"""NullConnection behavioral tests — no-op connection for local filesystem."""
from __future__ import annotations

import pytest

from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.null import NullConnection


class TestNullConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        assert isinstance(NullConnection(), ConnectionProtocol)


class TestNullConnectionLifecycle:
    def test_always_connected(self):
        conn = NullConnection()
        assert conn.is_connected is True

    def test_connect_returns_self(self):
        conn = NullConnection()
        result = conn.connect()
        assert result is conn

    def test_disconnect_is_noop(self):
        conn = NullConnection()
        conn.disconnect()
        assert conn.is_connected is True

    def test_client_is_none(self):
        conn = NullConnection()
        assert conn.client is None

    def test_context_manager(self):
        with NullConnection() as conn:
            assert conn.is_connected is True
