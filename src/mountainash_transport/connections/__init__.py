"""Connection infrastructure — OAuth flows, callback servers, token lifecycle."""
from __future__ import annotations

__all__ = [
    "OAuth2FlowProtocol", "OAuth1FlowProtocol",
    "CallbackServerProtocol", "ConnectionMixinProtocol",
    "ConnectionError", "TokenExchangeError", "TokenRefreshError", "AuthorizationRequired",
    "OAuthFlow", "OAuth2ConnectionMixin",
    "OAuth1Flow", "OAuth1ConnectionMixin",
    "LocalCallbackServer", "extract_code_from_input", "prompt_for_code",
]

from .protocols import (
    OAuth2FlowProtocol, OAuth1FlowProtocol,
    CallbackServerProtocol, ConnectionMixinProtocol,
)
from .errors import ConnectionError, TokenExchangeError, TokenRefreshError, AuthorizationRequired
from .oauth2.flow import OAuthFlow
from .oauth2.mixin import OAuth2ConnectionMixin
from .oauth1.flow import OAuth1Flow
from .oauth1.mixin import OAuth1ConnectionMixin
from .server.callback import LocalCallbackServer
from .server.manual import extract_code_from_input, prompt_for_code
