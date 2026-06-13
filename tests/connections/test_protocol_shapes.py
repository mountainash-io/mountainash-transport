"""Protocol conformance tests for connection protocols."""
from __future__ import annotations

import pytest

from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.connections.null import NullConnection
from mountainash_transport.connections.protocols import (
    OAuth2FlowProtocol,
    OAuth1FlowProtocol,
    CallbackServerProtocol,
)


class FakeOAuth2Spec:
    name = "testprovider"
    def __init__(self, metadata=None):
        self._metadata = metadata or {
            "authorize_url": "https://auth.example.com/authorize",
            "token_url": "https://auth.example.com/token",
        }
    @property
    def metadata(self):
        return self._metadata


class FakeOAuth1Spec:
    name = "testprovider_oauth1"
    def __init__(self, metadata=None):
        self._metadata = metadata or {
            "request_token_url": "https://auth.example.com/oauth/request_token",
            "authorize_url": "https://auth.example.com/oauth/authorize",
            "access_token_url": "https://auth.example.com/oauth/access_token",
        }
    @property
    def metadata(self):
        return self._metadata


class FakeProfile:
    def to_handler_kwargs(self) -> dict:
        return {"timeout": 30}
    def get_connection_url(self) -> str:
        return "https://example.com"


# ---------------------------------------------------------------------------
# ConnectionProtocol conformance
# ---------------------------------------------------------------------------

class TestConnectionProtocolConformance:
    def test_http_connection_conforms(self):
        conn = HTTPConnection({})
        assert isinstance(conn, ConnectionProtocol)

    def test_null_connection_conforms(self):
        assert isinstance(NullConnection(), ConnectionProtocol)

    def test_s3_connection_conforms(self):
        from mountainash_transport.connections.s3 import S3Connection
        conn = S3Connection({})
        assert isinstance(conn, ConnectionProtocol)

    def test_oauth2_connection_conforms(self):
        from mountainash_transport.connections.oauth2.connection import OAuth2Connection

        class FakeOAuth2Profile(FakeProfile):
            __spec__ = FakeOAuth2Spec()

        class FakeAuth:
            CLIENT_ID = "cid"
            CLIENT_SECRET = property(lambda self: type("S", (), {"get_secret_value": lambda s: "csec"})())
            SCOPE = "read"
            SETTINGS_SOURCE_SECRETS_PROVIDER = "test_mem"
            def persist_key(self): return "test.oauth2"

        conn = OAuth2Connection(FakeOAuth2Profile(), FakeAuth())
        assert isinstance(conn, ConnectionProtocol)

    def test_oauth1_connection_conforms(self):
        from mountainash_transport.connections.oauth1.connection import OAuth1Connection

        class FakeOAuth1Profile(FakeProfile):
            __spec__ = FakeOAuth1Spec()

        class FakeAuth:
            CONSUMER_KEY = "ck"
            CONSUMER_SECRET = property(lambda self: type("S", (), {"get_secret_value": lambda s: "cs"})())
            SETTINGS_SOURCE_SECRETS_PROVIDER = "test_mem"
            def persist_key(self): return "test.oauth1"

        conn = OAuth1Connection(FakeOAuth1Profile(), FakeAuth())
        assert isinstance(conn, ConnectionProtocol)

    def test_object_does_not_conform(self):
        assert not isinstance(object(), ConnectionProtocol)


# ---------------------------------------------------------------------------
# OAuth2FlowProtocol (unchanged)
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
        assert isinstance(OAuthFlow(FakeOAuth2Spec()), OAuth2FlowProtocol)


# ---------------------------------------------------------------------------
# OAuth1FlowProtocol (unchanged)
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
        assert isinstance(OAuth1Flow(FakeOAuth1Spec()), OAuth1FlowProtocol)


# ---------------------------------------------------------------------------
# CallbackServerProtocol (unchanged)
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
