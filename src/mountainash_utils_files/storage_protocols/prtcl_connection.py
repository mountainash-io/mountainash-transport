from __future__ import annotations

import typing
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageConnectionProtocol(Protocol):
    """Protocol for storage connection management."""

    def connect(self) -> None:
        """Establish a connection to the storage system."""
        ...

    def disconnect(self) -> None:
        """Close the connection to the storage system."""
        ...

    def is_connected(self) -> bool:
        """Check whether the storage connection is currently active."""
        ...
