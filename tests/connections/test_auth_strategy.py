import time

import httpx
import pytest
from mountainash_auth_client import OAuth2AuthProfile, OAuth2TokenManager
from mountainash_auth_client.errors import AuthorizationRequired
from mountainash_settings.secrets import MemorySecretStore
from mountainash_transport.connections.auth_strategy import (
    OAuth2RefreshableAuthStrategy, create_auth_strategy,
)


def _record(token="A"):
    return {
        "access_token": token,
        "refresh_token": "refresh-token",
        "token_type": "Bearer",
        "token_expires_at": int(time.time()) + 3600,
    }


def _managed(store):
    auth = OAuth2AuthProfile()
    key = f"oauth.{auth.persist_key()}"
    store.set(key, _record())
    manager = OAuth2TokenManager(_FakeProvider(), auth, token_store=store)
    return OAuth2RefreshableAuthStrategy(manager), manager, key


@pytest.fixture
def endpoint_calls(monkeypatch):
    calls = []

    def post(client, url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(
            200,
            json={"access_token": "B", "refresh_token": "rotated", "expires_in": 3600,
                  "token_type": "Bearer"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", post)
    return calls


def test_get_headers_reuses_valid_record_without_endpoint_refresh(endpoint_calls):
    s, _, _ = _managed(MemorySecretStore())
    assert s.get_headers() == {"Authorization": "Bearer A"}
    assert s.get_headers() == {"Authorization": "Bearer A"}
    assert endpoint_calls == []


def test_refresh_persists_token_and_next_header_reacquires(endpoint_calls):
    store = MemorySecretStore()
    s, _, key = _managed(store)
    s.get_headers()
    assert s.refresh() is True
    assert store.get(key)["access_token"] == "B"
    assert s.get_headers() == {"Authorization": "Bearer B"}
    assert len(endpoint_calls) == 1
    store.set(key, _record("C"))
    assert s.get_headers() == {"Authorization": "Bearer C"}
    assert len(endpoint_calls) == 1


class _InterruptedClearStore(MemorySecretStore):
    """Model a committed clear marker with failed record removal."""

    def delete(self, key):
        self._cleared.add(key)
        raise OSError("interrupted record removal")


@pytest.mark.parametrize("clear", ["delete", "revoke", "interrupted"])
def test_next_header_rejects_cleared_token(clear, endpoint_calls):
    store = _InterruptedClearStore() if clear == "interrupted" else MemorySecretStore()
    s, manager, key = _managed(store)
    assert s.get_headers() == {"Authorization": "Bearer A"}

    if clear == "interrupted":
        with pytest.raises(OSError):
            manager.revoke()
        assert store.get(key)["access_token"] == "A"
    elif clear == "revoke":
        manager.revoke()
    else:
        with store.transaction(key):
            store.delete(key)
    assert store.is_cleared(key)

    with pytest.raises(AuthorizationRequired):
        s.get_headers()
    assert endpoint_calls == []


def test_apply_is_noop_but_returns_new_dict():
    s, _, _ = _managed(MemorySecretStore())
    original = {"x": 1}
    result = s.apply(original)
    assert result == {"x": 1}
    assert result is not original      # honours the protocol's "new dict" contract


class _FakeProvider:   # stand-in for OAuth2ProviderProfileProtocol
    NAME = "idp"
    TOKEN_URL = "https://idp.example/token"


def test_no_provider_returns_none():
    assert create_auth_strategy(OAuth2AuthProfile(ACCESS_TOKEN="t")) is None


def test_provider_without_store_raises():
    with pytest.raises(ValueError, match="token_store"):
        create_auth_strategy(OAuth2AuthProfile(), oauth_provider=_FakeProvider())


def test_provider_and_store_builds_strategy(monkeypatch):
    import mountainash_transport.connections.auth_strategy as mod
    store = MemorySecretStore()
    provider = _FakeProvider()
    auth = OAuth2AuthProfile()

    def manager(received_provider, received_auth, *, token_store):
        assert received_provider is provider
        assert received_auth is auth
        assert token_store is store
        return OAuth2TokenManager(received_provider, received_auth, token_store=token_store)

    monkeypatch.setattr(mod, "OAuth2TokenManager", manager)
    s = create_auth_strategy(auth, oauth_provider=provider, token_store=store)
    assert isinstance(s, OAuth2RefreshableAuthStrategy)


def test_non_oauth2_auth_with_provider_raises():
    """A stray oauth_provider paired with a non-OAuth2 auth profile is a
    misconfiguration — surfaced fail-closed, not silently ignored."""
    from mountainash_auth_client import NoAuthProfile
    with pytest.raises(ValueError):
        create_auth_strategy(NoAuthProfile(), oauth_provider=_FakeProvider(),
                             token_store=MemorySecretStore())
