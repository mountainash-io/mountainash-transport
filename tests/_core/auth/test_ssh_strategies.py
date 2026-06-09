"""SSH auth strategy tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mountainash_transport._core.auth.strategies import (
    AuthStrategy,
    SSHPasswordStrategy,
    SSHKeyStrategy,
    SSHKerberosStrategy,
    _parse_private_key,
)


class TestSSHPasswordStrategy:
    def test_conforms_to_protocol(self):
        assert isinstance(SSHPasswordStrategy("secret"), AuthStrategy)

    def test_injects_password(self):
        result = SSHPasswordStrategy("secret").apply({"timeout": 30})
        assert result["password"] == "secret"
        assert result["timeout"] == 30

    def test_returns_new_dict(self):
        original = {"timeout": 30}
        result = SSHPasswordStrategy("secret").apply(original)
        assert result is not original
        assert "password" not in original

    def test_empty_password(self):
        result = SSHPasswordStrategy("").apply({})
        assert result["password"] == ""


class TestSSHKeyStrategyFilePath:
    def test_conforms_to_protocol(self):
        assert isinstance(SSHKeyStrategy(key_path="/home/user/.ssh/id_rsa"), AuthStrategy)

    def test_injects_key_filename(self):
        result = SSHKeyStrategy(key_path="/home/user/.ssh/id_rsa").apply({})
        assert result["key_filename"] == "/home/user/.ssh/id_rsa"
        assert "pkey" not in result

    def test_key_filename_with_passphrase(self):
        result = SSHKeyStrategy(key_path="/home/user/.ssh/id_rsa", passphrase="mypass").apply({})
        assert result["key_filename"] == "/home/user/.ssh/id_rsa"
        assert result["passphrase"] == "mypass"

    def test_returns_new_dict(self):
        original = {"timeout": 30}
        result = SSHKeyStrategy(key_path="/home/user/.ssh/id_rsa").apply(original)
        assert result is not original
        assert "key_filename" not in original


class TestSSHKeyStrategyRawKey:
    def test_injects_pkey_from_raw_string(self):
        fake_pkey = MagicMock()
        raw_key = "-----BEGIN RSA PRIVATE KEY-----\nfakekey\n-----END RSA PRIVATE KEY-----"
        with patch(
            "mountainash_transport._core.auth.strategies._parse_private_key",
            return_value=fake_pkey,
        ) as mock_parse:
            result = SSHKeyStrategy(key_string=raw_key).apply({})
            mock_parse.assert_called_once_with(raw_key, None)
            assert result["pkey"] is fake_pkey
            assert "key_filename" not in result

    def test_raw_key_with_passphrase(self):
        fake_pkey = MagicMock()
        raw_key = "-----BEGIN OPENSSH PRIVATE KEY-----\nfakekey\n-----END OPENSSH PRIVATE KEY-----"
        with patch(
            "mountainash_transport._core.auth.strategies._parse_private_key",
            return_value=fake_pkey,
        ) as mock_parse:
            result = SSHKeyStrategy(key_string=raw_key, passphrase="mypass").apply({})
            mock_parse.assert_called_once_with(raw_key, "mypass")
            assert result["pkey"] is fake_pkey


class TestParsePrivateKey:
    def _make_mock_key_class(self, success: bool, pkey_obj=None):
        """Return a mock paramiko key class that either succeeds or raises SSHException."""
        mock_class = MagicMock()
        if success:
            mock_instance = pkey_obj or MagicMock()
            mock_class.from_private_key.return_value = mock_instance
        else:
            import paramiko
            mock_class.from_private_key.side_effect = paramiko.SSHException("bad key")
        return mock_class

    def test_tries_key_classes_in_order(self):
        import paramiko

        fake_pkey = MagicMock()
        mock_rsa = MagicMock()
        mock_rsa.from_private_key.side_effect = paramiko.SSHException("not rsa")
        mock_ed25519 = MagicMock()
        mock_ed25519.from_private_key.return_value = fake_pkey

        with patch("mountainash_transport._core.auth.strategies.importlib") as mock_importlib:
            mock_paramiko = MagicMock()
            mock_paramiko.SSHException = paramiko.SSHException  # use real exception class
            mock_paramiko.RSAKey = mock_rsa
            mock_paramiko.Ed25519Key = mock_ed25519
            mock_paramiko.ECDSAKey = MagicMock()
            mock_paramiko.DSSKey = MagicMock()
            mock_importlib.import_module.return_value = mock_paramiko

            result = _parse_private_key("-----BEGIN key-----", None)

        assert result is fake_pkey
        mock_rsa.from_private_key.assert_called_once()
        mock_ed25519.from_private_key.assert_called_once()

    def test_passphrase_passed_to_parser(self):
        import paramiko

        fake_pkey = MagicMock()
        mock_rsa = MagicMock()
        mock_rsa.from_private_key.return_value = fake_pkey

        with patch("mountainash_transport._core.auth.strategies.importlib") as mock_importlib:
            mock_paramiko = MagicMock()
            mock_paramiko.SSHException = paramiko.SSHException  # use real exception class
            mock_paramiko.RSAKey = mock_rsa
            mock_importlib.import_module.return_value = mock_paramiko

            result = _parse_private_key("-----BEGIN key-----", "secret")

        # Verify passphrase= was passed as keyword arg
        call_kwargs = mock_rsa.from_private_key.call_args
        assert call_kwargs.kwargs.get("password") == "secret" or (
            len(call_kwargs.args) >= 2 and call_kwargs.args[1] == "secret"
        )

    def test_all_types_fail_raises_value_error(self):
        import paramiko

        mock_key_cls = MagicMock()
        mock_key_cls.from_private_key.side_effect = paramiko.SSHException("bad")

        with patch("mountainash_transport._core.auth.strategies.importlib") as mock_importlib:
            mock_paramiko = MagicMock()
            mock_paramiko.SSHException = paramiko.SSHException  # use real exception class
            mock_paramiko.RSAKey = mock_key_cls
            mock_paramiko.Ed25519Key = mock_key_cls
            mock_paramiko.ECDSAKey = mock_key_cls
            mock_paramiko.DSSKey = mock_key_cls
            mock_importlib.import_module.return_value = mock_paramiko

            with pytest.raises(ValueError, match="Could not parse private key"):
                _parse_private_key("-----BEGIN GARBAGE-----", None)


class TestSSHKerberosStrategy:
    def test_conforms_to_protocol(self):
        assert isinstance(SSHKerberosStrategy(), AuthStrategy)

    def test_injects_gss_auth(self):
        result = SSHKerberosStrategy().apply({})
        assert result["gss_auth"] is True

    def test_gss_kex_defaults_false(self):
        result = SSHKerberosStrategy().apply({})
        assert "gss_kex" not in result

    def test_gss_kex_opt_in(self):
        result = SSHKerberosStrategy(gss_kex=True).apply({})
        assert result["gss_kex"] is True

    def test_gss_host(self):
        result = SSHKerberosStrategy(gss_host="myhost.example.com").apply({})
        assert result["gss_host"] == "myhost.example.com"

    def test_returns_new_dict(self):
        original = {"timeout": 30}
        result = SSHKerberosStrategy().apply(original)
        assert result is not original
        assert "gss_auth" not in original
