"""Tests for connection error types."""
from __future__ import annotations

import pytest

from mountainash_transport.connections.errors import (
    TransportConnectionError,
    ConnectionTimeoutError,
    UnsupportedAuthProfileError,
)


class TestTransportConnectionError:
    def test_is_exception(self):
        assert issubclass(TransportConnectionError, Exception)


class TestConnectionTimeoutError:
    def test_is_subclass_of_transport_connection_error(self):
        assert issubclass(ConnectionTimeoutError, TransportConnectionError)

    def test_message(self):
        err = ConnectionTimeoutError("timed out connecting to host")
        assert "timed out" in str(err)


class TestUnsupportedAuthProfileError:
    def test_is_transport_connection_error(self):
        assert issubclass(UnsupportedAuthProfileError, TransportConnectionError)

    def test_message_names_the_profile(self):
        err = UnsupportedAuthProfileError("OAuth2AuthProfile")
        assert "OAuth2AuthProfile" in str(err)
        # Points callers at the right home for OAuth-authenticated connections.
        assert "auth-client" in str(err) or "ProviderProfile" in str(err)

    def test_stores_profile_name(self):
        assert UnsupportedAuthProfileError("X").profile_name == "X"

    def test_raisable_as_transport_connection_error(self):
        with pytest.raises(TransportConnectionError):
            raise UnsupportedAuthProfileError("X")
