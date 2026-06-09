"""Tests for SSHStorageProfile — unified SSH + SFTP settings."""

from __future__ import annotations

import pytest

from mountainash_auth_client import CertificateAuth, KerberosAuth, NoAuth, PasswordAuth
from pydantic import SecretStr

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.settings.storage.profiles import (
    SSH_SPEC,
    SSHStorageProfile,
)


def _make(*, host: str = "server.example", username: str = "alice", **extra):
    kwargs = {
        "PROVIDER_TYPE": CONST_STORAGE_PROVIDER_TYPE.SSH,
        "HOST": host,
        "USERNAME": username,
    }
    kwargs.update(extra)
    return SSHStorageProfile(**kwargs)


@pytest.mark.unit
class TestSSHConstruction:
    def test_instantiates_with_password_auth(self):
        s = _make()
        assert s.HOST == "server.example"
        assert s.USERNAME == "alice"

    def test_username_required(self):
        with pytest.raises(Exception):
            SSHStorageProfile(
                PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.SSH,
                HOST="h",
                USERNAME="",
            )

    def test_default_port_is_22(self):
        s = _make()
        assert s.PORT == 22

    def test_default_host_key_policy_is_reject(self):
        s = _make()
        assert s.HOST_KEY_POLICY == "reject"

    @pytest.mark.parametrize(
        "policy", ["reject", "warn", "auto_add", "ignore"]
    )
    def test_valid_host_key_policies_accepted(self, policy):
        s = _make(HOST_KEY_POLICY=policy)
        assert s.HOST_KEY_POLICY == policy

    def test_invalid_host_key_policy_rejected(self):
        with pytest.raises(Exception):
            _make(HOST_KEY_POLICY="bogus")


@pytest.mark.unit
class TestSSHFakeFieldsAbsent:
    """Regression: fake SSH fields removed by T5."""

    @pytest.mark.parametrize(
        "field",
        [
            "COMPRESSION_LEVEL",
            "PREFERRED_AUTH_METHODS",
            "CIPHERS",
            "MAC_ALGORITHMS",
            "KEY_EXCHANGE_ALGORITHMS",
        ],
    )
    def test_fake_ssh_field_absent(self, field):
        assert field not in SSHStorageProfile.model_fields

    def test_extras_silently_ignored(self):
        """Profile inherits extra='ignore' -- unknown kwargs drop."""
        s = _make(
            COMPRESSION_LEVEL=9,  # silently ignored
            CIPHERS=["aes256"],  # silently ignored
        )
        assert not hasattr(s, "COMPRESSION_LEVEL")
        assert not hasattr(s, "CIPHERS")


@pytest.mark.unit
class TestSSHPasswordAuth:
    def test_password_becomes_plain_string_in_kwargs(self):
        auth = PasswordAuth(USERNAME="alice", PASSWORD=SecretStr("pw"))
        s = _make()
        kw = s.to_handler_kwargs(auth_profile=auth)
        # Unwrapped -- paramiko.SSHClient.connect takes a plain string.
        assert kw["password"] == "pw"

    def test_password_kwargs_includes_canonical_keys(self):
        auth = PasswordAuth(USERNAME="alice", PASSWORD=SecretStr("pw"))
        s = _make()
        kw = s.to_handler_kwargs(auth_profile=auth)
        assert kw["hostname"] == "server.example"
        assert kw["port"] == 22
        assert kw["username"] == "alice"
        assert kw["timeout"] == 30.0
        assert kw["allow_agent"] is True
        assert kw["look_for_keys"] is True
        assert kw["compress"] is False


@pytest.mark.unit
class TestSSHCertificateAuth:
    def test_key_filename_surfaced_from_private_key_path(self):
        auth = CertificateAuth(
            PRIVATE_KEY_PATH="/home/alice/.ssh/id_ed25519",
        )
        s = _make()
        kw = s.to_handler_kwargs(auth_profile=auth)
        assert kw["key_filename"] == "/home/alice/.ssh/id_ed25519"
        assert "pkey" not in kw

    def test_pkey_surfaced_from_inline_private_key(self):
        auth = CertificateAuth(
            PRIVATE_KEY=SecretStr("-----BEGIN OPENSSH PRIVATE KEY-----\n..."),
        )
        s = _make()
        kw = s.to_handler_kwargs(auth_profile=auth)
        assert "pkey" in kw
        assert kw["pkey"].startswith("-----BEGIN OPENSSH")
        assert "key_filename" not in kw

    def test_passphrase_forwarded_when_present(self):
        auth = CertificateAuth(
            PRIVATE_KEY_PATH="/k/id_rsa",
            PASSPHRASE=SecretStr("kpw"),
        )
        s = _make()
        kw = s.to_handler_kwargs(auth_profile=auth)
        assert kw["passphrase"] == "kpw"


@pytest.mark.unit
class TestSSHKerberosAuth:
    def test_kerberos_sets_gss_flags(self):
        auth = KerberosAuth(PRINCIPAL="alice@EXAMPLE.COM")
        s = _make()
        kw = s.to_handler_kwargs(auth_profile=auth)
        assert kw["gss_auth"] is True
        assert kw["gss_kex"] is True
        assert kw["gss_host"] == "server.example"


@pytest.mark.unit
class TestSSHPostConnectEnvelope:
    def test_host_key_policy_surfaced_in_post_connect(self):
        s = _make(HOST_KEY_POLICY="auto_add")
        kw = s.to_handler_kwargs()
        assert kw["_post_connect"]["host_key_policy"] == "auto_add"

    def test_known_hosts_surfaced_in_post_connect(self):
        s = _make(KNOWN_HOSTS_FILE="/etc/ssh/known_hosts")
        kw = s.to_handler_kwargs()
        assert kw["_post_connect"]["known_hosts_file"] == "/etc/ssh/known_hosts"


@pytest.mark.unit
class TestSSHDescriptor:
    def test_descriptor_name(self):
        assert SSH_SPEC.name == "ssh"

    def test_descriptor_sdk_package(self):
        assert SSH_SPEC.sdk_package == "paramiko"

    def test_descriptor_not_read_only(self):
        assert SSH_SPEC.read_only is False

    def test_descriptor_does_not_support_multipart(self):
        assert SSH_SPEC.supports_multipart is False
