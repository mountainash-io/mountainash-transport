"""Tests for SMBStorageProfile — SMB / CIFS settings."""

from __future__ import annotations

import pytest

from mountainash_auth_client import KerberosAuth, PasswordAuth
from pydantic import SecretStr

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.settings.profiles import (
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
class TestSMBPasswordAuthDomainEncoding:
    def test_domain_encoded_on_username(self):
        auth = PasswordAuth(USERNAME="alice", PASSWORD=SecretStr("pw"))
        s = _make(USERNAME="alice", DOMAIN="CORP")
        kw = s.to_handler_kwargs(auth_profile=auth)
        assert kw["username"] == "CORP\\alice"
        assert kw["auth_protocol"] == "negotiate"
        assert kw["password"] == "pw"

    def test_no_domain_plain_username(self):
        auth = PasswordAuth(USERNAME="alice", PASSWORD=SecretStr("pw"))
        s = _make(USERNAME="alice")
        kw = s.to_handler_kwargs(auth_profile=auth)
        assert kw["username"] == "alice"
        assert kw["auth_protocol"] == "negotiate"


@pytest.mark.unit
class TestSMBKerberosAuth:
    def test_kerberos_sets_protocol(self):
        auth = KerberosAuth(PRINCIPAL="alice@CORP")
        s = _make(USERNAME="alice", DOMAIN="CORP")
        kw = s.to_handler_kwargs(auth_profile=auth)
        assert kw["auth_protocol"] == "kerberos"

    def test_kerberos_principal_becomes_username(self):
        auth = KerberosAuth(PRINCIPAL="alice")
        s = _make(DOMAIN="CORP")
        kw = s.to_handler_kwargs(auth_profile=auth)
        assert kw["username"] == "CORP\\alice"


@pytest.mark.unit
class TestSMBConnectionKwargs:
    def test_server_and_port_defaults(self):
        auth = PasswordAuth(USERNAME="u", PASSWORD=SecretStr("p"))
        s = _make(USERNAME="u")
        kw = s.to_handler_kwargs(auth_profile=auth)
        assert kw["server"] == "file.example"
        assert kw["port"] == 445

    def test_encrypt_default_false(self):
        auth = PasswordAuth(USERNAME="u", PASSWORD=SecretStr("p"))
        s = _make(USERNAME="u")
        kw = s.to_handler_kwargs(auth_profile=auth)
        assert kw["encrypt"] is False

    def test_encrypt_true_opt_in(self):
        auth = PasswordAuth(USERNAME="u", PASSWORD=SecretStr("p"))
        s = _make(USERNAME="u", ENCRYPT=True)
        kw = s.to_handler_kwargs(auth_profile=auth)
        assert kw["encrypt"] is True

    def test_connection_timeout_default_and_override(self):
        auth = PasswordAuth(USERNAME="u", PASSWORD=SecretStr("p"))
        s = _make(USERNAME="u")
        kw = s.to_handler_kwargs(auth_profile=auth)
        assert kw["connection_timeout"] == 60

        s2 = _make(USERNAME="u", CONNECTION_TIMEOUT=15)
        kw2 = s2.to_handler_kwargs(auth_profile=auth)
        assert kw2["connection_timeout"] == 15


@pytest.mark.unit
class TestSMBDescriptor:
    def test_descriptor_name(self):
        assert SMB_SPEC.name == "smb"

    def test_descriptor_sdk_package(self):
        assert SMB_SPEC.sdk_package == "smbprotocol"

    def test_descriptor_not_read_only(self):
        assert SMB_SPEC.read_only is False
