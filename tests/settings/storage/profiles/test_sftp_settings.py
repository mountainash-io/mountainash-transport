"""Tests for SFTPStorageProfile — SFTP storage settings."""

from __future__ import annotations

import pytest

from mountainash_auth_client import NoAuth

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.settings.storage.profiles import (
    SFTP_SPEC,
    SFTPStorageProfile,
)


def _make(*, host: str = "server.example", username: str = "alice", **extra):
    kwargs = {
        "PROVIDER_TYPE": CONST_STORAGE_PROVIDER_TYPE.SFTP,
        "HOST": host,
        "USERNAME": username,
    }
    kwargs.update(extra)
    return SFTPStorageProfile(**kwargs)


@pytest.mark.unit
class TestSFTPConstruction:
    def test_instantiates_with_password_auth(self):
        s = _make()
        assert s.HOST == "server.example"
        assert s.USERNAME == "alice"

    def test_username_required(self):
        with pytest.raises(Exception):
            SFTPStorageProfile(
                PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.SFTP,
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
class TestSFTPFakeFieldsAbsent:
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
        assert field not in SFTPStorageProfile.model_fields

    def test_extras_silently_ignored(self):
        """Profile inherits extra='ignore' -- unknown kwargs drop."""
        s = _make(
            COMPRESSION_LEVEL=9,  # silently ignored
            CIPHERS=["aes256"],  # silently ignored
        )
        assert not hasattr(s, "COMPRESSION_LEVEL")
        assert not hasattr(s, "CIPHERS")


@pytest.mark.unit
class TestSFTPHandlerKwargs:
    """to_handler_kwargs returns SDK-level config only (no auth)."""

    def test_canonical_keys_present(self):
        s = _make()
        kw = s.to_handler_kwargs()
        assert kw["hostname"] == "server.example"
        assert kw["port"] == 22
        assert kw["username"] == "alice"
        assert kw["timeout"] == 30.0
        assert kw["allow_agent"] is True
        assert kw["look_for_keys"] is True
        assert kw["compress"] is False

    def test_no_auth_keys_in_kwargs(self):
        """Auth credentials are injected by the strategy layer, not the profile."""
        s = _make()
        kw = s.to_handler_kwargs()
        assert "password" not in kw
        assert "key_filename" not in kw
        assert "pkey" not in kw
        assert "gss_auth" not in kw


@pytest.mark.unit
class TestSFTPPostConnectEnvelope:
    def test_host_key_policy_surfaced_in_post_connect(self):
        s = _make(HOST_KEY_POLICY="auto_add")
        kw = s.to_handler_kwargs()
        assert kw["_post_connect"]["host_key_policy"] == "auto_add"

    def test_known_hosts_surfaced_in_post_connect(self):
        s = _make(KNOWN_HOSTS_FILE="/etc/ssh/known_hosts")
        kw = s.to_handler_kwargs()
        assert kw["_post_connect"]["known_hosts_file"] == "/etc/ssh/known_hosts"


@pytest.mark.unit
class TestSFTPDescriptor:
    def test_descriptor_name(self):
        assert SFTP_SPEC.name == "sftp"

    def test_descriptor_sdk_package(self):
        assert SFTP_SPEC.sdk_package == "paramiko"

    def test_descriptor_not_read_only(self):
        assert SFTP_SPEC.read_only is False

    def test_descriptor_does_not_support_multipart(self):
        assert SFTP_SPEC.supports_multipart is False
