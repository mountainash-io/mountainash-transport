"""Tests for SMBSettings — SMB / CIFS settings."""

from __future__ import annotations

import pytest

from mountainash_auth_client import KerberosAuth, PasswordAuth
from pydantic import SecretStr

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.settings.providers.smb_settings import (
    SMB_SPEC,
    SMBSettings,
)


def _make(*, auth, server: str = "file.example", **extra):
    kwargs = {
        "PROVIDER_TYPE": CONST_STORAGE_PROVIDER_TYPE.SMB,
        "SERVER": server,
        "auth": auth,
    }
    kwargs.update(extra)
    return SMBSettings(**kwargs)


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
        assert field not in SMBSettings.model_fields


@pytest.mark.unit
class TestSMBPasswordAuthDomainEncoding:
    def test_domain_encoded_on_username(self):
        s = _make(
            auth=PasswordAuth(username="alice", password=SecretStr("pw")),
            USERNAME="alice",
            DOMAIN="CORP",
        )
        kw = s.to_handler_kwargs()
        assert kw["username"] == "CORP\\alice"
        assert kw["auth_protocol"] == "negotiate"
        assert kw["password"] == "pw"

    def test_no_domain_plain_username(self):
        s = _make(
            auth=PasswordAuth(username="alice", password=SecretStr("pw")),
            USERNAME="alice",
        )
        kw = s.to_handler_kwargs()
        assert kw["username"] == "alice"
        assert kw["auth_protocol"] == "negotiate"


@pytest.mark.unit
class TestSMBKerberosAuth:
    def test_kerberos_sets_protocol(self):
        s = _make(
            auth=KerberosAuth(principal="alice@CORP"),
            USERNAME="alice",
            DOMAIN="CORP",
        )
        kw = s.to_handler_kwargs()
        assert kw["auth_protocol"] == "kerberos"

    def test_kerberos_principal_becomes_username(self):
        s = _make(
            auth=KerberosAuth(principal="alice"),
            DOMAIN="CORP",
        )
        kw = s.to_handler_kwargs()
        assert kw["username"] == "CORP\\alice"


@pytest.mark.unit
class TestSMBConnectionKwargs:
    def test_server_and_port_defaults(self):
        s = _make(
            auth=PasswordAuth(username="u", password=SecretStr("p")),
            USERNAME="u",
        )
        kw = s.to_handler_kwargs()
        assert kw["server"] == "file.example"
        assert kw["port"] == 445

    def test_encrypt_default_false(self):
        s = _make(
            auth=PasswordAuth(username="u", password=SecretStr("p")),
            USERNAME="u",
        )
        kw = s.to_handler_kwargs()
        assert kw["encrypt"] is False

    def test_encrypt_true_opt_in(self):
        s = _make(
            auth=PasswordAuth(username="u", password=SecretStr("p")),
            USERNAME="u",
            ENCRYPT=True,
        )
        kw = s.to_handler_kwargs()
        assert kw["encrypt"] is True

    def test_connection_timeout_default_and_override(self):
        s = _make(
            auth=PasswordAuth(username="u", password=SecretStr("p")),
            USERNAME="u",
        )
        kw = s.to_handler_kwargs()
        assert kw["connection_timeout"] == 60

        s2 = _make(
            auth=PasswordAuth(username="u", password=SecretStr("p")),
            USERNAME="u",
            CONNECTION_TIMEOUT=15,
        )
        kw2 = s2.to_handler_kwargs()
        assert kw2["connection_timeout"] == 15


@pytest.mark.unit
class TestSMBDescriptor:
    def test_descriptor_name(self):
        assert SMB_SPEC.name == "smb"

    def test_descriptor_sdk_package(self):
        assert SMB_SPEC.sdk_package == "smbprotocol"

    def test_descriptor_not_read_only(self):
        assert SMB_SPEC.read_only is False
