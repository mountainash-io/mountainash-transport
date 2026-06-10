"""Tests that create_connection() accepts ProfileProtocol-only profiles."""
from __future__ import annotations

import pytest

from mountainash_transport.connections import create_connection
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.connections.null import NullConnection
from mountainash_transport.settings.profile_protocol import ProfileProtocol


class BareHTTPProfile:
    """ProfileProtocol-only — no get_connection_url()."""

    class __spec__:
        provider_type = "http"

    def to_handler_kwargs(self) -> dict:
        return {"timeout": 30}


class BareLocalProfile:
    """ProfileProtocol-only — no get_connection_url()."""

    class __spec__:
        provider_type = "local"

    def to_handler_kwargs(self) -> dict:
        return {}


@pytest.mark.unit
class TestFactoryAcceptsProfileProtocol:
    def test_bare_profile_satisfies_profile_protocol(self):
        assert isinstance(BareHTTPProfile(), ProfileProtocol)

    def test_bare_http_profile_creates_http_connection(self):
        conn = create_connection(BareHTTPProfile())
        assert isinstance(conn, HTTPConnection)

    def test_bare_local_profile_creates_null_connection(self):
        conn = create_connection(BareLocalProfile())
        assert isinstance(conn, NullConnection)
