"""Auth strategies — inject credentials into SDK client kwargs."""
from __future__ import annotations

import base64
import importlib
import typing as t

from typing import Protocol, runtime_checkable


@runtime_checkable
class AuthStrategy(Protocol):
    """Inject auth credentials into SDK client kwargs.

    Returns a NEW dict — does not mutate the input.
    """

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]: ...


class NoAuthStrategy:
    """Passthrough — no credentials injected."""

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        return {**kwargs}


class BearerTokenStrategy:
    """Inject a Bearer token into the Authorization header."""

    def __init__(self, token: str) -> None:
        self._token = token

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        result = {**kwargs}
        existing = dict(result.get("headers", {}))
        existing["Authorization"] = f"Bearer {self._token}"
        result["headers"] = existing
        return result


class BasicAuthStrategy:
    """Inject HTTP Basic auth into the Authorization header."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        result = {**kwargs}
        encoded = base64.b64encode(
            f"{self._username}:{self._password}".encode()
        ).decode()
        existing = dict(result.get("headers", {}))
        existing["Authorization"] = f"Basic {encoded}"
        result["headers"] = existing
        return result


class OAuth1SignedStrategy:
    """Inject authlib OAuth1Auth handler into httpx kwargs (auth= parameter)."""

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._oauth_token = oauth_token
        self._oauth_token_secret = oauth_token_secret

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        try:
            _mod = importlib.import_module("authlib.integrations.httpx_client.oauth1_client")
            AuthlibOAuth1Auth = _mod.OAuth1Auth
        except ImportError as exc:
            raise ImportError(
                "OAuth1 requires authlib: pip install mountainash-transport[oauth1]"
            ) from exc

        result = {**kwargs}
        result["auth"] = AuthlibOAuth1Auth(
            client_id=self._consumer_key,
            client_secret=self._consumer_secret,
            token=self._oauth_token,
            token_secret=self._oauth_token_secret,
        )
        return result
