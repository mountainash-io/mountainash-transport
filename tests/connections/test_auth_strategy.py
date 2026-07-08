import pytest
from mountainash_auth_client import OAuth2AuthProfile
from mountainash_transport.connections.auth_strategy import (
    OAuth2RefreshableAuthStrategy, create_auth_strategy,
)


class _FakeCred:
    def __init__(self, tok): self.access_token, self.token_type = tok, "Bearer"


class _FakeMgr:
    def __init__(self): self.acquired = self.refreshed = 0
    def acquire(self): self.acquired += 1; return _FakeCred("A")
    def refresh(self): self.refreshed += 1; return _FakeCred("B")


def test_get_headers_acquires_once_and_caches():
    mgr = _FakeMgr()
    s = OAuth2RefreshableAuthStrategy(mgr)
    assert s.get_headers() == {"Authorization": "Bearer A"}
    assert s.get_headers() == {"Authorization": "Bearer A"}   # cached
    assert mgr.acquired == 1


def test_refresh_updates_header():
    mgr = _FakeMgr()
    s = OAuth2RefreshableAuthStrategy(mgr)
    s.get_headers()
    assert s.refresh() is True
    assert s.get_headers() == {"Authorization": "Bearer B"}
    assert mgr.refreshed == 1


def test_apply_is_noop_but_returns_new_dict():
    s = OAuth2RefreshableAuthStrategy(_FakeMgr())
    original = {"x": 1}
    result = s.apply(original)
    assert result == {"x": 1}
    assert result is not original      # honours the protocol's "new dict" contract


class _FakeProvider:   # stand-in for OAuth2ProviderProfileProtocol
    NAME = "idp"


def test_no_provider_returns_none():
    assert create_auth_strategy(OAuth2AuthProfile(ACCESS_TOKEN="t")) is None


def test_provider_without_resolver_raises():
    with pytest.raises((ValueError, TypeError)):
        create_auth_strategy(OAuth2AuthProfile(), oauth_provider=_FakeProvider())


def test_provider_and_resolver_builds_strategy(monkeypatch):
    import mountainash_transport.connections.auth_strategy as mod
    monkeypatch.setattr(mod, "OAuth2TokenManager", lambda *a, **k: object())
    s = create_auth_strategy(OAuth2AuthProfile(), oauth_provider=_FakeProvider(),
                             secret_resolver=object())
    assert isinstance(s, OAuth2RefreshableAuthStrategy)


def test_non_oauth2_auth_with_provider_raises():
    """A stray oauth_provider paired with a non-OAuth2 auth profile is a
    misconfiguration — surfaced fail-closed, not silently ignored."""
    from mountainash_auth_client import NoAuthProfile
    with pytest.raises(ValueError):
        create_auth_strategy(NoAuthProfile(), oauth_provider=_FakeProvider(),
                             secret_resolver=object())
