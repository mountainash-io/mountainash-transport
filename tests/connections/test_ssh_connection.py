"""SSHConnection behavioral tests."""
from __future__ import annotations

import socket
import sys
from unittest.mock import MagicMock, patch

import pytest

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


@pytest.fixture
def mock_paramiko():
    """Stand in for the real `paramiko` module for the duration of a test.

    SSHConnection.connect() does `import paramiko` lazily (to keep it out of
    the package's top-level import graph), so patching the module out of
    `sys.modules` — rather than patching an `ssh.paramiko` module attribute
    that no longer exists — is what actually intercepts it.
    """
    mock = MagicMock()
    with patch.dict(sys.modules, {"paramiko": mock}):
        yield mock


class TestSSHConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        conn = SSHConnection(FAKE_SSH_KWARGS)
        assert isinstance(conn, ConnectionProtocol)


class TestSSHConnectionLifecycle:
    def test_connect_creates_client(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS)
        result = conn.connect()

        mock_paramiko.SSHClient.assert_called_once()
        mock_client.connect.assert_called_once()
        assert conn.client is mock_client
        assert conn.is_connected is True
        assert result is conn

    def test_disconnect_closes_client(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS)
        conn.connect()
        conn.disconnect()

        mock_client.close.assert_called_once()
        assert conn.client is None
        assert conn.is_connected is False

    def test_not_connected_initially(self):
        conn = SSHConnection(FAKE_SSH_KWARGS)
        assert conn.client is None
        assert conn.is_connected is False

    def test_disconnect_when_not_connected_is_noop(self, mock_paramiko):
        conn = SSHConnection(FAKE_SSH_KWARGS)
        conn.disconnect()  # should not raise

    def test_context_manager(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS)
        with conn:
            conn.connect()
            assert conn.is_connected is True
        mock_client.close.assert_called_once()
        assert conn.is_connected is False

    def test_connect_is_idempotent(self, mock_paramiko):
        """connect() when already connected disconnects first, then reconnects."""
        mock_client1 = MagicMock()
        mock_client2 = MagicMock()
        mock_paramiko.SSHClient.side_effect = [mock_client1, mock_client2]
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS)
        conn.connect()
        assert conn.client is mock_client1

        conn.connect()
        mock_client1.close.assert_called_once()
        assert conn.client is mock_client2


