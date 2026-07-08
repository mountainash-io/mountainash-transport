import pytest
from mountainash_auth_client import OAuth2AuthProfile
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.storage.facade import StorageFacade
from mountainash_transport.settings.storage.profiles import HTTPStorageProfile


class _FakeProvider: NAME = "idp"


def _http(): return HTTPStorageProfile()


def test_managed_oauth2_threads_strategy_into_engine(monkeypatch):
    import mountainash_transport.connections.auth_strategy as mod
    monkeypatch.setattr(mod, "OAuth2TokenManager", lambda *a, **k: object())
    f = StorageFacade(
        CONST_STORAGE_PROVIDER_TYPE.HTTP, _http(),
        auth_profile=OAuth2AuthProfile(),                 # no static token
        oauth_provider=_FakeProvider(), secret_resolver=object(),
    )
    engine = f._backend._engine
    assert engine is not None and engine._auth_strategy is not None   # wiring gap regression


def test_managed_oauth2_without_provider_fails_closed():
    with pytest.raises(ValueError):
        StorageFacade(
            CONST_STORAGE_PROVIDER_TYPE.HTTP, _http(),
            auth_profile=OAuth2AuthProfile(),             # no static token, no provider
        )


def test_static_token_oauth2_needs_no_strategy():
    f = StorageFacade(
        CONST_STORAGE_PROVIDER_TYPE.HTTP, _http(),
        auth_profile=OAuth2AuthProfile(ACCESS_TOKEN="tkn"),   # static token, no provider
    )
    assert f._backend._engine._auth_strategy is None      # authenticated via emitted bearer


def test_gate_rejects_oauth2_on_s3_without_building_manager(monkeypatch):
    """Ordering: the supported_auth gate rejects OAuth2 on S3 BEFORE the strategy factory
    constructs any OAuth2TokenManager (no token I/O for an unsupported backend)."""
    import mountainash_transport.connections.auth_strategy as mod
    built = {"n": 0}
    monkeypatch.setattr(mod, "OAuth2TokenManager",
                        lambda *a, **k: built.__setitem__("n", built["n"] + 1))
    from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile
    from mountainash_transport.connections.errors import UnsupportedAuthProfileError
    with pytest.raises(UnsupportedAuthProfileError):
        StorageFacade(
            CONST_STORAGE_PROVIDER_TYPE.S3,
            S3StorageProfile(BUCKET="b", FLAVOR="aws"),
            auth_profile=OAuth2AuthProfile(),
            oauth_provider=_FakeProvider(), secret_resolver=object(),
        )
    assert built["n"] == 0            # manager never constructed


def test_managed_oauth2_no_stored_token_propagates(monkeypatch):
    """A managed strategy whose acquire() raises AuthorizationRequired surfaces it on the
    first storage op (non-interactive; no browser)."""
    import mountainash_transport.connections.auth_strategy as mod
    from mountainash_auth_client.errors import AuthorizationRequired

    class _NoTokenMgr:
        def acquire(self): raise AuthorizationRequired(provider="idp", user="default")
        def refresh(self): raise AssertionError("should not refresh")

    monkeypatch.setattr(mod, "OAuth2TokenManager", lambda *a, **k: _NoTokenMgr())
    f = StorageFacade(
        CONST_STORAGE_PROVIDER_TYPE.HTTP, _http(),
        auth_profile=OAuth2AuthProfile(),
        oauth_provider=_FakeProvider(), secret_resolver=object(),
    )
    with pytest.raises(AuthorizationRequired):
        f._backend._engine._auth_strategy.get_headers()   # first use triggers acquire()
