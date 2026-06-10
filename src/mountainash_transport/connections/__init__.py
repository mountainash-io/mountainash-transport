"""Connection infrastructure — OAuth flows, callback servers, token lifecycle, and factory."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.auth.resolver import resolve_auth_strategy
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.settings.profile_protocol import ProfileProtocol

# --- Legacy/existing public API (kept for backward compat) -------------------
from .protocols import (
    OAuth2FlowProtocol, OAuth1FlowProtocol,
    CallbackServerProtocol,
)
from .errors import (
    ConnectionError, TokenExchangeError, TokenRefreshError, AuthorizationRequired,
    TransportConnectionError, ConnectionTimeoutError,
)
from .oauth2.flow import OAuthFlow
from .oauth1.flow import OAuth1Flow
from .server.callback import LocalCallbackServer
from .server.manual import extract_code_from_input, prompt_for_code

# --- New connection classes ---------------------------------------------------
from .http import HTTPConnection
from .null import NullConnection
from .s3 import S3Connection
from .oauth2.connection import OAuth2Connection
from .oauth1.connection import OAuth1Connection
from .ssh import SSHConnection
from .sftp import SFTPConnection
from .tunnel import TunnelledConnection, _PatchedEndpointProfile

if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthProfile
    from mountainash_transport._core.protocols import ConnectionProtocol


def _provider_type_from_profile(profile: ProfileProtocol) -> CONST_STORAGE_PROVIDER_TYPE | None:
    """Extract the CONST_STORAGE_PROVIDER_TYPE enum from a profile, or None."""
    provider = getattr(getattr(profile, "__spec__", None), "provider_type", None)
    if isinstance(provider, CONST_STORAGE_PROVIDER_TYPE):
        return provider
    if provider is not None:
        return CONST_STORAGE_PROVIDER_TYPE.find_member(str(provider))
    return None


# --- Provider → leaf connection map ------------------------------------------

_PROVIDER_CONNECTION_MAP: dict[str, type] = {
    "http": HTTPConnection,
    "local": NullConnection,
    "s3": S3Connection,
    "s3express": S3Connection,
    "r2": S3Connection,
    "minio": S3Connection,
    "b2": S3Connection,
    "sftp": SSHConnection,
}


def _connection_for_provider(profile: ProfileProtocol) -> type:
    """Map profile's provider_type to a leaf connection class."""
    provider = getattr(getattr(profile, "__spec__", None), "provider_type", None)
    provider_str = str(provider.value) if hasattr(provider, "value") else str(provider)
    return _PROVIDER_CONNECTION_MAP.get(provider_str, HTTPConnection)


def create_connection(
    profile: ProfileProtocol,
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

    provider_type = _provider_type_from_profile(profile)

    # SFTP: two-layer composition (SSHConnection → SFTPConnection)
    if provider_type == CONST_STORAGE_PROVIDER_TYPE.SFTP:
        strategy = resolve_auth_strategy(auth_profile, provider_type=CONST_STORAGE_PROVIDER_TYPE.SFTP)
        ssh_conn = SSHConnection(profile, strategy)
        return SFTPConnection(ssh_conn)

    strategy = resolve_auth_strategy(auth_profile, provider_type=provider_type)
    leaf_cls = _connection_for_provider(profile)
    if leaf_cls is NullConnection:
        return NullConnection()
    return leaf_cls(profile, strategy)


def create_tunnelled_connection(
    bastion_profile: ProfileProtocol,
    bastion_auth: AuthProfile | None,
    target_profile: ProfileProtocol,
    target_auth: AuthProfile | None,
    remote_host: str,
    remote_port: int,
) -> TunnelledConnection:
    """Create a tunnelled connection through an SSH bastion host."""
    ssh_conn = SSHConnection(
        bastion_profile,
        resolve_auth_strategy(bastion_auth, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH),
    )

    def inner_factory(local_port: int) -> ConnectionProtocol:
        patched = _PatchedEndpointProfile(target_profile, "127.0.0.1", local_port)
        return create_connection(patched, target_auth)

    return TunnelledConnection(ssh_conn, inner_factory, remote_host, remote_port)


__all__ = [
    # Legacy
    "OAuth2FlowProtocol", "OAuth1FlowProtocol",
    "CallbackServerProtocol",
    "ConnectionError", "TokenExchangeError", "TokenRefreshError", "AuthorizationRequired",
    "TransportConnectionError", "ConnectionTimeoutError",
    "OAuthFlow",
    "OAuth1Flow",
    "LocalCallbackServer", "extract_code_from_input", "prompt_for_code",
    # New
    "HTTPConnection", "NullConnection", "S3Connection", "OAuth2Connection", "OAuth1Connection",
    "SSHConnection", "SFTPConnection", "TunnelledConnection",
    "create_connection", "create_tunnelled_connection",
]
