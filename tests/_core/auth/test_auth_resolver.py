"""Tests for resolve_auth_strategy() dispatch."""
from __future__ import annotations

import pytest

from mountainash_transport._core.auth.resolver import resolve_auth_strategy
from mountainash_transport._core.auth.strategies import (
    AuthStrategy,
    BasicAuthStrategy,
    BearerTokenStrategy,
    NoAuthStrategy,
)


class TestResolveAuthStrategy:
    def test_none_returns_no_auth(self):
        strategy = resolve_auth_strategy(None)
        assert isinstance(strategy, NoAuthStrategy)

    def test_returns_auth_strategy(self):
        strategy = resolve_auth_strategy(None)
        assert isinstance(strategy, AuthStrategy)

    def test_unknown_type_returns_no_auth(self):
        strategy = resolve_auth_strategy(object())
        assert isinstance(strategy, NoAuthStrategy)

    def test_no_auth_profile(self):
        from mountainash_auth_client import NoAuth
        strategy = resolve_auth_strategy(NoAuth())
        assert isinstance(strategy, NoAuthStrategy)

    def test_token_auth_profile(self):
        from mountainash_auth_client import TokenAuth
        auth = TokenAuth(TOKEN="my-token")
        strategy = resolve_auth_strategy(auth)
        assert isinstance(strategy, BearerTokenStrategy)
        result = strategy.apply({})
        assert result["headers"]["Authorization"] == "Bearer my-token"

    def test_password_auth_profile(self):
        from mountainash_auth_client import PasswordAuth
        auth = PasswordAuth(USERNAME="admin", PASSWORD="secret")
        strategy = resolve_auth_strategy(auth)
        assert isinstance(strategy, BasicAuthStrategy)
        result = strategy.apply({})
        assert "Basic " in result["headers"]["Authorization"]

    def test_jwt_auth_profile(self):
        from mountainash_auth_client import JWTAuth
        auth = JWTAuth(TOKEN="jwt-tok")
        strategy = resolve_auth_strategy(auth)
        assert isinstance(strategy, BearerTokenStrategy)
        result = strategy.apply({})
        assert result["headers"]["Authorization"] == "Bearer jwt-tok"

    def test_oauth2_auth_with_token(self):
        from mountainash_auth_client import OAuth2Auth
        auth = OAuth2Auth(TOKEN="oauth2-tok")
        strategy = resolve_auth_strategy(auth)
        assert isinstance(strategy, BearerTokenStrategy)

    def test_oauth2_authcode_with_token(self):
        from mountainash_auth_client import OAuth2AuthCodeAuth
        auth = OAuth2AuthCodeAuth(CLIENT_ID="cid", CLIENT_SECRET="csec", ACCESS_TOKEN="authcode-tok")
        strategy = resolve_auth_strategy(auth)
        assert isinstance(strategy, BearerTokenStrategy)
