"""Auth strategy protocols for the HTTP engine.

These describe the credential-injection / live-refresh contract the HTTP
request engine consumes. Concrete static strategies were removed in Phase 3
(credential rendering now flows through ``Profile.emit``); the refreshable
protocol remains as the seam for flow-owned token refresh.
"""
from __future__ import annotations

import typing as t
from typing import Protocol, runtime_checkable


@runtime_checkable
class AuthStrategy(Protocol):
    """Inject auth credentials into SDK client kwargs. Returns a NEW dict."""

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]: ...


@runtime_checkable
class RefreshableAuthStrategy(AuthStrategy, Protocol):
    """Auth strategy supporting credential refresh.

    After a successful refresh(), get_headers() must reflect the new
    credentials. Implementations must be internally synchronized.
    """

    def refresh(self) -> bool: ...

    def get_headers(self) -> dict[str, str]: ...
