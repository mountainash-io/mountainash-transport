"""SSHConnection — general-purpose leaf connection creating a paramiko.SSHClient."""
from __future__ import annotations

import socket
import typing as t

from typing_extensions import Self

from mountainash_transport._core.auth.strategies import AuthStrategy
from mountainash_transport.connections.errors import (
    ConnectionTimeoutError,
    TransportConnectionError,
)
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
from .._core.protocols import ConnectionProtocol

try:
    import paramiko
except ImportError:
    paramiko = None  # type: ignore[assignment]


_HOST_KEY_POLICIES: dict[str, str] = {
    "reject": "RejectPolicy",
    "warn": "WarningPolicy",
    "auto_add": "AutoAddPolicy",
}


class SSHConnection(ConnectionProtocol):
    """Creates an authenticated paramiko.SSHClient from profile config + auth strategy."""

    def __init__(
        self,
        profile: StorageProfileProtocol,
        auth_strategy: AuthStrategy,
    ) -> None:
        self._profile = profile
        self._auth_strategy = auth_strategy
        self._client: t.Any = None

    def connect(self) -> Self:
        if paramiko is None:
            raise TransportConnectionError(
                "paramiko is required for SSH connections — "
                "install with: pip install mountainash-transport[sftp]"
            )

        if self._client is not None:
            self.disconnect()

        kwargs = self._profile.to_handler_kwargs()
        kwargs = self._auth_strategy.apply(kwargs)

        post_connect = kwargs.pop("_post_connect", {})

        client = paramiko.SSHClient()
        client.load_system_host_keys()

        policy_name = post_connect.get("host_key_policy", "reject")
        policy_attr = _HOST_KEY_POLICIES.get(policy_name)
        if policy_attr:
            client.set_missing_host_key_policy(getattr(paramiko, policy_attr)())
        else:
            client.set_missing_host_key_policy(paramiko.RejectPolicy())

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

        self._client = client
        return self

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None

    @property
    def client(self) -> t.Any:
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: t.Any) -> None:
        self.disconnect()
