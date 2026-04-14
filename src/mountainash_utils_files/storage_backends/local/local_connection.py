"""LocalConnectionMixin — no-op connection management for local filesystem."""

from __future__ import annotations


class LocalConnectionMixin:
    """No-op connection mixin for local filesystem.

    Local filesystem requires no connection management.
    """

    def connect(self) -> None:
        """No-op: local filesystem requires no connection."""

    def disconnect(self) -> None:
        """No-op: local filesystem requires no disconnection."""

    def is_connected(self) -> bool:
        """Always connected for local filesystem."""
        return True
