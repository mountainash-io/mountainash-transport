"""Shared protocols — ConnectionProtocol for all connection types."""
from __future__ import annotations

from types import TracebackType

from typing import Protocol, TypeVar, runtime_checkable

from typing_extensions import Self

C = TypeVar("C", covariant=True)


@runtime_checkable
class ConnectionProtocol(Protocol[C]):
    """Unified connection lifecycle protocol.

    Disconnect attempts cleanup of all owned resources, including partial
    acquisition, and is idempotent even after failure. Explicit connect may
    reopen a connection; facade close is instead terminal. Context-body errors
    remain primary if cleanup fails. Decorators exclusively own their children.
    """

    def connect(self) -> Self: ...

    def disconnect(self) -> None: ...

    @property
    def client(self) -> C | None: ...

    @property
    def is_connected(self) -> bool: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self, exc_type: type[BaseException] | None,
        exc_value: BaseException | None, traceback: TracebackType | None,
    ) -> None: ...
