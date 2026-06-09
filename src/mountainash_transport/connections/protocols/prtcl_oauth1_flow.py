"""OAuth1 flow protocol — 3-legged authorization."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class OAuth1FlowProtocol(Protocol):
    """Interface for OAuth 1.0a 3-legged flows."""

    def build_authorize_url(self, oauth_token: str) -> str: ...

    def request_token(
        self,
        consumer_key: str,
        consumer_secret: str,
        callback_url: str = ...,
    ) -> dict[str, str]: ...

    def exchange_verifier(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        verifier: str,
    ) -> dict[str, str]: ...

    def authorize(
        self,
        consumer_key: str,
        consumer_secret: str,
        redirect_mode: str = ...,
    ) -> dict[str, str]: ...
