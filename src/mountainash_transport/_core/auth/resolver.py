"""Auth strategy resolver — map auth profiles to strategies."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.auth.strategies import (
    AuthStrategy,
    BasicAuthStrategy,
    BearerTokenStrategy,
    IAMCredentialStrategy,
    NoAuthStrategy,
    SSHKeyStrategy,
    SSHKerberosStrategy,
    SSHPasswordStrategy,
)
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.settings.utils.secrets import _unwrap_secret

if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthProfile

from mountainash_auth_client import (
    CertificateAuth,
    IAMAuth,
    JWTAuth,
    KerberosAuth,
    NoAuth,
    OAuth2Auth,
    OAuth2AuthCodeAuth,
    PasswordAuth,
    TokenAuth,
)


def _resolve_ssh_strategy(auth_profile: object) -> AuthStrategy | None:
    """Map an auth profile to an SSH-specific strategy.

    Returns ``None`` if the profile type is not SSH-relevant; the caller
    falls through to ``NoAuthStrategy`` in that case.
    """
    if isinstance(auth_profile, PasswordAuth):
        password = _unwrap_secret(auth_profile.PASSWORD) or ""
        return SSHPasswordStrategy(password)

    if isinstance(auth_profile, CertificateAuth):
        key_path = str(auth_profile.PRIVATE_KEY_PATH) if auth_profile.PRIVATE_KEY_PATH else None
        key_string = _unwrap_secret(auth_profile.PRIVATE_KEY) if auth_profile.PRIVATE_KEY else None
        passphrase = _unwrap_secret(auth_profile.PASSPHRASE) if auth_profile.PASSPHRASE else None
        return SSHKeyStrategy(key_path=key_path, key_string=key_string, passphrase=passphrase)

    if isinstance(auth_profile, KerberosAuth):
        return SSHKerberosStrategy(gss_host=auth_profile.SERVICE_NAME)

    return None


def resolve_auth_strategy(
    auth_profile: AuthProfile | None,
    provider_type: CONST_STORAGE_PROVIDER_TYPE | None = None,
) -> AuthStrategy:
    """Map an auth profile instance to its auth strategy."""
    if auth_profile is None:
        return NoAuthStrategy()

    if isinstance(auth_profile, NoAuth):
        return NoAuthStrategy()

    if provider_type == CONST_STORAGE_PROVIDER_TYPE.SSH:
        ssh_strategy = _resolve_ssh_strategy(auth_profile)
        if ssh_strategy is not None:
            return ssh_strategy
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

    if isinstance(auth_profile, IAMAuth):
        return IAMCredentialStrategy(
            access_key_id=auth_profile.ACCESS_KEY_ID,
            secret_access_key=_unwrap_secret(auth_profile.SECRET_ACCESS_KEY),
            session_token=_unwrap_secret(auth_profile.SESSION_TOKEN) if auth_profile.SESSION_TOKEN else None,
        )

    if isinstance(auth_profile, PasswordAuth):
        username = auth_profile.USERNAME or ""
        password = _unwrap_secret(auth_profile.PASSWORD) or ""
        return BasicAuthStrategy(username, password)

    return NoAuthStrategy()
