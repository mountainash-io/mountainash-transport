"""OAuth2Connection — manages token lifecycle, delegates client creation to HTTPConnection."""
from __future__ import annotations

import typing as t

from typing_extensions import Self

import httpx

from mountainash_auth_client import TokenAuthProfile
from mountainash_auth_client.targets import TargetFamily
from mountainash_auth_client.errors import AuthorizationRequired as AuthClientAuthorizationRequired
from mountainash_auth_client.connections.oauth2.flow import OAuthFlow
from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol

if t.TYPE_CHECKING:
    from mountainash_auth_client.schemas.oauth2 import OAuth2AuthProfile
    from mountainash_auth_client.schemas.oauth2_authcode import OAuth2AuthCodeAuthProfile


class OAuth2Connection:
    """Token lifecycle + client creation via inner HTTPConnection."""

    def __init__(
        self,
        profile: StorageProfileProtocol,
        auth_profile: OAuth2AuthProfile | OAuth2AuthCodeAuthProfile,
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
            access_token = OAuthFlow(self._spec).resolve_access_token(
                self._auth, auto_authorize=self._auto_authorize
            )
        except AuthClientAuthorizationRequired:
            # Preserve transport's public error contract (TransportConnectionError
            # subclass); the resolver raises auth-client's distinct class.
            raise AuthorizationRequired(provider=self._spec.name, user="default")
        merged = TokenAuthProfile(TOKEN=access_token).emit(
            TargetFamily.HTTP, base=self._profile.to_handler_kwargs()
        )
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

