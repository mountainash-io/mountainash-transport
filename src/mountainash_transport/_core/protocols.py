"""Shared protocols — ConnectionProtocol for all connection types."""
from __future__ import annotations

import typing as t

from typing import Protocol, TypeVar, runtime_checkable

from typing_extensions import Self

C = TypeVar("C")


@runtime_checkable
class ConnectionProtocol(Protocol[C]):
    """Unified connection lifecycle protocol.

    Replaces both StorageConnectionProtocol and ConnectionMixinProtocol.
    All connections implement this: leaf, OAuth decorated, and tunnelled.
    """

    def connect(self) -> Self: ...

    def disconnect(self) -> None: ...

    @property
    def client(self) -> C | None: ...

    @property
    def is_connected(self) -> bool: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, *args: t.Any) -> None: ...
