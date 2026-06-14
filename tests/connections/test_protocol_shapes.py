"""Protocol conformance tests for connection protocols."""
from __future__ import annotations

from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.connections.null import NullConnection


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

    def test_object_does_not_conform(self):
        assert not isinstance(object(), ConnectionProtocol)
