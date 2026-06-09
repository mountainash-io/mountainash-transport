"""Callback server protocol — ephemeral OAuth redirect listener."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CallbackServerProtocol(Protocol):
    """Interface for OAuth callback servers."""

    @property
    def port(self) -> int: ...

    @property
    def redirect_uri(self) -> str: ...

    def wait_for_callback(self) -> dict[str, str]: ...
