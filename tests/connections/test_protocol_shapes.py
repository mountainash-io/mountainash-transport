"""Protocol conformance tests for connection protocols."""
from __future__ import annotations

from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.connections.null import NullConnection


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
