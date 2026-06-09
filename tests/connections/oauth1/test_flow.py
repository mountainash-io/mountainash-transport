"""Tests for OAuth1Flow."""
from __future__ import annotations

import pytest

from mountainash_transport.connections.oauth1.flow import OAuth1Flow


class TestOAuth1FlowBuildAuthorizeUrl:
    def test_contains_oauth_token_param(self, fake_oauth1_spec):
        flow = OAuth1Flow(fake_oauth1_spec)
        url = flow.build_authorize_url("test_oauth_token_123")
        assert "oauth_token=test_oauth_token_123" in url

    def test_contains_authorize_base_url(self, fake_oauth1_spec):
        flow = OAuth1Flow(fake_oauth1_spec)
        url = flow.build_authorize_url("tok")
        assert "https://auth.example.com/oauth/authorize" in url

    def test_properties_read_from_metadata(self, fake_oauth1_spec):
        flow = OAuth1Flow(fake_oauth1_spec)
        assert flow.request_token_url == "https://auth.example.com/oauth/request_token"
        assert flow.authorize_url == "https://auth.example.com/oauth/authorize"
        assert flow.access_token_url == "https://auth.example.com/oauth/access_token"


class TestOAuth1FlowAuthlib:
    def test_request_token_requires_authlib(self, fake_oauth1_spec, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "authlib.integrations.httpx_client":
                raise ImportError("No module named 'authlib'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        flow = OAuth1Flow(fake_oauth1_spec)
        with pytest.raises(ImportError, match="authlib"):
            flow.request_token("consumer_key", "consumer_secret")

    def test_exchange_verifier_requires_authlib(self, fake_oauth1_spec, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "authlib.integrations.httpx_client":
                raise ImportError("No module named 'authlib'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        flow = OAuth1Flow(fake_oauth1_spec)
        with pytest.raises(ImportError, match="authlib"):
            flow.exchange_verifier("ck", "cs", "tok", "tok_sec", "verifier")
