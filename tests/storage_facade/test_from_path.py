"""Tests for StorageFacade.from_path classmethod."""
from __future__ import annotations

import pytest

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.storage_facade import StorageFacade


def test_from_path_returns_storagefacade_for_local():
    facade = StorageFacade.from_path("/tmp/foo.txt")
    assert isinstance(facade, StorageFacade)
    # LOCAL backend is always registered, so this must succeed.


def test_from_path_returns_storagefacade_for_s3(monkeypatch):
    """Verify provider routing without requiring real S3 backend construction."""
    captured: dict[str, object] = {}

    class _Dummy:
        pass

    from mountainash_utils_files.storage_facade import facade as facade_mod

    def _fake_get(provider, auth=None):
        captured["provider"] = provider
        captured["auth"] = auth
        return _Dummy()

    # facade.py binds get_storage_backend at module load; patch it there.
    monkeypatch.setattr(facade_mod, "get_storage_backend", _fake_get)

    StorageFacade.from_path("s3://bucket/key")
    assert captured["provider"] == CONST_STORAGE_PROVIDER_TYPE.S3
    assert captured["auth"] is None


def test_from_path_passes_auth_params(monkeypatch):
    captured: dict[str, object] = {}

    class _Dummy:
        pass

    def _fake_get(provider, auth=None):
        captured["provider"] = provider
        captured["auth"] = auth
        return _Dummy()

    from mountainash_utils_files.storage_facade import facade as facade_mod

    monkeypatch.setattr(facade_mod, "get_storage_backend", _fake_get)

    sentinel = object()
    StorageFacade.from_path("gs://bucket/key", auth_params=sentinel)  # type: ignore[arg-type]
    assert captured["provider"] == CONST_STORAGE_PROVIDER_TYPE.GCS
    assert captured["auth"] is sentinel


def test_from_path_raises_for_unrecognised_scheme():
    with pytest.raises(ValueError, match="Unrecognised scheme"):
        StorageFacade.from_path("gopher://example.com/")


def test_from_path_raises_for_describe_only_scheme():
    with pytest.raises(ValueError, match="has no registered backend"):
        StorageFacade.from_path("hdfs://cluster/file")
