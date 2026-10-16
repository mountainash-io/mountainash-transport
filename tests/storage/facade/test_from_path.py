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
    StorageFacade.from_path("gs://bucket/key", storage_profile=sentinel)
    assert captured["provider"] == CONST_STORAGE_PROVIDER_TYPE.GCS
    assert captured["storage_profile"] is sentinel


def test_from_path_raises_for_unrecognised_scheme():
    with pytest.raises(ValueError, match="Unrecognised scheme"):
        StorageFacade.from_path("gopher://example.com/")


def test_from_path_raises_for_unknown_scheme():
    with pytest.raises(ValueError):
        StorageFacade.from_path("foobar://cluster/file")


def test_sftp_facade_context_closes_channel_and_ssh(monkeypatch) -> None:
    from unittest.mock import MagicMock
    import paramiko
    from mountainash_transport.settings.storage.profiles.sftp_storage_profile import SFTPStorageProfile

    native_ssh = MagicMock()
    channel = native_ssh.open_sftp.return_value
    monkeypatch.setattr(paramiko, "SSHClient", lambda: native_ssh)
    profile = SFTPStorageProfile(HOST="host", USERNAME="user")
    with StorageFacade.from_path("sftp://host/file", profile) as facade:
        assert facade._connection is not None and facade._connection.is_connected
    channel.close.assert_called_once()
    native_ssh.close.assert_called_once()
    facade.close()
    native_ssh.close.assert_called_once()


def test_backend_construction_error_retains_both_sftp_cleanup_failures(monkeypatch) -> None:
    from unittest.mock import MagicMock
    import paramiko
    from mountainash_transport.settings.storage.profiles.sftp_storage_profile import SFTPStorageProfile
    from mountainash_transport.storage.facade import facade as facade_module

    native_ssh = MagicMock()
    channel = native_ssh.open_sftp.return_value
    channel.close.side_effect = OSError("channel cleanup fault")
    native_ssh.close.side_effect = OSError("SSH cleanup fault")
    monkeypatch.setattr(paramiko, "SSHClient", lambda: native_ssh)
    primary = ValueError("backend construction fault")

    def fail_backend(*args, **kwargs):
        raise primary

    monkeypatch.setattr(facade_module, "get_storage_backend", fail_backend)
    profile = SFTPStorageProfile(HOST="host", USERNAME="user")
    with pytest.raises(ValueError) as caught:
        StorageFacade.from_path("sftp://host/file", profile)
    assert caught.value is primary
    assert "channel cleanup fault" in str(primary.__notes__)
    assert "SSH cleanup fault" in str(primary.__notes__)
    channel.close.assert_called_once()
    native_ssh.close.assert_called_once()
