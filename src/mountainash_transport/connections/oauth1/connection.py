"""OAuth1Connection — manages OAuth1 token lifecycle, delegates to HTTPConnection."""
from __future__ import annotations

import typing as t

from typing_extensions import Self

import httpx

from mountainash_auth_client import OAuth1AuthProfile
from mountainash_auth_client.targets import TargetFamily
from mountainash_auth_client.errors import AuthorizationRequired as AuthClientAuthorizationRequired
from mountainash_auth_client.connections.oauth1.flow import OAuth1Flow
from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol


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
        try:
            oauth_token, oauth_token_secret = OAuth1Flow(self._spec).resolve_token_pair(
                self._auth, auto_authorize=self._auto_authorize
            )
        except AuthClientAuthorizationRequired:
            raise AuthorizationRequired(provider=self._spec.name, user="default")
        emitter = OAuth1AuthProfile(
            CONSUMER_KEY=self._auth.CONSUMER_KEY,
            CONSUMER_SECRET=self._auth.CONSUMER_SECRET,  # SecretStr through; do NOT unwrap
            ACCESS_TOKEN=oauth_token,
            ACCESS_TOKEN_SECRET=oauth_token_secret,
        )
        merged = emitter.emit(TargetFamily.HTTP, base=self._profile.to_handler_kwargs())
        self._inner = HTTPConnection(merged)
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

