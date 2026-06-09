"""Tests for OAuth2ConnectionMixin."""
from __future__ import annotations

import time

import pytest

from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.oauth2.mixin import OAuth2ConnectionMixin


class FakeProvider(OAuth2ConnectionMixin):
    _spec = type("S", (), {
        "name": "testprovider",
        "metadata": {
            "authorize_url": "https://auth.example.com/authorize",
            "token_url": "https://auth.example.com/token",
        },
    })()
    _base_url = "https://api.example.com"
    _client = None


class TestOAuth2MixinNoToken:
    def test_raises_authorization_required_when_no_token(self, memory_backend, fake_oauth2_auth):
        provider = FakeProvider()
        with pytest.raises(AuthorizationRequired) as exc_info:
            provider.connect(fake_oauth2_auth)
        assert exc_info.value.provider == "testprovider"


class TestOAuth2MixinWithToken:
    def test_connects_with_valid_stored_token(self, memory_backend, fake_oauth2_auth):
        memory_backend.set("test.oauth2", {
            "access_token": "tok_abc",
            "refresh_token": "refresh_xyz",
            "token_expires_at": int(time.time()) + 3600,
        })
        provider = FakeProvider()
        result = provider.connect(fake_oauth2_auth)
        assert result is provider
        provider.disconnect()

    def test_client_is_set_after_connect(self, memory_backend, fake_oauth2_auth):
        memory_backend.set("test.oauth2", {
            "access_token": "tok_abc",
            "refresh_token": "refresh_xyz",
            "token_expires_at": int(time.time()) + 3600,
        })
        provider = FakeProvider()
        provider.connect(fake_oauth2_auth)
        assert provider.client is not None
        provider.disconnect()

    def test_client_has_bearer_auth_header(self, memory_backend, fake_oauth2_auth):
        memory_backend.set("test.oauth2", {
            "access_token": "tok_abc",
            "refresh_token": "refresh_xyz",
            "token_expires_at": int(time.time()) + 3600,
        })
        provider = FakeProvider()
        provider.connect(fake_oauth2_auth)
        auth_header = provider.client.headers.get("authorization", "")
        assert "Bearer tok_abc" in auth_header
        provider.disconnect()


class TestOAuth2MixinExpiredToken:
    def test_raises_when_expired_no_refresh(self, memory_backend, fake_oauth2_auth):
        memory_backend.set("test.oauth2", {
            "access_token": "old_tok",
            "refresh_token": None,
            "token_expires_at": int(time.time()) - 1000,
        })
        provider = FakeProvider()
        with pytest.raises(AuthorizationRequired):
            provider.connect(fake_oauth2_auth)


class TestOAuth2MixinDisconnect:
    def test_disconnect_sets_client_to_none(self, memory_backend, fake_oauth2_auth):
        memory_backend.set("test.oauth2", {
            "access_token": "tok",
            "refresh_token": "ref",
            "token_expires_at": int(time.time()) + 3600,
        })
        provider = FakeProvider()
        provider.connect(fake_oauth2_auth)
        assert provider.client is not None
        provider.disconnect()
        assert provider.client is None

    def test_context_manager_calls_disconnect(self, memory_backend, fake_oauth2_auth):
        memory_backend.set("test.oauth2", {
            "access_token": "tok",
            "refresh_token": "ref",
            "token_expires_at": int(time.time()) + 3600,
        })
        provider = FakeProvider()
        provider.connect(fake_oauth2_auth)
        provider.__enter__()
        provider.__exit__(None, None, None)
        assert provider.client is None


class TestClientProperty:
    def test_client_none_before_connect(self):
        provider = FakeProvider()
        assert provider.client is None
