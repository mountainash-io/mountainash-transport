"""Tests for OAuth1ConnectionMixin."""
from __future__ import annotations

import pytest

from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.oauth1.mixin import OAuth1ConnectionMixin


class FakeOAuth1Provider(OAuth1ConnectionMixin):
    _spec = type("S", (), {
        "name": "testprovider_oauth1",
        "metadata": {
            "request_token_url": "https://auth.example.com/oauth/request_token",
            "authorize_url": "https://auth.example.com/oauth/authorize",
            "access_token_url": "https://auth.example.com/oauth/access_token",
        },
    })()
    _base_url = "https://api.example.com"
    _client = None


class TestOAuth1MixinNoToken:
    def test_raises_authorization_required_when_no_token(self, memory_backend, fake_oauth1_auth):
        provider = FakeOAuth1Provider()
        with pytest.raises(AuthorizationRequired) as exc_info:
            provider.connect(fake_oauth1_auth)
        assert exc_info.value.provider == "testprovider_oauth1"


class TestOAuth1MixinClientProperty:
    def test_client_none_before_connect(self):
        provider = FakeOAuth1Provider()
        assert provider.client is None


class TestOAuth1MixinDisconnect:
    def test_disconnect_sets_client_to_none(self):
        import httpx
        provider = FakeOAuth1Provider()
        provider._client = httpx.Client()
        assert provider.client is not None
        provider.disconnect()
        assert provider.client is None

    def test_context_manager_calls_disconnect(self):
        import httpx
        provider = FakeOAuth1Provider()
        provider._client = httpx.Client()
        provider.__enter__()
        provider.__exit__(None, None, None)
        assert provider.client is None


class TestOAuth1MixinAuthlibRequired:
    def test_build_client_requires_authlib(self, monkeypatch, fake_oauth1_auth):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "authlib.integrations.httpx_client":
                raise ImportError("No module named 'authlib'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        provider = FakeOAuth1Provider()
        with pytest.raises(ImportError, match="authlib"):
            provider._build_client(
                {"oauth_token": "tok", "oauth_token_secret": "sec"},
                fake_oauth1_auth,
            )
