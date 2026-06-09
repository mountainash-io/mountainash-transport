"""SFTPConnection — decorator over SSHConnection exposing paramiko.SFTPClient."""
from __future__ import annotations

import typing as t

from typing_extensions import Self

from mountainash_transport.connections.errors import TransportConnectionError
from .._core.protocols import ConnectionProtocol


class SFTPConnection(ConnectionProtocol):
    """Opens an SFTP channel over an SSHConnection.

    Owns the inner SSHConnection exclusively — disconnect() tears down both.
    """

    def __init__(self, ssh_connection: t.Any) -> None:
        self._ssh = ssh_connection
        self._sftp: t.Any = None

    def connect(self) -> Self:
        if self._sftp is not None:
            self._sftp.close()
            self._sftp = None

        if not self._ssh.is_connected:
            self._ssh.connect()

        try:
            self._sftp = self._ssh.client.open_sftp()
        except Exception as exc:
            raise TransportConnectionError(
                f"Failed to open SFTP subsystem: {exc}"
            ) from exc

        return self

    def disconnect(self) -> None:
        if self._sftp is not None:
            self._sftp.close()
        self._sftp = None
        self._ssh.disconnect()

    @property
    def client(self) -> t.Any:
        return self._sftp

    @property
    def is_connected(self) -> bool:
        return self._sftp is not None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: t.Any) -> None:
        self.disconnect()
