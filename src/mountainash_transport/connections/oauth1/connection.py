"""OAuth1Connection — manages OAuth1 token lifecycle, delegates to HTTPConnection."""
from __future__ import annotations

import typing as t

from typing_extensions import Self

import httpx

from mountainash_auth_client import OAuth1AuthProfile
from mountainash_auth_client.targets import TargetFamily
from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.connections.oauth1.flow import OAuth1Flow
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
from mountainash_settings.secrets.registry import get_secrets_backend


class OAuth1Connection:
    """Token lifecycle + client creation via inner HTTPConnection."""

    def __init__(
        self,
        profile: StorageProfileProtocol,
        auth_profile: OAuth1AuthProfile,
        *,
        auto_authorize: bool = False,
    ) -> None:
        self._profile = profile
        self._spec = profile.__spec__
        self._auth = auth_profile
        self._auto_authorize = auto_authorize
        self._inner: HTTPConnection | None = None

    def connect(self) -> Self:
        self._inner = HTTPConnection(self._resolve_kwargs())
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

    def _resolve_kwargs(self) -> dict[str, t.Any]:
        provider = self._spec.name
        backend = get_secrets_backend(self._auth.SETTINGS_SOURCE_SECRETS_PROVIDER)
        key = self._auth.persist_key()
        tokens = backend.get(key)

        if not (tokens and tokens.get("oauth_token")):
            if not self._auto_authorize:
                raise AuthorizationRequired(provider=provider, user="default")
            flow = OAuth1Flow(self._spec)
            tokens = flow.authorize(
                consumer_key=self._auth.CONSUMER_KEY,
                consumer_secret=self._auth.CONSUMER_SECRET.get_secret_value(),
            )
            backend.set(key, tokens)

        emitter = OAuth1AuthProfile(
            CONSUMER_KEY=self._auth.CONSUMER_KEY,
            CONSUMER_SECRET=self._auth.CONSUMER_SECRET.get_secret_value(),
            ACCESS_TOKEN=tokens["oauth_token"],
            ACCESS_TOKEN_SECRET=tokens["oauth_token_secret"],
        )
        return emitter.emit(TargetFamily.HTTP, base=self._profile.to_handler_kwargs())
