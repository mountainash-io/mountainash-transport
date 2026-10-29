"""Tests for SMBStorageProfile — SMB / CIFS settings."""

from __future__ import annotations

import pytest

from mountainash_auth_client import NoAuthProfile

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.settings.storage.profiles import (
    SMB_SPEC,
    SMBStorageProfile,
)


def _make(*, server: str = "file.example", **extra):
    kwargs = {
        "PROVIDER_TYPE": CONST_STORAGE_PROVIDER_TYPE.SMB,
        "SERVER": server,
    }
    kwargs.update(extra)
    return SMBStorageProfile(**kwargs)


@pytest.mark.unit
class TestSMBFakeFieldsAbsent:
    """Regression: all the fake version/dialect fields are gone (T6)."""

    @pytest.mark.parametrize(
        "field",
        [
            "VERSION",
            "MIN_VERSION",
            "MAX_VERSION",
            "PREFERRED_DIALECT",
            "FALLBACK_VERSIONS",
            "SHARE",
            "USE_KERBEROS",
            "KERBEROS_KDC",
            "KERBEROS_REALM",
            "KERBEROS_KEYTAB",
        ],
    )
    def test_fake_field_absent(self, field):
        assert field not in SMBStorageProfile.model_fields


@pytest.mark.unit
class TestSMBConnectionKwargs:
    """to_handler_kwargs returns SDK-level config only (no auth)."""

    def test_server_and_port_defaults(self):
        s = _make(USERNAME="u")
        kw = s.to_handler_kwargs()
        assert kw["server"] == "file.example"
        assert kw["port"] == 445

    def test_encrypt_default_false(self):
        s = _make(USERNAME="u")
        kw = s.to_handler_kwargs()
        assert kw["encrypt"] is False

    def test_encrypt_true_opt_in(self):
        s = _make(USERNAME="u", ENCRYPT=True)
        kw = s.to_handler_kwargs()
        assert kw["encrypt"] is True

    def test_connection_timeout_default_and_override(self):
        s = _make(USERNAME="u")
        kw = s.to_handler_kwargs()
        assert kw["connection_timeout"] == 60

        s2 = _make(USERNAME="u", CONNECTION_TIMEOUT=15)
        kw2 = s2.to_handler_kwargs()
        assert kw2["connection_timeout"] == 15

    def test_profile_username_with_domain_encoded(self):
        s = _make(USERNAME="alice", DOMAIN="CORP")
        kw = s.to_handler_kwargs()
        assert kw["username"] == "CORP\\alice"

    def test_profile_username_no_domain(self):
        s = _make(USERNAME="alice")
        kw = s.to_handler_kwargs()
        assert kw["username"] == "alice"

    def test_no_auth_keys_in_kwargs(self):
        """Auth credentials are injected by the strategy layer, not the profile."""
        s = _make(USERNAME="u")
        kw = s.to_handler_kwargs()
        assert "password" not in kw
        assert "auth_protocol" not in kw


@pytest.mark.unit
class TestSMBDescriptor:
    def test_descriptor_name(self):
        assert SMB_SPEC.name == "smb"

    def test_descriptor_sdk_package(self):
        assert SMB_SPEC.sdk_package == "smbprotocol"

    def test_descriptor_not_read_only(self):
        assert SMB_SPEC.read_only is False
