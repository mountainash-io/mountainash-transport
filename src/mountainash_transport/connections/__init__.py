"""Connection infrastructure — OAuth flows, callback servers, token lifecycle, and factory."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.auth.resolver import resolve_auth_strategy
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol

# --- Legacy/existing public API (kept for backward compat) -------------------
from .protocols import (
    OAuth2FlowProtocol, OAuth1FlowProtocol,
    CallbackServerProtocol, ConnectionMixinProtocol,
)
from .errors import (
    ConnectionError, TokenExchangeError, TokenRefreshError, AuthorizationRequired,
    TransportConnectionError, ConnectionTimeoutError,
)
from .oauth2.flow import OAuthFlow
from .oauth2.mixin import OAuth2ConnectionMixin
from .oauth1.flow import OAuth1Flow
from .oauth1.mixin import OAuth1ConnectionMixin
from .server.callback import LocalCallbackServer
from .server.manual import extract_code_from_input, prompt_for_code

# --- New connection classes ---------------------------------------------------
from .http import HTTPConnection
from .null import NullConnection
from .s3 import S3Connection
from .oauth2.connection import OAuth2Connection
from .oauth1.connection import OAuth1Connection

if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthProfile
    from mountainash_transport._core.protocols import ConnectionProtocol


# --- Provider → leaf connection map ------------------------------------------

_PROVIDER_CONNECTION_MAP: dict[str, type] = {
    "http": HTTPConnection,
    "local": NullConnection,
    "s3": S3Connection,
    "s3express": S3Connection,
    "r2": S3Connection,
    "minio": S3Connection,
    "b2": S3Connection,
}


def _connection_for_provider(profile: StorageProfileProtocol) -> type:
    """Map profile's provider_type to a leaf connection class."""
    provider = getattr(getattr(profile, "__spec__", None), "provider_type", None)
    provider_str = str(provider.value) if hasattr(provider, "value") else str(provider)
    return _PROVIDER_CONNECTION_MAP.get(provider_str, HTTPConnection)


def create_connection(
    profile: StorageProfileProtocol,
    auth_profile: AuthProfile | None = None,
    *,
    auto_authorize: bool = False,
) -> ConnectionProtocol:
    """Create the right connection for a profile + auth combination."""
    from mountainash_auth_client import OAuth2Auth, OAuth2AuthCodeAuth

    if isinstance(auth_profile, (OAuth2Auth, OAuth2AuthCodeAuth)):
        return OAuth2Connection(profile, auth_profile, auto_authorize=auto_authorize)

    try:
        from mountainash_auth_client.schemas.oauth1 import OAuth1Auth
        if isinstance(auth_profile, OAuth1Auth):
            return OAuth1Connection(profile, auth_profile, auto_authorize=auto_authorize)
    except ImportError:
        pass

    strategy = resolve_auth_strategy(auth_profile)
    leaf_cls = _connection_for_provider(profile)
    if leaf_cls is NullConnection:
        return NullConnection()
    return leaf_cls(profile, strategy)


__all__ = [
    # Legacy
    "OAuth2FlowProtocol", "OAuth1FlowProtocol",
    "CallbackServerProtocol", "ConnectionMixinProtocol",
    "ConnectionError", "TokenExchangeError", "TokenRefreshError", "AuthorizationRequired",
    "TransportConnectionError", "ConnectionTimeoutError",
    "OAuthFlow", "OAuth2ConnectionMixin",
    "OAuth1Flow", "OAuth1ConnectionMixin",
    "LocalCallbackServer", "extract_code_from_input", "prompt_for_code",
    # New
    "HTTPConnection", "NullConnection", "S3Connection", "OAuth2Connection", "OAuth1Connection",
    "create_connection",
]
