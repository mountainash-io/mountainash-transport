"""SSHConnection — general-purpose leaf connection creating a paramiko.SSHClient."""
from __future__ import annotations

import socket
import typing as t
from types import TracebackType

from typing_extensions import Self

from mountainash_transport.connections.errors import (
    ConnectionTimeoutError,
    TransportConnectionError,
)
from .._core.protocols import ConnectionProtocol


_HOST_KEY_POLICIES: dict[str, str] = {
    "reject": "RejectPolicy",
    "warn": "WarningPolicy",
    "auto_add": "AutoAddPolicy",
}


class SSHConnection(ConnectionProtocol):
    """Creates an authenticated paramiko.SSHClient from connect kwargs + auth strategy."""

    def __init__(self, connect_kwargs: dict[str, t.Any]) -> None:
        self._connect_kwargs = connect_kwargs
        self._client: t.Any = None

    def connect(self) -> Self:
        try:
            import paramiko
        except ImportError as exc:
            raise TransportConnectionError(
                "paramiko is required for SSH connections — "
                "install with: pip install mountainash-transport[sftp]"
            ) from exc

        if self._client is not None:
            self.disconnect()

        kwargs = dict(self._connect_kwargs)

        post_connect = kwargs.pop("_post_connect", {})
        policy_name = post_connect.get("host_key_policy", "reject")
        policy_attr = _HOST_KEY_POLICIES.get(policy_name)
        if policy_attr is None:
            raise ValueError(
                f"Invalid host_key_policy: {policy_name!r}. Must be one of "
                f"{sorted(_HOST_KEY_POLICIES)}."
            )

        client = paramiko.SSHClient()
        self._client = client
        try:
            client.load_system_host_keys()
            client.set_missing_host_key_policy(getattr(paramiko, policy_attr)())

            known_hosts = post_connect.get("known_hosts_file")
            if known_hosts:
                client.load_host_keys(known_hosts)

            try:
                client.connect(**kwargs)
            except socket.timeout as exc:
                raise ConnectionTimeoutError(f"SSH connection timed out: {exc}") from exc
            except socket.gaierror as exc:
                raise TransportConnectionError(f"SSH DNS resolution failed: {exc}") from exc
            except OSError as exc:
                raise TransportConnectionError(f"SSH connection failed: {exc}") from exc
            except Exception as exc:
                raise TransportConnectionError(f"SSH connection failed: {exc}") from exc
        except BaseException as primary:
            try:
                self.disconnect()
            except BaseException as cleanup:
                primary.add_note(f"Connection cleanup also failed: {cleanup!r}")
            raise
        return self

    def disconnect(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                raise TransportConnectionError(f"Failed to close SSH client: {exc}") from exc

    @property
    def client(self) -> t.Any:
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client is not None

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
