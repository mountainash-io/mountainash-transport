"""Connection infrastructure — OAuth flows, callback servers, token lifecycle, and factory."""
from __future__ import annotations

import typing as t

from mountainash_auth_client.targets import TargetFamily

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.settings.profile_protocol import ProfileProtocol

# --- Legacy/existing public API (kept for backward compat) -------------------
from .errors import (
    ConnectionError, TokenExchangeError, TokenRefreshError, AuthorizationRequired,
    TransportConnectionError, ConnectionTimeoutError,
)
from mountainash_auth_client.connections.oauth2.flow import OAuthFlow
from mountainash_auth_client.connections.oauth1.flow import OAuth1Flow
from mountainash_auth_client.connections.server.callback import LocalCallbackServer
from mountainash_auth_client.connections.server.manual import (
    extract_code_from_input, prompt_for_code,
)

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


def _connection_for_provider(provider_type: CONST_STORAGE_PROVIDER_TYPE | None) -> type:
    """Map provider_type to a leaf connection class."""
    if provider_type is None:
        return HTTPConnection
    provider_str = str(provider_type.value) if hasattr(provider_type, "value") else str(provider_type)
    return _PROVIDER_CONNECTION_MAP.get(provider_str, HTTPConnection)


# --- Provider → SDK target family map ----------------------------------------

_PROVIDER_FAMILY_MAP: dict[str, TargetFamily] = {
    "http": TargetFamily.HTTP,
    "s3": TargetFamily.BOTO, "s3express": TargetFamily.BOTO, "r2": TargetFamily.BOTO,
    "minio": TargetFamily.BOTO, "b2": TargetFamily.BOTO,
    "sftp": TargetFamily.PARAMIKO, "ssh": TargetFamily.PARAMIKO,
}


def _family_for_provider(provider_type: CONST_STORAGE_PROVIDER_TYPE | None) -> TargetFamily | None:
    """Map a storage provider type to the SDK target family it emits for."""
    if provider_type is None:
        return None
    provider_str = str(provider_type.value) if hasattr(provider_type, "value") else str(provider_type)
    return _PROVIDER_FAMILY_MAP.get(provider_str)


def _emit_kwargs(
    profile: ProfileProtocol,
    auth_profile: AuthProfile | None,
    family: TargetFamily | None,
) -> dict[str, t.Any]:
    """Assemble connection kwargs: storage config via emit(family), then auth
    credentials layered on the same family.

    family is None (Local / unmapped) → no SDK emission; fall back to
    to_handler_kwargs (Local keeps its real method). For the S3 assume-role
    envelope (nested base_kwargs), credentials emit onto the inner base_kwargs.
    """
    from mountainash_auth_client import NoAuthProfile

    if family is None:
        return profile.to_handler_kwargs()

    # Profiles emit SDK config via emit(family). ProfileProtocol's base contract
    # is to_handler_kwargs-only (by design — see test_profile_protocol), so a
    # bare protocol implementer without emit() falls back to to_handler_kwargs,
    # preserving the factory's pre-Phase-4 tolerance for any ProfileProtocol.
    emit = getattr(profile, "emit", None)
    base = emit(family) if callable(emit) else profile.to_handler_kwargs()
    if auth_profile is None or isinstance(auth_profile, NoAuthProfile):
        return base
    if "base_kwargs" in base:
        return {**base, "base_kwargs": auth_profile.emit(family, base=base["base_kwargs"])}
    return auth_profile.emit(family, base=base)


def create_connection(
    profile: ProfileProtocol,
    auth_profile: AuthProfile | None = None,
    *,
    auto_authorize: bool = False,
) -> ConnectionProtocol:
    """Create the right connection for a profile + auth combination."""
    from mountainash_auth_client import OAuth2AuthProfile, OAuth2AuthCodeAuthProfile

    if isinstance(auth_profile, (OAuth2AuthProfile, OAuth2AuthCodeAuthProfile)):
        return OAuth2Connection(profile, auth_profile, auto_authorize=auto_authorize)

    try:
        from mountainash_auth_client.schemas.oauth1 import OAuth1AuthProfile
        if isinstance(auth_profile, OAuth1AuthProfile):
            return OAuth1Connection(profile, auth_profile, auto_authorize=auto_authorize)
    except ImportError:
        pass

    provider_type = _provider_type_from_profile(profile)
    family = _family_for_provider(provider_type)

    if provider_type == CONST_STORAGE_PROVIDER_TYPE.SFTP:
        ssh_conn = SSHConnection(_emit_kwargs(profile, auth_profile, family))
        return SFTPConnection(ssh_conn)

    leaf_cls = _connection_for_provider(provider_type)
    if leaf_cls is NullConnection:
        return NullConnection()
    return leaf_cls(_emit_kwargs(profile, auth_profile, family))


def create_tunnelled_connection(
    bastion_profile: ProfileProtocol,
    bastion_auth: AuthProfile | None,
    target_profile: ProfileProtocol,
    target_auth: AuthProfile | None,
    remote_host: str,
    remote_port: int,
) -> TunnelledConnection:
    """Create a tunnelled connection through an SSH bastion host."""
    bastion_family = _family_for_provider(CONST_STORAGE_PROVIDER_TYPE.SSH)
    ssh_conn = SSHConnection(_emit_kwargs(bastion_profile, bastion_auth, bastion_family))

    def inner_factory(local_port: int) -> ConnectionProtocol:
        patched = _PatchedEndpointProfile(target_profile, "127.0.0.1", local_port)
        return create_connection(patched, target_auth)

    return TunnelledConnection(ssh_conn, inner_factory, remote_host, remote_port)


__all__ = [
    # Legacy
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
