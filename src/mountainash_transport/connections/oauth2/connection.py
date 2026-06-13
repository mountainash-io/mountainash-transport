"""OAuth2Connection — manages token lifecycle, delegates client creation to HTTPConnection."""
from __future__ import annotations

import typing as t

from typing_extensions import Self

import httpx

from mountainash_auth_client import TokenAuthProfile
from mountainash_auth_client.targets import TargetFamily
from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.connections.oauth2.flow import OAuthFlow
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
from mountainash_settings.secrets.registry import get_secrets_backend

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
        access_token = self._resolve_token()
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

    def _resolve_token(self) -> str:
        provider = self._spec.name
        flow = OAuthFlow(self._spec)

        backend = get_secrets_backend(self._auth.SETTINGS_SOURCE_SECRETS_PROVIDER)
        key = self._auth.persist_key()
        tokens = backend.get(key)

        access_token: str | None = None

        if tokens and not flow.is_expired(tokens.get("token_expires_at")):
            access_token = tokens["access_token"]
        elif tokens and tokens.get("refresh_token"):
            with backend.transaction(key):
                tokens = backend.get(key)
                if tokens and not flow.is_expired(tokens.get("token_expires_at")):
                    access_token = tokens["access_token"]
                else:
                    try:
                        new_tokens = flow.refresh(
                            refresh_token=tokens["refresh_token"],
                            client_id=self._auth.CLIENT_ID,
                            client_secret=self._auth.CLIENT_SECRET.get_secret_value(),
                        )
                    except Exception:
                        backend.delete(key)
                        if not self._auto_authorize:
                            raise AuthorizationRequired(provider=provider, user="default")
                    else:
                        backend.set(key, new_tokens)
                        access_token = new_tokens["access_token"]

        if not access_token:
            if self._auto_authorize:
                new_tokens = flow.authorize(
                    client_id=self._auth.CLIENT_ID,
                    client_secret=self._auth.CLIENT_SECRET.get_secret_value(),
                    scope=self._auth.SCOPE,
                )
                backend.set(key, new_tokens)
                access_token = new_tokens["access_token"]
            else:
                raise AuthorizationRequired(provider=provider, user="default")

        return access_token
