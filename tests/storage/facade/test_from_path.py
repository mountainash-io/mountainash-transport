"""Tests for StorageFacade.from_path classmethod."""
from __future__ import annotations

import pytest

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.storage.facade import StorageFacade


def test_from_path_returns_storagefacade_for_local():
    facade = StorageFacade.from_path("/tmp/foo.txt")
    assert isinstance(facade, StorageFacade)
    # LOCAL backend is always registered, so this must succeed.


def test_from_path_returns_storagefacade_for_s3(monkeypatch):
    """Verify provider routing without requiring real S3 backend construction."""
    captured: dict[str, object] = {}

    class _Dummy:
        pass

    from mountainash_transport.storage.facade import facade as facade_mod

    def _fake_get(provider, storage_profile=None, *, auth_profile=None, connection=None):
        captured["provider"] = provider
        captured["storage_profile"] = storage_profile
        captured["auth_profile"] = auth_profile
        return _Dummy()

    # facade.py binds get_storage_backend at module load; patch it there.
    monkeypatch.setattr(facade_mod, "get_storage_backend", _fake_get)

    StorageFacade.from_path("s3://bucket/key")
    assert captured["provider"] == CONST_STORAGE_PROVIDER_TYPE.S3
    assert captured["storage_profile"] is None
    assert captured["auth_profile"] is None


def test_from_path_passes_profile(monkeypatch):
    captured: dict[str, object] = {}

    class _Dummy:
        pass

    class _FakeConn:
        def connect(self):
            return self

    def _fake_get(provider, storage_profile=None, *, auth_profile=None, connection=None):
        captured["provider"] = provider
        captured["storage_profile"] = storage_profile
        return _Dummy()

    def _fake_create_conn(profile, auth_profile=None, **kw):
        return _FakeConn()

    from mountainash_transport.storage.facade import facade as facade_mod
    from mountainash_transport import connections as conn_mod

    monkeypatch.setattr(facade_mod, "get_storage_backend", _fake_get)
    monkeypatch.setattr(conn_mod, "create_connection", _fake_create_conn)

    sentinel = object()
    StorageFacade.from_path("gs://bucket/key", storage_profile=sentinel)  # type: ignore[arg-type]
    assert captured["provider"] == CONST_STORAGE_PROVIDER_TYPE.GCS
    assert captured["storage_profile"] is sentinel


def test_from_path_raises_for_unrecognised_scheme():
    with pytest.raises(ValueError, match="Unrecognised scheme"):
        StorageFacade.from_path("gopher://example.com/")


def test_from_path_raises_for_unknown_scheme():
    with pytest.raises(ValueError):
        StorageFacade.from_path("foobar://cluster/file")
