"""Auth strategy resolver — map auth profiles to strategies."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.auth.strategies import (
    AuthStrategy,
    BasicAuthStrategy,
    BearerTokenStrategy,
    NoAuthStrategy,
)
from mountainash_transport.settings.utils.secrets import _unwrap_secret

if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthProfile

from mountainash_auth_client import (
    JWTAuth,
    NoAuth,
    OAuth2Auth,
    OAuth2AuthCodeAuth,
    PasswordAuth,
    TokenAuth,
)


def resolve_auth_strategy(auth_profile: AuthProfile | None) -> AuthStrategy:
    """Map an auth profile instance to its auth strategy."""
    if auth_profile is None:
        return NoAuthStrategy()

    if isinstance(auth_profile, NoAuth):
        return NoAuthStrategy()

    if isinstance(auth_profile, (TokenAuth, JWTAuth)):
        token = _unwrap_secret(auth_profile.TOKEN)
        if token:
            return BearerTokenStrategy(token)
        return NoAuthStrategy()

    if isinstance(auth_profile, OAuth2Auth):
        token = _unwrap_secret(auth_profile.TOKEN)
        if token:
            return BearerTokenStrategy(token)
        return NoAuthStrategy()

    if isinstance(auth_profile, OAuth2AuthCodeAuth):
        token = _unwrap_secret(auth_profile.ACCESS_TOKEN)
        if token:
            return BearerTokenStrategy(token)
        return NoAuthStrategy()

    if isinstance(auth_profile, PasswordAuth):
        username = auth_profile.USERNAME or ""
        password = _unwrap_secret(auth_profile.PASSWORD) or ""
        return BasicAuthStrategy(username, password)

    return NoAuthStrategy()
