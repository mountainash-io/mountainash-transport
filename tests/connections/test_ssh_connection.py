"""SSHConnection behavioral tests."""
from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

import pytest

from mountainash_transport._core.auth.strategies import NoAuthStrategy, SSHPasswordStrategy
from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.ssh import SSHConnection


FAKE_SSH_KWARGS: dict = {
    "hostname": "example.com",
    "port": 22,
    "username": "user",
}

FAKE_SSH_KWARGS_WITH_POST_CONNECT: dict = {
    "hostname": "example.com",
    "port": 22,
    "username": "user",
    "_post_connect": {"host_key_policy": "auto_add"},
}


class TestSSHConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        conn = SSHConnection(FAKE_SSH_KWARGS, NoAuthStrategy())
        assert isinstance(conn, ConnectionProtocol)


class TestSSHConnectionLifecycle:
    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_connect_creates_client(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS, NoAuthStrategy())
        result = conn.connect()

        mock_paramiko.SSHClient.assert_called_once()
        mock_client.connect.assert_called_once()
        assert conn.client is mock_client
        assert conn.is_connected is True
        assert result is conn

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_disconnect_closes_client(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS, NoAuthStrategy())
        conn.connect()
        conn.disconnect()

        mock_client.close.assert_called_once()
        assert conn.client is None
        assert conn.is_connected is False

    def test_not_connected_initially(self):
        conn = SSHConnection(FAKE_SSH_KWARGS, NoAuthStrategy())
        assert conn.client is None
        assert conn.is_connected is False

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_disconnect_when_not_connected_is_noop(self, mock_paramiko):
        conn = SSHConnection(FAKE_SSH_KWARGS, NoAuthStrategy())
        conn.disconnect()  # should not raise

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_context_manager(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS, NoAuthStrategy())
        with conn:
            conn.connect()
            assert conn.is_connected is True
        mock_client.close.assert_called_once()
        assert conn.is_connected is False

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_connect_is_idempotent(self, mock_paramiko):
        """connect() when already connected disconnects first, then reconnects."""
        mock_client1 = MagicMock()
        mock_client2 = MagicMock()
        mock_paramiko.SSHClient.side_effect = [mock_client1, mock_client2]
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS, NoAuthStrategy())
        conn.connect()
        assert conn.client is mock_client1

        conn.connect()
        mock_client1.close.assert_called_once()
        assert conn.client is mock_client2


class TestSSHConnectionAuth:
    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_password_strategy_injected(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        strategy = SSHPasswordStrategy("s3cr3t")
        conn = SSHConnection(FAKE_SSH_KWARGS, strategy)
        conn.connect()

        call_kwargs = mock_client.connect.call_args[1]
        assert call_kwargs["password"] == "s3cr3t"

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_no_auth_no_password(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS, NoAuthStrategy())
        conn.connect()

        call_kwargs = mock_client.connect.call_args[1]
        assert "password" not in call_kwargs


class TestSSHConnectionHostKeyPolicy:
    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_auto_add_policy_set(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy = MagicMock
        mock_paramiko.RejectPolicy = MagicMock

        kwargs = {**FAKE_SSH_KWARGS, "_post_connect": {"host_key_policy": "auto_add"}}
        conn = SSHConnection(kwargs, NoAuthStrategy())
        conn.connect()

        mock_client.set_missing_host_key_policy.assert_called_once()
        # The policy passed should be an AutoAddPolicy instance
        policy_arg = mock_client.set_missing_host_key_policy.call_args[0][0]
        assert isinstance(policy_arg, mock_paramiko.AutoAddPolicy)

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_reject_policy_set_by_default(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS, NoAuthStrategy())
        conn.connect()

        mock_client.set_missing_host_key_policy.assert_called_once()
        policy_arg = mock_client.set_missing_host_key_policy.call_args[0][0]
        assert isinstance(policy_arg, mock_paramiko.RejectPolicy)

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_known_hosts_file_loaded(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        kwargs = {**FAKE_SSH_KWARGS, "_post_connect": {"known_hosts_file": "/home/user/.ssh/known_hosts"}}
        conn = SSHConnection(kwargs, NoAuthStrategy())
        conn.connect()

        mock_client.load_host_keys.assert_called_once_with("/home/user/.ssh/known_hosts")

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_known_hosts_not_loaded_when_absent(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS, NoAuthStrategy())
        conn.connect()

        mock_client.load_host_keys.assert_not_called()


class TestSSHConnectionErrorWrapping:
    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_authentication_exception_wrapped(self, mock_paramiko):
        from mountainash_transport.connections.errors import TransportConnectionError

        AuthException = type("AuthenticationException", (Exception,), {})
        mock_paramiko.AuthenticationException = AuthException
        mock_client = MagicMock()
        mock_client.connect.side_effect = AuthException("auth failed")
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS, NoAuthStrategy())
        with pytest.raises(TransportConnectionError, match="SSH connection failed"):
            conn.connect()

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_ssh_exception_wrapped(self, mock_paramiko):
        from mountainash_transport.connections.errors import TransportConnectionError

        SSHException = type("SSHException", (Exception,), {})
        mock_client = MagicMock()
        mock_client.connect.side_effect = SSHException("banner error")
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS, NoAuthStrategy())
        with pytest.raises(TransportConnectionError, match="SSH connection failed"):
            conn.connect()

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_socket_timeout_raises_connection_timeout_error(self, mock_paramiko):
        from mountainash_transport.connections.errors import ConnectionTimeoutError

        mock_client = MagicMock()
        mock_client.connect.side_effect = socket.timeout("timed out")
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS, NoAuthStrategy())
        with pytest.raises(ConnectionTimeoutError, match="SSH connection timed out"):
            conn.connect()

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_socket_gaierror_wrapped(self, mock_paramiko):
        from mountainash_transport.connections.errors import TransportConnectionError

        mock_client = MagicMock()
        mock_client.connect.side_effect = socket.gaierror("name or service not known")
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS, NoAuthStrategy())
        with pytest.raises(TransportConnectionError, match="SSH DNS resolution failed"):
            conn.connect()

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_oserror_wrapped(self, mock_paramiko):
        from mountainash_transport.connections.errors import TransportConnectionError

        mock_client = MagicMock()
        mock_client.connect.side_effect = OSError("connection refused")
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS, NoAuthStrategy())
        with pytest.raises(TransportConnectionError, match="SSH connection failed"):
            conn.connect()

    @patch("mountainash_transport.connections.ssh.paramiko", new=None)
    def test_paramiko_none_raises_transport_connection_error(self):
        from mountainash_transport.connections.errors import TransportConnectionError

        conn = SSHConnection(FAKE_SSH_KWARGS, NoAuthStrategy())
        with pytest.raises(TransportConnectionError, match="paramiko is required"):
            conn.connect()
