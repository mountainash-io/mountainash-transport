"""Tests for connection error types."""
from __future__ import annotations

import pytest

from mountainash_transport.connections.errors import (
    AuthorizationRequired,
    ConnectionError,
    TokenExchangeError,
    TokenRefreshError,
)


class TestConnectionErrorBase:
    def test_all_errors_inherit_from_connection_error(self):
        assert issubclass(TokenExchangeError, ConnectionError)
        assert issubclass(TokenRefreshError, ConnectionError)
        assert issubclass(AuthorizationRequired, ConnectionError)

    def test_connection_error_is_exception(self):
        assert issubclass(ConnectionError, Exception)


class TestTokenExchangeError:
    def test_attributes_stored(self):
        err = TokenExchangeError(url="https://example.com/token", status_code=400, body='{"error":"invalid_grant"}')
        assert err.url == "https://example.com/token"
        assert err.status_code == 400
        assert err.body == '{"error":"invalid_grant"}'

    def test_str_contains_status_code(self):
        err = TokenExchangeError(url="https://example.com/token", status_code=401, body="Unauthorized")
        assert "401" in str(err)

    def test_str_contains_url(self):
        err = TokenExchangeError(url="https://example.com/token", status_code=400, body="bad")
        assert "https://example.com/token" in str(err)

    def test_body_truncated_in_str(self):
        long_body = "Z" * 500
        err = TokenExchangeError(url="https://auth.test/token", status_code=400, body=long_body)
        assert str(err).count("Z") <= 200

    def test_can_be_raised_and_caught(self):
        with pytest.raises(TokenExchangeError) as exc_info:
            raise TokenExchangeError(url="https://example.com/token", status_code=500, body="server error")
        assert exc_info.value.status_code == 500

    def test_catchable_as_connection_error(self):
        with pytest.raises(ConnectionError):
            raise TokenExchangeError(url="https://example.com/token", status_code=400, body="err")


class TestTokenRefreshError:
    def test_attributes_stored(self):
        err = TokenRefreshError(url="https://example.com/refresh", status_code=401, body="expired")
        assert err.url == "https://example.com/refresh"
        assert err.status_code == 401
        assert err.body == "expired"

    def test_str_contains_status_code(self):
        err = TokenRefreshError(url="https://example.com/refresh", status_code=403, body="forbidden")
        assert "403" in str(err)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(TokenRefreshError) as exc_info:
            raise TokenRefreshError(url="https://example.com/refresh", status_code=401, body="expired")
        assert exc_info.value.url == "https://example.com/refresh"


class TestAuthorizationRequired:
    def test_attributes_stored(self):
        err = AuthorizationRequired(provider="fitbit", user="alice")
        assert err.provider == "fitbit"
        assert err.user == "alice"

    def test_str_contains_provider(self):
        err = AuthorizationRequired(provider="whoop", user="bob")
        assert "whoop" in str(err)

    def test_str_contains_user(self):
        err = AuthorizationRequired(provider="fitbit", user="charlie")
        assert "charlie" in str(err)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(AuthorizationRequired) as exc_info:
            raise AuthorizationRequired(provider="oura", user="eve")
        assert exc_info.value.provider == "oura"
