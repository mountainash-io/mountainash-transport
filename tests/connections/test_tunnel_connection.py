"""TunnelledConnection behavioral tests."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.errors import TransportConnectionError
from mountainash_transport.connections.tunnel import (
    TunnelledConnection,
    _PatchedEndpointProfile,
)


def _make_mock_ssh():
    """Return (ssh_mock, transport_mock) with is_connected=False initially."""
    ssh = MagicMock()
    ssh.is_connected = False
    mock_transport = MagicMock()
    ssh.client.get_transport.return_value = mock_transport
    return ssh, mock_transport


def _make_mock_server(port: int = 54321) -> MagicMock:
    mock_server = MagicMock()
    mock_server.server_address = ("127.0.0.1", port)
    return mock_server


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestTunnelledConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        ssh, _ = _make_mock_ssh()
        conn = TunnelledConnection(ssh, lambda port: MagicMock(), "db.internal", 5432)
        assert isinstance(conn, ConnectionProtocol)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestTunnelledConnectionLifecycle:
    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_not_connected_initially(self, _mock_sf):
        ssh, _ = _make_mock_ssh()
        conn = TunnelledConnection(ssh, lambda port: MagicMock(), "db.internal", 5432)
        assert conn.client is None
        assert conn.is_connected is False
        assert conn.local_port is None

    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_connect_binds_listener_and_inner(self, mock_sf):
        mock_server = _make_mock_server(54321)
        mock_sf.return_value = mock_server

        ssh, mock_transport = _make_mock_ssh()
        ssh.is_connected = True

        inner_mock = MagicMock()
        inner_mock.is_connected = True
        factory_calls: list[int] = []

        def factory(port: int) -> MagicMock:
            factory_calls.append(port)
            return inner_mock

        conn = TunnelledConnection(ssh, factory, "db.internal", 5432)
        conn.connect()

        mock_sf.assert_called_once_with(mock_transport, "db.internal", 5432)
        assert factory_calls == [54321]
        inner_mock.connect.assert_called_once()
        assert conn.local_port == 54321
        assert conn.client is inner_mock.client
        assert conn.is_connected is True

    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_connect_connects_ssh_if_not_connected(self, mock_sf):
        mock_sf.return_value = _make_mock_server()

        ssh, _ = _make_mock_ssh()
        ssh.is_connected = False

        inner_mock = MagicMock()
        inner_mock.is_connected = True

        conn = TunnelledConnection(ssh, lambda port: inner_mock, "host", 3306)
        conn.connect()

        ssh.connect.assert_called_once()

    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_connect_skips_ssh_connect_when_already_connected(self, mock_sf):
        mock_sf.return_value = _make_mock_server()

        ssh, _ = _make_mock_ssh()
        ssh.is_connected = True

        inner_mock = MagicMock()
        inner_mock.is_connected = True

        conn = TunnelledConnection(ssh, lambda port: inner_mock, "host", 3306)
        conn.connect()

        ssh.connect.assert_not_called()

    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_disconnect_tears_down_in_order(self, mock_sf):
        mock_server = _make_mock_server()
        mock_sf.return_value = mock_server

        ssh, _ = _make_mock_ssh()
        ssh.is_connected = True

        inner_mock = MagicMock()
        inner_mock.is_connected = True
        call_order: list[str] = []

        inner_mock.disconnect.side_effect = lambda: call_order.append("inner")
        mock_server.shutdown.side_effect = lambda: call_order.append("server")
        ssh.disconnect.side_effect = lambda: call_order.append("ssh")

        conn = TunnelledConnection(ssh, lambda port: inner_mock, "host", 5432)
        conn.connect()
        conn.disconnect()

        assert call_order == ["inner", "server", "ssh"]
        assert conn.client is None
        assert conn.is_connected is False
        assert conn.local_port is None

    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_context_manager(self, mock_sf):
        mock_sf.return_value = _make_mock_server()

        ssh, _ = _make_mock_ssh()
        ssh.is_connected = True

        inner_mock = MagicMock()
        inner_mock.is_connected = True

        conn = TunnelledConnection(ssh, lambda port: inner_mock, "host", 5432)
        with conn:
            conn.connect()
            assert conn.is_connected is True

        inner_mock.disconnect.assert_called_once()
        ssh.disconnect.assert_called_once()

    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_connect_is_idempotent(self, mock_sf):
        """Second connect() tears down first, then reconnects."""
        server1 = _make_mock_server(11111)
        server2 = _make_mock_server(22222)
        mock_sf.side_effect = [server1, server2]

        ssh, _ = _make_mock_ssh()
        ssh.is_connected = True

        inner1 = MagicMock()
        inner1.is_connected = True
        inner2 = MagicMock()
        inner2.is_connected = True
        inners = [inner1, inner2]

        conn = TunnelledConnection(ssh, lambda port: inners.pop(0), "host", 5432)
        conn.connect()
        assert conn.local_port == 11111

        conn.connect()
        inner1.disconnect.assert_called_once()
        server1.shutdown.assert_called_once()
        assert conn.local_port == 22222


# ---------------------------------------------------------------------------
# Error wrapping
# ---------------------------------------------------------------------------


class TestTunnelledConnectionErrorWrapping:
    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_listener_bind_failure_raises_transport_connection_error(self, mock_sf):
        mock_sf.side_effect = OSError("address already in use")

        ssh, _ = _make_mock_ssh()
        ssh.is_connected = True

        conn = TunnelledConnection(ssh, lambda port: MagicMock(), "host", 5432)

        with pytest.raises(TransportConnectionError, match="Failed to bind tunnel listener"):
            conn.connect()


# ---------------------------------------------------------------------------
# _PatchedEndpointProfile
# ---------------------------------------------------------------------------


class TestPatchedEndpointProfile:
    def _make_inner(self, kwargs: dict) -> MagicMock:
        inner = MagicMock()
        inner.to_handler_kwargs.return_value = kwargs
        inner.some_attr = "value"
        return inner

    def test_patches_hostname_and_port(self):
        inner = self._make_inner({"hostname": "db.internal", "port": 5432, "user": "admin"})
        profile = _PatchedEndpointProfile(inner, "127.0.0.1", 54321)
        kwargs = profile.to_handler_kwargs()
        assert kwargs["hostname"] == "127.0.0.1"
        assert kwargs["port"] == 54321
        assert kwargs["user"] == "admin"

    def test_patches_base_url(self):
        inner = self._make_inner({"base_url": "https://s3.amazonaws.com", "region": "us-east-1"})
        profile = _PatchedEndpointProfile(inner, "127.0.0.1", 9000)
        kwargs = profile.to_handler_kwargs()
        assert kwargs["base_url"] == "http://127.0.0.1:9000"
        assert kwargs["region"] == "us-east-1"

    def test_patches_endpoint_url(self):
        inner = self._make_inner({"endpoint_url": "https://storage.googleapis.com"})
        profile = _PatchedEndpointProfile(inner, "127.0.0.1", 8080)
        kwargs = profile.to_handler_kwargs()
        assert kwargs["endpoint_url"] == "http://127.0.0.1:8080"

    def test_unrecognised_kwargs_pass_through(self):
        inner = self._make_inner({"driver": "postgres", "database": "mydb"})
        profile = _PatchedEndpointProfile(inner, "127.0.0.1", 5432)
        kwargs = profile.to_handler_kwargs()
        assert kwargs == {"driver": "postgres", "database": "mydb"}

    def test_delegates_other_attributes(self):
        inner = self._make_inner({})
        inner.some_attr = "delegated"
        profile = _PatchedEndpointProfile(inner, "127.0.0.1", 1234)
        assert profile.some_attr == "delegated"

    def test_get_connection_url_shows_tunnel(self):
        inner = self._make_inner({})
        profile = _PatchedEndpointProfile(inner, "127.0.0.1", 54321)
        assert profile.get_connection_url() == "tunnel://127.0.0.1:54321"


# ---------------------------------------------------------------------------
# _PatchedEndpointProfile.emit() override
# ---------------------------------------------------------------------------


class TestPatchedEndpointEmit:
    def test_emit_patches_hostname_and_port(self):
        from mountainash_auth_client.targets import TargetFamily
        from mountainash_transport.settings.storage.profiles.sftp_storage_profile import SFTPStorageProfile

        inner = SFTPStorageProfile(HOST="real-remote", USERNAME="u", PORT=22)
        patched = _PatchedEndpointProfile(inner, "127.0.0.1", 54321)
        out = patched.emit(TargetFamily.PARAMIKO)
        assert out["hostname"] == "127.0.0.1"
        assert out["port"] == 54321

    def test_emit_patches_endpoint_url(self):
        from mountainash_auth_client.targets import TargetFamily
        from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile

        inner = S3StorageProfile(FLAVOR="minio", ENDPOINT_URL="http://real:9000", REGION="us-east-1")
        patched = _PatchedEndpointProfile(inner, "127.0.0.1", 7777)
        out = patched.emit(TargetFamily.BOTO)
        assert out["endpoint_url"] == "http://127.0.0.1:7777"
