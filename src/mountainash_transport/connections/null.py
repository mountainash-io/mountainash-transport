"""NullConnection — no-op connection for backends that need no client (local filesystem)."""
from __future__ import annotations

import typing as t

from typing_extensions import Self
from .._core.protocols import ConnectionProtocol


class NullConnection(ConnectionProtocol):
    """Always-connected, no-op connection for local filesystem and similar backends."""

    def connect(self) -> Self:
        return self

    def disconnect(self) -> None:
        pass

    @property
    def client(self) -> None:
        return None

    @property
    def is_connected(self) -> bool:
        return True

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: t.Any) -> None:
        pass
