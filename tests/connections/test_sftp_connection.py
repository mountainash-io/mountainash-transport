"""SFTPConnection behavioral tests."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.sftp import SFTPConnection


def _make_mock_ssh():
    ssh = MagicMock()
    ssh.is_connected = False
    mock_sftp = MagicMock()
    ssh.client.open_sftp.return_value = mock_sftp
    return ssh, mock_sftp


class TestSFTPConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        ssh, _ = _make_mock_ssh()
        conn = SFTPConnection(ssh)
        assert isinstance(conn, ConnectionProtocol)


class TestSFTPConnectionLifecycle:
    def test_connect_opens_sftp_ssh_already_connected(self):
        ssh, mock_sftp = _make_mock_ssh()
        ssh.is_connected = True

        conn = SFTPConnection(ssh)
        result = conn.connect()

        ssh.connect.assert_not_called()
        ssh.client.open_sftp.assert_called_once()
        assert conn.client is mock_sftp
        assert conn.is_connected is True
        assert result is conn

    def test_connect_connects_ssh_if_not_connected(self):
        ssh, mock_sftp = _make_mock_ssh()
        ssh.is_connected = False

        conn = SFTPConnection(ssh)
        conn.connect()

        ssh.connect.assert_called_once()
        ssh.client.open_sftp.assert_called_once()
        assert conn.client is mock_sftp

    def test_connect_skips_ssh_connect_if_already_connected(self):
        ssh, _ = _make_mock_ssh()
        ssh.is_connected = True

        conn = SFTPConnection(ssh)
        conn.connect()

        ssh.connect.assert_not_called()

    def test_disconnect_closes_sftp_and_ssh(self):
        ssh, mock_sftp = _make_mock_ssh()
        ssh.is_connected = True

        conn = SFTPConnection(ssh)
        conn.connect()
        conn.disconnect()

        mock_sftp.close.assert_called_once()
        ssh.disconnect.assert_called_once()
        assert conn.client is None
        assert conn.is_connected is False

    def test_not_connected_initially(self):
        ssh, _ = _make_mock_ssh()
        conn = SFTPConnection(ssh)
        assert conn.client is None
        assert conn.is_connected is False

    def test_disconnect_when_not_connected_still_calls_ssh_disconnect(self):
        ssh, _ = _make_mock_ssh()
        conn = SFTPConnection(ssh)
        conn.disconnect()  # should not raise

        ssh.disconnect.assert_called_once()

    def test_context_manager(self):
        ssh, mock_sftp = _make_mock_ssh()
        ssh.is_connected = True

        conn = SFTPConnection(ssh)
        with conn:
            conn.connect()
            assert conn.is_connected is True

        mock_sftp.close.assert_called_once()
        ssh.disconnect.assert_called_once()
        assert conn.is_connected is False

    def test_connect_is_idempotent(self):
        """connect() when already connected closes old sftp and opens new one."""
        ssh = MagicMock()
        ssh.is_connected = True
        mock_sftp1 = MagicMock()
        mock_sftp2 = MagicMock()
        ssh.client.open_sftp.side_effect = [mock_sftp1, mock_sftp2]

        conn = SFTPConnection(ssh)
        conn.connect()
        assert conn.client is mock_sftp1

        conn.connect()
        mock_sftp1.close.assert_called_once()
        assert conn.client is mock_sftp2


class TestSFTPConnectionErrorWrapping:
    def test_open_sftp_failure_wrapped_as_transport_connection_error(self):
        from mountainash_transport.connections.errors import TransportConnectionError

        ssh = MagicMock()
        ssh.is_connected = True
        ssh.client.open_sftp.side_effect = Exception("channel request denied")

        conn = SFTPConnection(ssh)
        with pytest.raises(TransportConnectionError, match="Failed to open SFTP subsystem"):
            conn.connect()
