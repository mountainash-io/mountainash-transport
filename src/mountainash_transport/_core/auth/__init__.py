"""Auth strategies — credential injection for SDK clients."""
from __future__ import annotations

from .strategies import (
    AuthStrategy,
    BasicAuthStrategy,
    BearerTokenStrategy,
    IAMCredentialStrategy,
    NoAuthStrategy,
    OAuth1SignedStrategy,
    SSHKeyStrategy,
    SSHKerberosStrategy,
    SSHPasswordStrategy,
)
from .resolver import resolve_auth_strategy

__all__ = [
    "AuthStrategy",
    "BasicAuthStrategy",
    "BearerTokenStrategy",
    "IAMCredentialStrategy",
    "NoAuthStrategy",
    "OAuth1SignedStrategy",
    "SSHKeyStrategy",
    "SSHKerberosStrategy",
    "SSHPasswordStrategy",
    "resolve_auth_strategy",
]
