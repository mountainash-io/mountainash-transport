"""OAuth1Connection — manages OAuth1 token lifecycle, delegates to HTTPConnection."""
from __future__ import annotations

import typing as t

from typing_extensions import Self

import httpx

from mountainash_transport._core.auth.strategies import AuthStrategy, OAuth1SignedStrategy
from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.connections.oauth1.flow import OAuth1Flow
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
from mountainash_settings.secrets.registry import get_secrets_backend

if t.TYPE_CHECKING:
    from mountainash_auth_client.schemas.oauth1 import OAuth1Auth


class OAuth1Connection:
    """Token lifecycle + client creation via inner HTTPConnection."""

    def __init__(
        self,
        profile: StorageProfileProtocol,
        auth_profile: OAuth1Auth,
        *,
        auto_authorize: bool = False,
    ) -> None:
        self._profile = profile
        self._spec = profile.__spec__
        self._auth = auth_profile
        self._auto_authorize = auto_authorize
        self._inner: HTTPConnection | None = None

    def connect(self) -> Self:
        strategy = self._resolve_strategy()
        self._inner = HTTPConnection(self._profile, strategy)
        self._inner.connect()
        return self

    def disconnect(self) -> None:
        if self._inner is not None:
            self._inner.disconnect()
        self._inner = None

    @property
    def client(self) -> httpx.Client | None:
        return self._inner.client if self._inner else None

    @property
    def is_connected(self) -> bool:
        return self._inner is not None and self._inner.is_connected

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: t.Any) -> None:
        self.disconnect()

    def _resolve_strategy(self) -> AuthStrategy:
        provider = self._spec.name

        backend = get_secrets_backend(self._auth.SETTINGS_SOURCE_SECRETS_PROVIDER)
        key = self._auth.persist_key()
        tokens = backend.get(key)

        if tokens and tokens.get("oauth_token"):
            return OAuth1SignedStrategy(
                consumer_key=self._auth.CONSUMER_KEY,
                consumer_secret=self._auth.CONSUMER_SECRET.get_secret_value(),
                oauth_token=tokens["oauth_token"],
                oauth_token_secret=tokens["oauth_token_secret"],
            )

        if self._auto_authorize:
            flow = OAuth1Flow(self._spec)
            new_tokens = flow.authorize(
                consumer_key=self._auth.CONSUMER_KEY,
                consumer_secret=self._auth.CONSUMER_SECRET.get_secret_value(),
            )
            backend.set(key, new_tokens)
            return OAuth1SignedStrategy(
                consumer_key=self._auth.CONSUMER_KEY,
                consumer_secret=self._auth.CONSUMER_SECRET.get_secret_value(),
                oauth_token=new_tokens["oauth_token"],
                oauth_token_secret=new_tokens["oauth_token_secret"],
            )

        raise AuthorizationRequired(provider=provider, user="default")
