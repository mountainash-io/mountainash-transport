"""OAuth2 flow protocol — token exchange, refresh, PKCE."""
from __future__ import annotations

import typing as t

from typing import Protocol, runtime_checkable


@runtime_checkable
class OAuth2FlowProtocol(Protocol):
    """Interface for OAuth 2.0 Authorization Code flows."""

    def build_authorize_url(
        self,
        client_id: str,
        redirect_uri: str,
        scope: str | None = ...,
    ) -> tuple[str, str]: ...

    def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        client_id: str,
        client_secret: str,
        scope: str | None = ...,
        state: str | None = ...,
    ) -> dict[str, t.Any]: ...

    def refresh(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, t.Any]: ...

    @staticmethod
    def is_expired(
        token_expires_at: int | None,
        buffer_seconds: int = ...,
    ) -> bool: ...

    def authorize(
        self,
        client_id: str,
        client_secret: str,
        redirect_mode: str = ...,
        scope: str | None = ...,
    ) -> dict[str, t.Any]: ...
