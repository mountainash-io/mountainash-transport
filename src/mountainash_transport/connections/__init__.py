"""Connection infrastructure — OAuth flows, callback servers, token lifecycle, and factory."""
from __future__ import annotations

import typing as t

from mountainash_auth_client import CONST_AUTH_PROFILES
from mountainash_auth_client.targets import TargetFamily

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.settings.profile_protocol import ProfileProtocol

# --- Legacy/existing public API (kept for backward compat) -------------------
from .errors import (
    ConnectionError, TokenExchangeError, TokenRefreshError, AuthorizationRequired,
    TransportConnectionError, ConnectionTimeoutError,
)
from mountainash_auth_client.oauth.oauth2.flow import OAuthFlow
from mountainash_auth_client.oauth.oauth1.flow import OAuth1Flow
from mountainash_auth_client.oauth.server.callback import LocalCallbackServer
from mountainash_auth_client.oauth.server.manual import (
    extract_code_from_input, prompt_for_code,
)

# --- New connection classes ---------------------------------------------------
from .http import HTTPConnection
from .null import NullConnection
from .s3 import S3Connection
from .ssh import SSHConnection
from .sftp import SFTPConnection
from .tunnel import TunnelledConnection, _PatchedEndpointProfile
from .auth_strategy import OAuth2RefreshableAuthStrategy, create_auth_strategy

if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthProfile
    from mountainash_transport._core.protocols import ConnectionProtocol


def _auth_kind(auth_profile: "AuthProfile | None") -> CONST_AUTH_PROFILES:
    """Derive the auth mode from an auth profile's spec provider_type.

    None → NONE. Every *AuthProfile's __spec__.provider_type string is a
    CONST_AUTH_PROFILES member value (e.g. "iam", "token", "none").
    """
    if auth_profile is None:
        return CONST_AUTH_PROFILES.NONE
    provider_type = getattr(getattr(auth_profile, "__spec__", None), "provider_type", None)
    if provider_type is None:
        return CONST_AUTH_PROFILES.NONE
    return CONST_AUTH_PROFILES(str(provider_type))


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


_NON_STS_FLAVORS = frozenset({"r2", "minio", "b2"})


def _emit_kwargs(
    profile: ProfileProtocol,
    auth_profile: AuthProfile | None,
    family: TargetFamily | None,
) -> dict[str, t.Any]:
    """Assemble connection kwargs. For BOTO with ROLE_ARN/PROFILE_NAME, build a
    Session-instruction envelope (consumed by S3Connection); otherwise layer
    credentials flat. Performs NO I/O."""
    from mountainash_auth_client import NoAuthProfile

    if family is None:
        return profile.to_handler_kwargs()

    emit = getattr(profile, "emit", None)
    base = emit(family) if callable(emit) else profile.to_handler_kwargs()

    if auth_profile is None or isinstance(auth_profile, NoAuthProfile):
        return base

    if family is TargetFamily.BOTO:
        role_arn = getattr(auth_profile, "ROLE_ARN", None)
        profile_name = getattr(auth_profile, "PROFILE_NAME", None)
        if role_arn or profile_name:
            flavor = getattr(profile, "FLAVOR", "aws")
            if role_arn and flavor in _NON_STS_FLAVORS:
                raise ValueError(
                    f"assume-role (ROLE_ARN) is not supported for S3 flavor {flavor!r}; "
                    "only aws/express reach AWS STS."
                )
            session: dict[str, t.Any] = dict(auth_profile.emit(family))  # aws_* creds or {}
            if profile_name:
                session["profile_name"] = profile_name
            if "region_name" in base:
                session["region_name"] = base["region_name"]
            return {
                "client_config": base,
                "session": session,
                "role_arn": role_arn,
                "session_name": "mountainash-transport",
            }

    return auth_profile.emit(family, base=base)


def create_connection(
    profile: ProfileProtocol,
    auth_profile: AuthProfile | None = None,
    *,
    auto_authorize: bool = False,
) -> ConnectionProtocol:
    """Create the right connection for a profile + auth combination."""
    spec = getattr(profile, "__spec__", None)
    supported = getattr(spec, "supported_auth", None)
    if supported is not None:
        mode = _auth_kind(auth_profile)
        if mode not in supported:
            from .errors import UnsupportedAuthProfileError
            name = type(auth_profile).__name__ if auth_profile else "NoAuth"
            raise UnsupportedAuthProfileError(
                name,
                reason=f"mode {mode.value!r} not in supported_auth "
                       f"{sorted(m.value for m in supported)}",
            )

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
    "HTTPConnection", "NullConnection", "S3Connection",
    "SSHConnection", "SFTPConnection", "TunnelledConnection",
    "OAuth2RefreshableAuthStrategy", "create_auth_strategy",
    "create_connection", "create_tunnelled_connection",
]
