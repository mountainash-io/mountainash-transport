"""Protocol conformance tests for connection protocols."""
from __future__ import annotations

import pytest

from mountainash_transport.connections.protocols import (
    OAuth2FlowProtocol,
    OAuth1FlowProtocol,
    CallbackServerProtocol,
    ConnectionMixinProtocol,
)


# ---------------------------------------------------------------------------
# OAuth2FlowProtocol
# ---------------------------------------------------------------------------

class GoodOAuth2Flow:
    def build_authorize_url(self, client_id, redirect_uri, scope=None): ...
    def exchange_code(self, code, redirect_uri, client_id, client_secret, scope=None, state=None): ...
    def refresh(self, refresh_token, client_id, client_secret): ...
    @staticmethod
    def is_expired(token_expires_at, buffer_seconds=300): ...
    def authorize(self, client_id, client_secret, redirect_mode="local_server", scope=None): ...


class BadOAuth2Flow:
    def build_authorize_url(self, client_id, redirect_uri, scope=None): ...


class TestOAuth2FlowProtocol:
    def test_positive_conformance(self):
        assert isinstance(GoodOAuth2Flow(), OAuth2FlowProtocol)

    def test_negative_conformance(self):
        assert not isinstance(BadOAuth2Flow(), OAuth2FlowProtocol)

    def test_empty_class_does_not_conform(self):
        assert not isinstance(object(), OAuth2FlowProtocol)

    def test_real_implementation_conforms(self):
        from mountainash_transport.connections.oauth2.flow import OAuthFlow
        from tests.connections.conftest import FakeOAuth2Spec
        assert isinstance(OAuthFlow(FakeOAuth2Spec()), OAuth2FlowProtocol)


# ---------------------------------------------------------------------------
# OAuth1FlowProtocol
# ---------------------------------------------------------------------------

class GoodOAuth1Flow:
    def build_authorize_url(self, oauth_token): ...
    def request_token(self, consumer_key, consumer_secret, callback_url="oob"): ...
    def exchange_verifier(self, consumer_key, consumer_secret, oauth_token, oauth_token_secret, verifier): ...
    def authorize(self, consumer_key, consumer_secret, redirect_mode="local_server"): ...


class BadOAuth1Flow:
    def build_authorize_url(self, oauth_token): ...


class TestOAuth1FlowProtocol:
    def test_positive_conformance(self):
        assert isinstance(GoodOAuth1Flow(), OAuth1FlowProtocol)

    def test_negative_conformance(self):
        assert not isinstance(BadOAuth1Flow(), OAuth1FlowProtocol)

    def test_empty_class_does_not_conform(self):
        assert not isinstance(object(), OAuth1FlowProtocol)

    def test_real_implementation_conforms(self):
        from mountainash_transport.connections.oauth1.flow import OAuth1Flow
        from tests.connections.conftest import FakeOAuth1Spec
        assert isinstance(OAuth1Flow(FakeOAuth1Spec()), OAuth1FlowProtocol)


# ---------------------------------------------------------------------------
# CallbackServerProtocol
# ---------------------------------------------------------------------------

class GoodCallbackServer:
    @property
    def port(self): return 0
    @property
    def redirect_uri(self): return ""
    def wait_for_callback(self): ...


class BadCallbackServer:
    @property
    def port(self): return 0


class TestCallbackServerProtocol:
    def test_positive_conformance(self):
        assert isinstance(GoodCallbackServer(), CallbackServerProtocol)

    def test_negative_conformance(self):
        assert not isinstance(BadCallbackServer(), CallbackServerProtocol)

    def test_empty_class_does_not_conform(self):
        assert not isinstance(object(), CallbackServerProtocol)

    def test_real_implementation_conforms(self):
        from mountainash_transport.connections.server.callback import LocalCallbackServer
        server = LocalCallbackServer(port=0, timeout=1)
        assert isinstance(server, CallbackServerProtocol)
        server._server.server_close()


# ---------------------------------------------------------------------------
# ConnectionMixinProtocol
# ---------------------------------------------------------------------------

class GoodConnectionMixin:
    def connect(self, auth, *, auto_authorize=False): ...
    def disconnect(self): ...
    @property
    def client(self): return None


class BadConnectionMixin:
    def connect(self, auth): ...


class TestConnectionMixinProtocol:
    def test_positive_conformance(self):
        assert isinstance(GoodConnectionMixin(), ConnectionMixinProtocol)

    def test_negative_conformance(self):
        assert not isinstance(BadConnectionMixin(), ConnectionMixinProtocol)

    def test_empty_class_does_not_conform(self):
        assert not isinstance(object(), ConnectionMixinProtocol)
