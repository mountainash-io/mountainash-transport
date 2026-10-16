"""SFTPConnection — decorator over SSHConnection exposing paramiko.SFTPClient."""
from __future__ import annotations

import contextlib
import typing as t
from types import TracebackType

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
        try:
            self._close_channel()
            if not self._ssh.is_connected:
                self._ssh.connect()
            try:
                self._sftp = self._ssh.client.open_sftp()
            except Exception as exc:
                raise TransportConnectionError(
                    f"Failed to open SFTP subsystem: {exc}"
                ) from exc
        except BaseException as primary:
            try:
                self.disconnect()
            except BaseException as cleanup:
                primary.add_note(f"Connection cleanup also failed: {cleanup!r}")
                for note in getattr(cleanup, "__notes__", ()):
                    primary.add_note(note)
            raise
        return self

    def _close_channel(self) -> None:
        channel, self._sftp = self._sftp, None
        if channel is not None:
            try:
                channel.close()
            except Exception as exc:
                raise TransportConnectionError(f"Failed to close SFTP channel: {exc}") from exc

    def disconnect(self) -> None:
        with contextlib.ExitStack() as cleanup:
            cleanup.callback(self._ssh.disconnect)
            self._close_channel()

    @property
    def client(self) -> t.Any:
        return self._sftp

    @property
    def is_connected(self) -> bool:
        return self._sftp is not None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None,
        exc_value: BaseException | None, traceback: TracebackType | None,
    ) -> None:
        try:
            self.disconnect()
        except BaseException as cleanup:
            if exc_value is None:
                raise
            exc_value.add_note(f"Connection cleanup also failed: {cleanup!r}")
            for note in getattr(cleanup, "__notes__", ()):
                exc_value.add_note(note)
