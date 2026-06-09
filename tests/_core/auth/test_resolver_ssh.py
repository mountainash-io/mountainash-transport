"""Tests for resolve_auth_strategy() SSH-family dispatch."""
from __future__ import annotations

import pytest

from mountainash_transport._core.auth.resolver import resolve_auth_strategy
from mountainash_transport._core.auth.strategies import (
    BasicAuthStrategy,
    BearerTokenStrategy,
    NoAuthStrategy,
    SSHKeyStrategy,
    SSHKerberosStrategy,
    SSHPasswordStrategy,
)
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE


class TestResolverSSHFamily:
    def test_password_auth_ssh_provider_returns_ssh_password_strategy(self):
        from mountainash_auth_client import PasswordAuth

        auth = PasswordAuth(USERNAME="user", PASSWORD="secret")
        strategy = resolve_auth_strategy(auth, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH)
        assert isinstance(strategy, SSHPasswordStrategy)
        result = strategy.apply({})
        assert result["password"] == "secret"

    def test_password_auth_no_provider_returns_basic_auth_strategy(self):
        from mountainash_auth_client import PasswordAuth

        auth = PasswordAuth(USERNAME="admin", PASSWORD="pass")
        strategy = resolve_auth_strategy(auth)
        assert isinstance(strategy, BasicAuthStrategy)

    def test_password_auth_http_provider_returns_basic_auth_strategy(self):
        from mountainash_auth_client import PasswordAuth

        auth = PasswordAuth(USERNAME="admin", PASSWORD="pass")
        strategy = resolve_auth_strategy(auth, provider_type=CONST_STORAGE_PROVIDER_TYPE.HTTP)
        assert isinstance(strategy, BasicAuthStrategy)

    def test_certificate_auth_key_path_ssh_returns_ssh_key_strategy(self):
        from pathlib import Path

        from mountainash_auth_client import CertificateAuth

        auth = CertificateAuth(PRIVATE_KEY_PATH=Path("/home/user/.ssh/id_rsa"))
        strategy = resolve_auth_strategy(auth, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH)
        assert isinstance(strategy, SSHKeyStrategy)
        result = strategy.apply({})
        assert result["key_filename"] == "/home/user/.ssh/id_rsa"

    def test_certificate_auth_raw_key_ssh_returns_ssh_key_strategy(self):
        from mountainash_auth_client import CertificateAuth

        raw_key = "-----BEGIN RSA PRIVATE KEY-----\nfakekey\n-----END RSA PRIVATE KEY-----"
        auth = CertificateAuth(PRIVATE_KEY=raw_key)
        strategy = resolve_auth_strategy(auth, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH)
        assert isinstance(strategy, SSHKeyStrategy)
        # key_string should be set (pkey parsing happens lazily in apply)
        assert strategy._key_string == raw_key

    def test_certificate_auth_with_passphrase_ssh_returns_ssh_key_strategy(self):
        from pathlib import Path

        from mountainash_auth_client import CertificateAuth

        auth = CertificateAuth(PRIVATE_KEY_PATH=Path("/home/user/.ssh/id_rsa"), PASSPHRASE="mypass")
        strategy = resolve_auth_strategy(auth, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH)
        assert isinstance(strategy, SSHKeyStrategy)
        result = strategy.apply({})
        assert result.get("passphrase") == "mypass"

    def test_kerberos_auth_ssh_returns_ssh_kerberos_strategy(self):
        from mountainash_auth_client import KerberosAuth

        auth = KerberosAuth(SERVICE_NAME="host/myserver.example.com")
        strategy = resolve_auth_strategy(auth, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH)
        assert isinstance(strategy, SSHKerberosStrategy)
        result = strategy.apply({})
        assert result["gss_auth"] is True

    def test_none_ssh_provider_returns_no_auth_strategy(self):
        strategy = resolve_auth_strategy(None, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH)
        assert isinstance(strategy, NoAuthStrategy)

    def test_no_auth_ssh_provider_returns_no_auth_strategy(self):
        from mountainash_auth_client import NoAuth

        strategy = resolve_auth_strategy(NoAuth(), provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH)
        assert isinstance(strategy, NoAuthStrategy)

    def test_token_auth_no_provider_returns_bearer_strategy(self):
        from mountainash_auth_client import TokenAuth

        auth = TokenAuth(TOKEN="mytoken")
        strategy = resolve_auth_strategy(auth)
        assert isinstance(strategy, BearerTokenStrategy)
        result = strategy.apply({})
        assert result["headers"]["Authorization"] == "Bearer mytoken"