class TestSSHConnectionAuth:
    def test_password_passed_to_paramiko(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        kwargs = {**FAKE_SSH_KWARGS, "password": "s3cr3t"}
        conn = SSHConnection(kwargs)
        conn.connect()

        call_kwargs = mock_client.connect.call_args[1]
        assert call_kwargs["password"] == "s3cr3t"

    def test_no_auth_no_password(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS)
        conn.connect()

        call_kwargs = mock_client.connect.call_args[1]
        assert "password" not in call_kwargs


class TestSSHConnectionHostKeyPolicy:
    @pytest.mark.parametrize(
        ("policy", "paramiko_class"),
        [("reject", "RejectPolicy"), ("warn", "WarningPolicy"), ("auto_add", "AutoAddPolicy")],
    )
    def test_each_policy_maps_to_paramiko_policy(self, mock_paramiko, policy, paramiko_class):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        for name in ("RejectPolicy", "WarningPolicy", "AutoAddPolicy"):
            setattr(mock_paramiko, name, type(name, (), {}))

        kwargs = {**FAKE_SSH_KWARGS, "_post_connect": {"host_key_policy": policy}}
        SSHConnection(kwargs).connect()

        mock_client.set_missing_host_key_policy.assert_called_once()
        policy_arg = mock_client.set_missing_host_key_policy.call_args[0][0]
        assert type(policy_arg) is getattr(mock_paramiko, paramiko_class)

    @pytest.mark.parametrize("policy", ["ignore", "bogus"])
    def test_unknown_policy_raises_without_connecting(self, mock_paramiko, policy):
        kwargs = {**FAKE_SSH_KWARGS, "_post_connect": {"host_key_policy": policy}}
        with pytest.raises(ValueError, match="auto_add.*reject.*warn"):
            SSHConnection(kwargs).connect()
        mock_paramiko.SSHClient.return_value.connect.assert_not_called()

    def test_reject_policy_set_by_default(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS)
        conn.connect()

        mock_client.set_missing_host_key_policy.assert_called_once()
        policy_arg = mock_client.set_missing_host_key_policy.call_args[0][0]
        assert isinstance(policy_arg, mock_paramiko.RejectPolicy)

    def test_known_hosts_file_loaded(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        kwargs = {**FAKE_SSH_KWARGS, "_post_connect": {"known_hosts_file": "/home/user/.ssh/known_hosts"}}
        conn = SSHConnection(kwargs)
        conn.connect()

        mock_client.load_host_keys.assert_called_once_with("/home/user/.ssh/known_hosts")

    def test_known_hosts_not_loaded_when_absent(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS)
        conn.connect()

        mock_client.load_host_keys.assert_not_called()


class TestSSHConnectionErrorWrapping:
    def test_authentication_exception_wrapped(self, mock_paramiko):
        from mountainash_transport.connections.errors import TransportConnectionError

        AuthException = type("AuthenticationException", (Exception,), {})
        mock_paramiko.AuthenticationException = AuthException
        mock_client = MagicMock()
        mock_client.connect.side_effect = AuthException("auth failed")
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS)
        with pytest.raises(TransportConnectionError, match="SSH connection failed"):
            conn.connect()

    def test_ssh_exception_wrapped(self, mock_paramiko):
        from mountainash_transport.connections.errors import TransportConnectionError

        SSHException = type("SSHException", (Exception,), {})
        mock_client = MagicMock()
        mock_client.connect.side_effect = SSHException("banner error")
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS)
        with pytest.raises(TransportConnectionError, match="SSH connection failed"):
            conn.connect()

    def test_socket_timeout_raises_connection_timeout_error(self, mock_paramiko):
        from mountainash_transport.connections.errors import ConnectionTimeoutError

        mock_client = MagicMock()
        mock_client.connect.side_effect = socket.timeout("timed out")
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS)
        with pytest.raises(ConnectionTimeoutError, match="SSH connection timed out"):
            conn.connect()

    def test_socket_gaierror_wrapped(self, mock_paramiko):
        from mountainash_transport.connections.errors import TransportConnectionError

        mock_client = MagicMock()
        mock_client.connect.side_effect = socket.gaierror("name or service not known")
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS)
        with pytest.raises(TransportConnectionError, match="SSH DNS resolution failed"):
            conn.connect()

    def test_oserror_wrapped(self, mock_paramiko):
        from mountainash_transport.connections.errors import TransportConnectionError

        mock_client = MagicMock()
        mock_client.connect.side_effect = OSError("connection refused")
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.RejectPolicy = MagicMock

        conn = SSHConnection(FAKE_SSH_KWARGS)
        with pytest.raises(TransportConnectionError, match="SSH connection failed"):
            conn.connect()

    def test_paramiko_none_raises_transport_connection_error(self):
        from mountainash_transport.connections.errors import TransportConnectionError

        with patch.dict(sys.modules, {"paramiko": None}):
            conn = SSHConnection(FAKE_SSH_KWARGS)
            with pytest.raises(TransportConnectionError, match="paramiko is required"):
                conn.connect()


@pytest.mark.parametrize("stage", ["load_system_host_keys", "load_host_keys", "connect"])
def test_partial_startup_releases_allocated_client(mock_paramiko, stage) -> None:
    from mountainash_transport.connections.errors import TransportConnectionError

    client = mock_paramiko.SSHClient.return_value
    original = OSError("startup failed")
    getattr(client, stage).side_effect = original
    conn = SSHConnection({**FAKE_SSH_KWARGS, "_post_connect": {"known_hosts_file": "known-hosts"}})
    with pytest.raises((OSError, TransportConnectionError)) as caught:
        conn.connect()
    assert caught.value is original or caught.value.__cause__ is original
    client.close.assert_called_once()
    assert conn.client is None


def test_failed_replacement_detaches_ssh_client(mock_paramiko) -> None:
    from mountainash_transport.connections.errors import TransportConnectionError

    first, second = MagicMock(), MagicMock()
    mock_paramiko.SSHClient.side_effect = [first, second]
    conn = SSHConnection(FAKE_SSH_KWARGS).connect()
    first.close.side_effect = OSError("close failed")
    with pytest.raises(TransportConnectionError):
        conn.connect()
    assert conn.client is None
    conn.disconnect()
    first.close.assert_called_once()
    conn.connect()
    assert conn.client is second
    conn.disconnect()
    second.close.assert_called_once()


def test_startup_error_survives_failed_ssh_cleanup(mock_paramiko) -> None:
    client = mock_paramiko.SSHClient.return_value
    primary = ValueError("invalid host keys")
    client.load_system_host_keys.side_effect = primary
    client.close.side_effect = OSError("cleanup failed")
    with pytest.raises(ValueError) as caught:
        SSHConnection(FAKE_SSH_KWARGS).connect()
    assert caught.value is primary
    assert primary.__notes__


def test_ssh_context_preserves_body_error(mock_paramiko) -> None:
    conn = SSHConnection(FAKE_SSH_KWARGS).connect()
    mock_paramiko.SSHClient.return_value.close.side_effect = OSError("cleanup failed")
    primary = ValueError("body")
    with pytest.raises(ValueError) as caught:
        with conn:
            raise primary
    assert caught.value is primary
    assert primary.__notes__
    assert conn.client is None
