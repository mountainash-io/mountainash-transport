"""Connection mixin protocol — OAuth connection lifecycle."""
from __future__ import annotations

import typing as t

from typing import Protocol, runtime_checkable

from typing_extensions import Self

if t.TYPE_CHECKING:
    import httpx


@runtime_checkable
class ConnectionMixinProtocol(Protocol):
    """Interface for OAuth connection mixins (token lifecycle + client)."""

    def connect(self, auth: t.Any, *, auto_authorize: bool = ...) -> Self: ...

    def disconnect(self) -> None: ...

    @property
    def client(self) -> httpx.Client | None: ...
