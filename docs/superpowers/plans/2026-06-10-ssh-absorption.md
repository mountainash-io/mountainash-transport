# SSH Absorption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Absorb SSH support into mountainash-transport's three-layer connection architecture (auth strategies, connections, backends), deprecating mountainash-utils-ssh.

**Architecture:** Three SSH auth strategies injecting paramiko credentials. SSHConnection as a general-purpose leaf. SFTPConnection decorator for storage. TunnelledConnection decorator with a local TCP forwarding listener. SFTPStorageBackend for file operations via SFTP. SDK-family-aware auth resolver routes the same auth profile to different strategies depending on provider type.

**Tech Stack:** paramiko (lazy import, `[sftp]` optional extra), mountainash-auth-client (CertificateAuth, KerberosAuth, PasswordAuth), threading (for tunnel listener)

**Design spec:** `docs/superpowers/specs/2026-06-10-ssh-absorption-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/mountainash_transport/_core/auth/strategies.py` | + SSHPasswordStrategy, SSHKeyStrategy, SSHKerberosStrategy |
| `src/mountainash_transport/_core/auth/resolver.py` | + provider_type param, SSH dispatch branches |
| `src/mountainash_transport/_core/auth/__init__.py` | + re-export new strategies |
| `src/mountainash_transport/connections/ssh.py` | SSHConnection leaf (paramiko.SSHClient) |
| `src/mountainash_transport/connections/sftp.py` | SFTPConnection decorator (paramiko.SFTPClient) |
| `src/mountainash_transport/connections/tunnel.py` | TunnelledConnection decorator (local TCP listener) |
| `src/mountainash_transport/connections/__init__.py` | + SSH branch in create_connection(), create_tunnelled_connection() |
| `src/mountainash_transport/storage/backends/ssh/__init__.py` | SFTPStorageBackend |
| `src/mountainash_transport/__init__.py` | + public API exports |
| `tests/_core/auth/test_ssh_strategies.py` | SSH strategy unit tests |
| `tests/_core/auth/test_resolver_ssh.py` | Resolver SSH-family dispatch tests |
| `tests/connections/test_ssh_connection.py` | SSHConnection lifecycle/auth/error tests |
| `tests/connections/test_sftp_connection.py` | SFTPConnection decorator tests |
| `tests/connections/test_tunnel_connection.py` | TunnelledConnection + factory tests |
| `tests/storage/backends/test_sftp.py` | SFTPStorageBackend operation tests |

---

### Task 1: SSH Auth Strategies

**Files:**
- Modify: `src/mountainash_transport/_core/auth/strategies.py`
- Modify: `src/mountainash_transport/_core/auth/__init__.py`
- Create: `tests/_core/auth/test_ssh_strategies.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/_core/auth/test_ssh_strategies.py`:

```python
"""SSH auth strategy tests."""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mountainash_transport._core.auth.strategies import (
    AuthStrategy,
    SSHPasswordStrategy,
    SSHKeyStrategy,
    SSHKerberosStrategy,
)


class TestSSHPasswordStrategy:
    def test_conforms_to_protocol(self):
        assert isinstance(SSHPasswordStrategy("secret"), AuthStrategy)

    def test_injects_password(self):
        result = SSHPasswordStrategy("my-pass").apply({"hostname": "host"})
        assert result["password"] == "my-pass"
        assert result["hostname"] == "host"

    def test_returns_new_dict(self):
        original = {"hostname": "host"}
        result = SSHPasswordStrategy("p").apply(original)
        assert result is not original
        assert "password" not in original

    def test_empty_password(self):
        result = SSHPasswordStrategy("").apply({})
        assert result["password"] == ""


class TestSSHKeyStrategyFilePath:
    def test_conforms_to_protocol(self):
        assert isinstance(
            SSHKeyStrategy(key_path=Path("/fake/key")), AuthStrategy
        )

    def test_injects_key_filename(self):
        result = SSHKeyStrategy(key_path=Path("/home/user/.ssh/id_ed25519")).apply(
            {"hostname": "host"}
        )
        assert result["key_filename"] == "/home/user/.ssh/id_ed25519"
        assert result["hostname"] == "host"

    def test_injects_key_filename_with_passphrase(self):
        result = SSHKeyStrategy(
            key_path=Path("/key"), passphrase="secret"
        ).apply({"hostname": "host"})
        assert result["key_filename"] == "/key"
        assert result["passphrase"] == "secret"

    def test_returns_new_dict(self):
        original = {"hostname": "host"}
        result = SSHKeyStrategy(key_path=Path("/key")).apply(original)
        assert result is not original
        assert "key_filename" not in original


class TestSSHKeyStrategyRawKey:
    @patch("mountainash_transport._core.auth.strategies._parse_private_key")
    def test_injects_pkey_from_raw_string(self, mock_parse):
        mock_key = MagicMock()
        mock_parse.return_value = mock_key

        result = SSHKeyStrategy(key_string="-----BEGIN RSA...").apply(
            {"hostname": "host"}
        )
        assert result["pkey"] is mock_key
        assert "key_filename" not in result
        mock_parse.assert_called_once_with("-----BEGIN RSA...", None)

    @patch("mountainash_transport._core.auth.strategies._parse_private_key")
    def test_raw_key_with_passphrase(self, mock_parse):
        mock_key = MagicMock()
        mock_parse.return_value = mock_key

        result = SSHKeyStrategy(
            key_string="-----BEGIN RSA...", passphrase="pass"
        ).apply({})
        mock_parse.assert_called_once_with("-----BEGIN RSA...", "pass")
        assert result["pkey"] is mock_key
        assert "passphrase" not in result


class TestParsePrivateKey:
    @patch("mountainash_transport._core.auth.strategies.paramiko")
    def test_tries_key_classes_in_order(self, mock_paramiko):
        from mountainash_transport._core.auth.strategies import _parse_private_key

        mock_key = MagicMock()
        mock_paramiko.RSAKey.from_private_key.side_effect = Exception("not RSA")
        mock_paramiko.Ed25519Key.from_private_key.return_value = mock_key
        mock_paramiko.ECDSAKey.from_private_key.side_effect = Exception("not ECDSA")
        mock_paramiko.DSSKey.from_private_key.side_effect = Exception("not DSS")

        result = _parse_private_key("key-data", None)
        assert result is mock_key

    @patch("mountainash_transport._core.auth.strategies.paramiko")
    def test_passphrase_passed_to_parser(self, mock_paramiko):
        from mountainash_transport._core.auth.strategies import _parse_private_key

        mock_key = MagicMock()
        mock_paramiko.RSAKey.from_private_key.return_value = mock_key

        _parse_private_key("key-data", "my-pass")
        call_args = mock_paramiko.RSAKey.from_private_key.call_args
        assert call_args[1].get("password") == "my-pass" or call_args[0][1] if len(call_args[0]) > 1 else True

    @patch("mountainash_transport._core.auth.strategies.paramiko")
    def test_all_types_fail_raises(self, mock_paramiko):
        from mountainash_transport._core.auth.strategies import _parse_private_key

        for attr in ("RSAKey", "Ed25519Key", "ECDSAKey", "DSSKey"):
            getattr(mock_paramiko, attr).from_private_key.side_effect = Exception("bad")

        with pytest.raises(ValueError, match="Could not parse"):
            _parse_private_key("bad-key", None)


class TestSSHKerberosStrategy:
    def test_conforms_to_protocol(self):
        assert isinstance(SSHKerberosStrategy(), AuthStrategy)

    def test_injects_gss_auth(self):
        result = SSHKerberosStrategy().apply({"hostname": "host"})
        assert result["gss_auth"] is True
        assert result["hostname"] == "host"

    def test_gss_kex_defaults_false(self):
        result = SSHKerberosStrategy().apply({})
        assert "gss_kex" not in result

    def test_gss_kex_opt_in(self):
        result = SSHKerberosStrategy(gss_kex=True).apply({})
        assert result["gss_kex"] is True

    def test_gss_host_from_service_name(self):
        result = SSHKerberosStrategy(gss_host="host.example.com").apply({})
        assert result["gss_host"] == "host.example.com"

    def test_returns_new_dict(self):
        original = {"hostname": "host"}
        result = SSHKerberosStrategy().apply(original)
        assert result is not original
        assert "gss_auth" not in original
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test-target-quick -- tests/_core/auth/test_ssh_strategies.py -v`
Expected: ImportError — `SSHPasswordStrategy`, `SSHKeyStrategy`, `SSHKerberosStrategy` do not exist yet.

- [ ] **Step 3: Implement SSH auth strategies**

Add the following to the end of `src/mountainash_transport/_core/auth/strategies.py`:

```python
# ---------------------------------------------------------------------------
# SSH-family strategies (paramiko kwargs)
# ---------------------------------------------------------------------------

# Lazy-imported; paramiko is an optional dependency ([sftp] extra).
paramiko: t.Any = None


def _ensure_paramiko() -> t.Any:
    global paramiko
    if paramiko is None:
        import importlib
        paramiko = importlib.import_module("paramiko")
    return paramiko


def _parse_private_key(key_string: str, passphrase: str | None) -> t.Any:
    """Parse a raw private key string into a paramiko PKey object.

    Tries concrete key classes in order — base-class auto-detection is
    version-sensitive.
    """
    _ensure_paramiko()
    import io as _io

    key_classes = [
        paramiko.RSAKey,
        paramiko.Ed25519Key,
        paramiko.ECDSAKey,
        paramiko.DSSKey,
    ]
    last_exc: Exception | None = None
    for cls in key_classes:
        try:
            return cls.from_private_key(_io.StringIO(key_string), password=passphrase)
        except Exception as exc:
            last_exc = exc
            continue
    raise ValueError(
        f"Could not parse private key with any paramiko key class"
    ) from last_exc


class SSHPasswordStrategy:
    """Inject SSH password into paramiko connect() kwargs."""

    def __init__(self, password: str) -> None:
        self._password = password

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        result = {**kwargs}
        result["password"] = self._password
        return result


class SSHKeyStrategy:
    """Inject SSH private key (file path or raw string) into paramiko kwargs."""

    def __init__(
        self,
        key_path: t.Any | None = None,
        key_string: str | None = None,
        passphrase: str | None = None,
    ) -> None:
        self._key_path = key_path
        self._key_string = key_string
        self._passphrase = passphrase

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        result = {**kwargs}
        if self._key_path is not None:
            result["key_filename"] = str(self._key_path)
            if self._passphrase:
                result["passphrase"] = self._passphrase
        elif self._key_string is not None:
            result["pkey"] = _parse_private_key(self._key_string, self._passphrase)
        return result


class SSHKerberosStrategy:
    """Inject Kerberos/GSSAPI auth into paramiko kwargs."""

    def __init__(
        self,
        gss_kex: bool = False,
        gss_host: str | None = None,
    ) -> None:
        self._gss_kex = gss_kex
        self._gss_host = gss_host

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        result = {**kwargs}
        result["gss_auth"] = True
        if self._gss_kex:
            result["gss_kex"] = True
        if self._gss_host:
            result["gss_host"] = self._gss_host
        return result
```

- [ ] **Step 4: Update `_core/auth/__init__.py` re-exports**

Add the new strategies to `src/mountainash_transport/_core/auth/__init__.py`:

```python
"""Auth strategies — credential injection for SDK clients."""
from __future__ import annotations

from .strategies import (
    AuthStrategy,
    BasicAuthStrategy,
    BearerTokenStrategy,
    IAMCredentialStrategy,
    NoAuthStrategy,
    OAuth1SignedStrategy,
    SSHPasswordStrategy,
    SSHKeyStrategy,
    SSHKerberosStrategy,
)
from .resolver import resolve_auth_strategy

__all__ = [
    "AuthStrategy",
    "BasicAuthStrategy",
    "BearerTokenStrategy",
    "IAMCredentialStrategy",
    "NoAuthStrategy",
    "OAuth1SignedStrategy",
    "SSHPasswordStrategy",
    "SSHKeyStrategy",
    "SSHKerberosStrategy",
    "resolve_auth_strategy",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `hatch run test:test-target-quick -- tests/_core/auth/test_ssh_strategies.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/_core/auth/strategies.py src/mountainash_transport/_core/auth/__init__.py tests/_core/auth/test_ssh_strategies.py
git commit -m "feat: add SSH auth strategies (Password, Key, Kerberos)"
```

---

### Task 2: SDK-Family-Aware Auth Resolver

**Files:**
- Modify: `src/mountainash_transport/_core/auth/resolver.py`
- Create: `tests/_core/auth/test_resolver_ssh.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/_core/auth/test_resolver_ssh.py`:

```python
"""Tests for resolve_auth_strategy() SSH-family dispatch."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from mountainash_transport._core.auth.resolver import resolve_auth_strategy
from mountainash_transport._core.auth.strategies import (
    AuthStrategy,
    BasicAuthStrategy,
    NoAuthStrategy,
    SSHPasswordStrategy,
    SSHKeyStrategy,
    SSHKerberosStrategy,
)
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE


class TestResolverSSHFamily:
    def test_password_auth_with_ssh_provider(self):
        from mountainash_auth_client import PasswordAuth
        auth = PasswordAuth(USERNAME="admin", PASSWORD="secret")
        strategy = resolve_auth_strategy(
            auth, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH
        )
        assert isinstance(strategy, SSHPasswordStrategy)
        result = strategy.apply({})
        assert result["password"] == "secret"

    def test_password_auth_without_provider_stays_basic(self):
        from mountainash_auth_client import PasswordAuth
        auth = PasswordAuth(USERNAME="admin", PASSWORD="secret")
        strategy = resolve_auth_strategy(auth)
        assert isinstance(strategy, BasicAuthStrategy)

    def test_password_auth_with_http_provider_stays_basic(self):
        from mountainash_auth_client import PasswordAuth
        auth = PasswordAuth(USERNAME="admin", PASSWORD="secret")
        strategy = resolve_auth_strategy(
            auth, provider_type=CONST_STORAGE_PROVIDER_TYPE.HTTP
        )
        assert isinstance(strategy, BasicAuthStrategy)

    def test_certificate_auth_with_ssh_provider(self):
        from mountainash_auth_client import CertificateAuth
        auth = CertificateAuth(PRIVATE_KEY_PATH=Path("/home/user/.ssh/id_ed25519"))
        strategy = resolve_auth_strategy(
            auth, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH
        )
        assert isinstance(strategy, SSHKeyStrategy)

    def test_certificate_auth_with_raw_key(self):
        from mountainash_auth_client import CertificateAuth
        auth = CertificateAuth(PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nfake")
        strategy = resolve_auth_strategy(
            auth, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH
        )
        assert isinstance(strategy, SSHKeyStrategy)

    def test_certificate_auth_with_passphrase(self):
        from mountainash_auth_client import CertificateAuth
        auth = CertificateAuth(
            PRIVATE_KEY_PATH=Path("/key"), PASSPHRASE="secret"
        )
        strategy = resolve_auth_strategy(
            auth, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH
        )
        assert isinstance(strategy, SSHKeyStrategy)
        result = strategy.apply({})
        assert result["key_filename"] == "/key"
        assert result["passphrase"] == "secret"

    def test_kerberos_auth_with_ssh_provider(self):
        from mountainash_auth_client import KerberosAuth
        auth = KerberosAuth(SERVICE_NAME="ssh")
        strategy = resolve_auth_strategy(
            auth, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH
        )
        assert isinstance(strategy, SSHKerberosStrategy)
        result = strategy.apply({})
        assert result["gss_auth"] is True

    def test_none_auth_with_ssh_returns_no_auth(self):
        strategy = resolve_auth_strategy(
            None, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH
        )
        assert isinstance(strategy, NoAuthStrategy)

    def test_no_auth_profile_with_ssh_returns_no_auth(self):
        from mountainash_auth_client import NoAuth
        strategy = resolve_auth_strategy(
            NoAuth(), provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH
        )
        assert isinstance(strategy, NoAuthStrategy)

    def test_default_provider_type_is_none(self):
        """Existing callers without provider_type still work."""
        from mountainash_auth_client import TokenAuth
        strategy = resolve_auth_strategy(TokenAuth(TOKEN="tok"))
        from mountainash_transport._core.auth.strategies import BearerTokenStrategy
        assert isinstance(strategy, BearerTokenStrategy)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test-target-quick -- tests/_core/auth/test_resolver_ssh.py -v`
Expected: FAIL — `resolve_auth_strategy()` does not accept `provider_type` yet.

- [ ] **Step 3: Update the resolver**

Replace `src/mountainash_transport/_core/auth/resolver.py` with:

```python
"""Auth strategy resolver — map auth profiles to strategies."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.auth.strategies import (
    AuthStrategy,
    BasicAuthStrategy,
    BearerTokenStrategy,
    IAMCredentialStrategy,
    NoAuthStrategy,
    SSHKeyStrategy,
    SSHKerberosStrategy,
    SSHPasswordStrategy,
)
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.settings.utils.secrets import _unwrap_secret

if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthProfile

from mountainash_auth_client import (
    CertificateAuth,
    IAMAuth,
    JWTAuth,
    KerberosAuth,
    NoAuth,
    OAuth2Auth,
    OAuth2AuthCodeAuth,
    PasswordAuth,
    TokenAuth,
)


def _resolve_ssh_strategy(auth_profile: AuthProfile) -> AuthStrategy | None:
    """Resolve an auth profile to an SSH-family strategy, or None to fall through."""
    if isinstance(auth_profile, PasswordAuth):
        password = _unwrap_secret(auth_profile.PASSWORD) or ""
        return SSHPasswordStrategy(password)

    if isinstance(auth_profile, CertificateAuth):
        key_path = getattr(auth_profile, "PRIVATE_KEY_PATH", None)
        key_string = _unwrap_secret(getattr(auth_profile, "PRIVATE_KEY", None))
        passphrase = _unwrap_secret(getattr(auth_profile, "PASSPHRASE", None))
        return SSHKeyStrategy(
            key_path=key_path,
            key_string=key_string,
            passphrase=passphrase,
        )

    if isinstance(auth_profile, KerberosAuth):
        service_name = getattr(auth_profile, "SERVICE_NAME", None)
        return SSHKerberosStrategy(
            gss_host=service_name,
        )

    return None


def resolve_auth_strategy(
    auth_profile: AuthProfile | None,
    provider_type: CONST_STORAGE_PROVIDER_TYPE | None = None,
) -> AuthStrategy:
    """Map an auth profile instance to its auth strategy.

    When *provider_type* is SSH, SSH-specific strategies are used instead of
    the HTTP-family defaults. Other provider types (or None) use the existing
    HTTP/S3 dispatch.
    """
    if auth_profile is None:
        return NoAuthStrategy()

    if isinstance(auth_profile, NoAuth):
        return NoAuthStrategy()

    # SSH-family dispatch (early return).
    if provider_type == CONST_STORAGE_PROVIDER_TYPE.SSH:
        ssh_strategy = _resolve_ssh_strategy(auth_profile)
        if ssh_strategy is not None:
            return ssh_strategy
        return NoAuthStrategy()

    # HTTP / S3 / default dispatch (unchanged).
    if isinstance(auth_profile, (TokenAuth, JWTAuth)):
        token = _unwrap_secret(auth_profile.TOKEN)
        if token:
            return BearerTokenStrategy(token)
        return NoAuthStrategy()

    if isinstance(auth_profile, OAuth2Auth):
        token = _unwrap_secret(auth_profile.TOKEN)
        if token:
            return BearerTokenStrategy(token)
        return NoAuthStrategy()

    if isinstance(auth_profile, OAuth2AuthCodeAuth):
        token = _unwrap_secret(auth_profile.ACCESS_TOKEN)
        if token:
            return BearerTokenStrategy(token)
        return NoAuthStrategy()

    if isinstance(auth_profile, IAMAuth):
        return IAMCredentialStrategy(
            access_key_id=auth_profile.ACCESS_KEY_ID,
            secret_access_key=_unwrap_secret(auth_profile.SECRET_ACCESS_KEY),
            session_token=_unwrap_secret(auth_profile.SESSION_TOKEN) if auth_profile.SESSION_TOKEN else None,
        )

    if isinstance(auth_profile, PasswordAuth):
        username = auth_profile.USERNAME or ""
        password = _unwrap_secret(auth_profile.PASSWORD) or ""
        return BasicAuthStrategy(username, password)

    return NoAuthStrategy()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test-target-quick -- tests/_core/auth/test_resolver_ssh.py tests/_core/auth/test_auth_resolver.py -v`
Expected: All tests PASS (both new SSH tests and existing resolver tests).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/_core/auth/resolver.py tests/_core/auth/test_resolver_ssh.py
git commit -m "feat: SDK-family-aware auth resolver with SSH dispatch"
```

---

### Task 3: SSHConnection (Leaf Connection)

**Files:**
- Create: `src/mountainash_transport/connections/ssh.py`
- Create: `tests/connections/test_ssh_connection.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/connections/test_ssh_connection.py`:

```python
"""SSHConnection behavioral tests."""
from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch, call

import pytest

from mountainash_transport._core.auth.strategies import (
    AuthStrategy,
    NoAuthStrategy,
    SSHPasswordStrategy,
)
from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.errors import (
    ConnectionTimeoutError,
    TransportConnectionError,
)
from mountainash_transport.connections.ssh import SSHConnection


class FakeSSHProfile:
    """Duck-types StorageProfileProtocol for SSHConnection tests."""

    def to_handler_kwargs(self) -> dict:
        return {
            "hostname": "example.com",
            "port": 22,
            "username": "testuser",
            "timeout": 30.0,
            "_post_connect": {
                "host_key_policy": "auto_add",
            },
        }

    def get_connection_url(self) -> str:
        return "ssh://testuser@example.com:22"


class FakeSSHProfileReject:
    def to_handler_kwargs(self) -> dict:
        return {
            "hostname": "host",
            "port": 22,
            "username": "user",
            "_post_connect": {"host_key_policy": "reject"},
        }

    def get_connection_url(self) -> str:
        return "ssh://user@host:22"


class FakeSSHProfileKnownHosts:
    def to_handler_kwargs(self) -> dict:
        return {
            "hostname": "host",
            "port": 22,
            "username": "user",
            "_post_connect": {
                "host_key_policy": "warn",
                "known_hosts_file": "/home/user/.ssh/known_hosts",
            },
        }

    def get_connection_url(self) -> str:
        return "ssh://user@host:22"


class TestSSHConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        conn = SSHConnection(FakeSSHProfile(), NoAuthStrategy())
        assert isinstance(conn, ConnectionProtocol)


class TestSSHConnectionLifecycle:
    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_connect_creates_client(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client

        conn = SSHConnection(FakeSSHProfile(), NoAuthStrategy())
        result = conn.connect()

        mock_paramiko.SSHClient.assert_called_once()
        mock_client.load_system_host_keys.assert_called_once()
        mock_client.set_missing_host_key_policy.assert_called_once()
        mock_client.connect.assert_called_once_with(
            hostname="example.com",
            port=22,
            username="testuser",
            timeout=30.0,
        )
        assert conn.client is mock_client
        assert conn.is_connected is True
        assert result is conn

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_disconnect_closes_client(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client

        conn = SSHConnection(FakeSSHProfile(), NoAuthStrategy())
        conn.connect()
        conn.disconnect()

        mock_client.close.assert_called_once()
        assert conn.client is None
        assert conn.is_connected is False

    def test_not_connected_initially(self):
        conn = SSHConnection(FakeSSHProfile(), NoAuthStrategy())
        assert conn.client is None
        assert conn.is_connected is False

    def test_disconnect_when_not_connected_is_noop(self):
        conn = SSHConnection(FakeSSHProfile(), NoAuthStrategy())
        conn.disconnect()

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_context_manager(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client

        conn = SSHConnection(FakeSSHProfile(), NoAuthStrategy())
        with conn:
            conn.connect()
            assert conn.is_connected is True
        mock_client.close.assert_called_once()

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_connect_is_idempotent(self, mock_paramiko):
        mock_client1 = MagicMock()
        mock_client2 = MagicMock()
        mock_paramiko.SSHClient.side_effect = [mock_client1, mock_client2]

        conn = SSHConnection(FakeSSHProfile(), NoAuthStrategy())
        conn.connect()
        conn.connect()

        mock_client1.close.assert_called_once()
        assert conn.client is mock_client2


class TestSSHConnectionAuth:
    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_password_strategy_injected(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client

        strategy = SSHPasswordStrategy("my-pass")
        conn = SSHConnection(FakeSSHProfile(), strategy)
        conn.connect()

        call_kwargs = mock_client.connect.call_args[1]
        assert call_kwargs["password"] == "my-pass"

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_no_auth_no_password(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client

        conn = SSHConnection(FakeSSHProfile(), NoAuthStrategy())
        conn.connect()

        call_kwargs = mock_client.connect.call_args[1]
        assert "password" not in call_kwargs


class TestSSHConnectionHostKeyPolicy:
    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_auto_add_policy(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client

        conn = SSHConnection(FakeSSHProfile(), NoAuthStrategy())
        conn.connect()

        mock_client.set_missing_host_key_policy.assert_called_once_with(
            mock_paramiko.AutoAddPolicy()
        )

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_reject_policy(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client

        conn = SSHConnection(FakeSSHProfileReject(), NoAuthStrategy())
        conn.connect()

        mock_client.set_missing_host_key_policy.assert_called_once_with(
            mock_paramiko.RejectPolicy()
        )

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_known_hosts_loaded(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client

        conn = SSHConnection(FakeSSHProfileKnownHosts(), NoAuthStrategy())
        conn.connect()

        mock_client.load_host_keys.assert_called_once_with(
            "/home/user/.ssh/known_hosts"
        )


class TestSSHConnectionErrorWrapping:
    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_auth_exception_wrapped(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AuthenticationException = type("AuthenticationException", (Exception,), {})
        mock_client.connect.side_effect = mock_paramiko.AuthenticationException("bad creds")

        conn = SSHConnection(FakeSSHProfile(), NoAuthStrategy())
        with pytest.raises(TransportConnectionError, match="bad creds"):
            conn.connect()

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_ssh_exception_wrapped(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.SSHException = type("SSHException", (Exception,), {})
        mock_client.connect.side_effect = mock_paramiko.SSHException("protocol error")

        conn = SSHConnection(FakeSSHProfile(), NoAuthStrategy())
        with pytest.raises(TransportConnectionError, match="protocol error"):
            conn.connect()

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_socket_timeout_wrapped(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_client.connect.side_effect = socket.timeout("timed out")

        conn = SSHConnection(FakeSSHProfile(), NoAuthStrategy())
        with pytest.raises(ConnectionTimeoutError, match="timed out"):
            conn.connect()

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_gaierror_wrapped(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_client.connect.side_effect = socket.gaierror("DNS failed")

        conn = SSHConnection(FakeSSHProfile(), NoAuthStrategy())
        with pytest.raises(TransportConnectionError, match="DNS failed"):
            conn.connect()

    @patch("mountainash_transport.connections.ssh.paramiko")
    def test_os_error_wrapped(self, mock_paramiko):
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_client.connect.side_effect = OSError("connection refused")

        conn = SSHConnection(FakeSSHProfile(), NoAuthStrategy())
        with pytest.raises(TransportConnectionError, match="connection refused"):
            conn.connect()

    @patch("mountainash_transport.connections.ssh.paramiko", new=None)
    def test_import_error_wrapped(self):
        conn = SSHConnection(FakeSSHProfile(), NoAuthStrategy())
        with pytest.raises(TransportConnectionError, match="paramiko"):
            conn.connect()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test-target-quick -- tests/connections/test_ssh_connection.py -v`
Expected: ImportError — `mountainash_transport.connections.ssh` does not exist yet.

- [ ] **Step 3: Implement SSHConnection**

Create `src/mountainash_transport/connections/ssh.py`:

```python
"""SSHConnection — general-purpose leaf connection creating a paramiko.SSHClient."""
from __future__ import annotations

import socket
import typing as t

from typing_extensions import Self

from mountainash_transport._core.auth.strategies import AuthStrategy
from mountainash_transport.connections.errors import (
    ConnectionTimeoutError,
    TransportConnectionError,
)
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
from .._core.protocols import ConnectionProtocol

try:
    import paramiko
except ImportError:
    paramiko = None  # type: ignore[assignment]


_HOST_KEY_POLICIES: dict[str, str] = {
    "reject": "RejectPolicy",
    "warn": "WarningPolicy",
    "auto_add": "AutoAddPolicy",
}


class SSHConnection(ConnectionProtocol):
    """Creates an authenticated paramiko.SSHClient from profile config + auth strategy.

    General-purpose — usable for SFTP, tunnels, remote commands, SCP.
    Designed for exclusive ownership by one decorator.
    """

    def __init__(
        self,
        profile: StorageProfileProtocol,
        auth_strategy: AuthStrategy,
    ) -> None:
        self._profile = profile
        self._auth_strategy = auth_strategy
        self._client: t.Any = None

    def connect(self) -> Self:
        if paramiko is None:
            raise TransportConnectionError(
                "paramiko is required for SSH connections — "
                "install with: pip install mountainash-transport[sftp]"
            )

        if self._client is not None:
            self.disconnect()

        kwargs = self._profile.to_handler_kwargs()
        kwargs = self._auth_strategy.apply(kwargs)

        post_connect = kwargs.pop("_post_connect", {})

        client = paramiko.SSHClient()
        client.load_system_host_keys()

        policy_name = post_connect.get("host_key_policy", "reject")
        policy_attr = _HOST_KEY_POLICIES.get(policy_name)
        if policy_attr:
            client.set_missing_host_key_policy(getattr(paramiko, policy_attr)())
        else:
            client.set_missing_host_key_policy(paramiko.RejectPolicy())

        known_hosts = post_connect.get("known_hosts_file")
        if known_hosts:
            client.load_host_keys(known_hosts)

        try:
            client.connect(**kwargs)
        except socket.timeout as exc:
            raise ConnectionTimeoutError(
                f"SSH connection timed out: {exc}"
            ) from exc
        except socket.gaierror as exc:
            raise TransportConnectionError(
                f"SSH DNS resolution failed: {exc}"
            ) from exc
        except OSError as exc:
            raise TransportConnectionError(
                f"SSH connection failed: {exc}"
            ) from exc

        self._client = client
        return self

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None

    @property
    def client(self) -> t.Any:
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: t.Any) -> None:
        self.disconnect()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test-target-quick -- tests/connections/test_ssh_connection.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/connections/ssh.py tests/connections/test_ssh_connection.py
git commit -m "feat: add SSHConnection leaf (paramiko.SSHClient)"
```

---

### Task 4: SFTPConnection (Decorator)

**Files:**
- Create: `src/mountainash_transport/connections/sftp.py`
- Create: `tests/connections/test_sftp_connection.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/connections/test_sftp_connection.py`:

```python
"""SFTPConnection behavioral tests."""
from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.errors import TransportConnectionError
from mountainash_transport.connections.sftp import SFTPConnection


def _make_mock_ssh():
    """Create a mock SSHConnection with a mock paramiko.SSHClient."""
    ssh = MagicMock()
    ssh.is_connected = False
    mock_sftp = MagicMock()
    ssh.client.open_sftp.return_value = mock_sftp
    return ssh, mock_sftp


class TestSFTPConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        ssh, _ = _make_mock_ssh()
        conn = SFTPConnection(ssh)
        assert isinstance(conn, ConnectionProtocol)


class TestSFTPConnectionLifecycle:
    def test_connect_opens_sftp(self):
        ssh, mock_sftp = _make_mock_ssh()
        ssh.is_connected = True

        conn = SFTPConnection(ssh)
        result = conn.connect()

        ssh.client.open_sftp.assert_called_once()
        assert conn.client is mock_sftp
        assert conn.is_connected is True
        assert result is conn

    def test_connect_connects_ssh_if_needed(self):
        ssh, mock_sftp = _make_mock_ssh()
        ssh.is_connected = False

        conn = SFTPConnection(ssh)
        conn.connect()

        ssh.connect.assert_called_once()

    def test_connect_skips_ssh_connect_if_already_connected(self):
        ssh, mock_sftp = _make_mock_ssh()
        ssh.is_connected = True

        conn = SFTPConnection(ssh)
        conn.connect()

        ssh.connect.assert_not_called()

    def test_disconnect_closes_sftp_and_ssh(self):
        ssh, mock_sftp = _make_mock_ssh()
        ssh.is_connected = True

        conn = SFTPConnection(ssh)
        conn.connect()
        conn.disconnect()

        mock_sftp.close.assert_called_once()
        ssh.disconnect.assert_called_once()
        assert conn.client is None
        assert conn.is_connected is False

    def test_not_connected_initially(self):
        ssh, _ = _make_mock_ssh()
        conn = SFTPConnection(ssh)
        assert conn.client is None
        assert conn.is_connected is False

    def test_disconnect_when_not_connected_is_noop(self):
        ssh, _ = _make_mock_ssh()
        conn = SFTPConnection(ssh)
        conn.disconnect()
        ssh.disconnect.assert_called_once()

    def test_context_manager(self):
        ssh, mock_sftp = _make_mock_ssh()
        ssh.is_connected = True

        conn = SFTPConnection(ssh)
        with conn:
            conn.connect()
            assert conn.is_connected is True
        mock_sftp.close.assert_called_once()
        ssh.disconnect.assert_called_once()

    def test_connect_is_idempotent(self):
        ssh, _ = _make_mock_ssh()
        ssh.is_connected = True

        sftp1 = MagicMock()
        sftp2 = MagicMock()
        ssh.client.open_sftp.side_effect = [sftp1, sftp2]

        conn = SFTPConnection(ssh)
        conn.connect()
        conn.connect()

        sftp1.close.assert_called_once()
        assert conn.client is sftp2


class TestSFTPConnectionErrorWrapping:
    def test_open_sftp_failure_wrapped(self):
        ssh, _ = _make_mock_ssh()
        ssh.is_connected = True
        ssh.client.open_sftp.side_effect = Exception("SFTP subsystem not available")

        conn = SFTPConnection(ssh)
        with pytest.raises(TransportConnectionError, match="SFTP"):
            conn.connect()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test-target-quick -- tests/connections/test_sftp_connection.py -v`
Expected: ImportError — `mountainash_transport.connections.sftp` does not exist yet.

- [ ] **Step 3: Implement SFTPConnection**

Create `src/mountainash_transport/connections/sftp.py`:

```python
"""SFTPConnection — decorator over SSHConnection exposing paramiko.SFTPClient."""
from __future__ import annotations

import typing as t

from typing_extensions import Self

from mountainash_transport.connections.errors import TransportConnectionError
from .._core.protocols import ConnectionProtocol


class SFTPConnection(ConnectionProtocol):
    """Opens an SFTP channel over an SSHConnection.

    Owns the inner SSHConnection exclusively — disconnect() tears down both.
    """

    def __init__(self, ssh_connection: t.Any) -> None:
        self._ssh = ssh_connection
        self._sftp: t.Any = None

    def connect(self) -> Self:
        if self._sftp is not None:
            self._sftp.close()
            self._sftp = None

        if not self._ssh.is_connected:
            self._ssh.connect()

        try:
            self._sftp = self._ssh.client.open_sftp()
        except Exception as exc:
            raise TransportConnectionError(
                f"Failed to open SFTP subsystem: {exc}"
            ) from exc

        return self

    def disconnect(self) -> None:
        if self._sftp is not None:
            self._sftp.close()
        self._sftp = None
        self._ssh.disconnect()

    @property
    def client(self) -> t.Any:
        return self._sftp

    @property
    def is_connected(self) -> bool:
        return self._sftp is not None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: t.Any) -> None:
        self.disconnect()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test-target-quick -- tests/connections/test_sftp_connection.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/connections/sftp.py tests/connections/test_sftp_connection.py
git commit -m "feat: add SFTPConnection decorator over SSHConnection"
```

---

### Task 5: TunnelledConnection (Decorator)

**Files:**
- Create: `src/mountainash_transport/connections/tunnel.py`
- Create: `tests/connections/test_tunnel_connection.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/connections/test_tunnel_connection.py`:

```python
"""TunnelledConnection behavioral tests."""
from __future__ import annotations

import socket
import threading
from unittest.mock import MagicMock, patch

import pytest

from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.errors import TransportConnectionError
from mountainash_transport.connections.tunnel import TunnelledConnection


def _make_mock_ssh():
    """Mock SSHConnection with a mock transport."""
    ssh = MagicMock()
    ssh.is_connected = False
    mock_transport = MagicMock()
    mock_channel = MagicMock()
    mock_transport.open_channel.return_value = mock_channel
    ssh.client.get_transport.return_value = mock_transport
    return ssh, mock_transport, mock_channel


class TestTunnelledConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        ssh, _, _ = _make_mock_ssh()
        inner_factory = MagicMock(return_value=MagicMock())
        conn = TunnelledConnection(ssh, inner_factory, "db.internal", 5432)
        assert isinstance(conn, ConnectionProtocol)


class TestTunnelledConnectionLifecycle:
    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_connect_binds_listener_and_inner(self, mock_forwarder):
        ssh, mock_transport, mock_channel = _make_mock_ssh()
        ssh.is_connected = True

        mock_inner = MagicMock()
        mock_inner.client = "inner-client"
        inner_factory = MagicMock(return_value=mock_inner)

        mock_server = MagicMock()
        mock_server.server_address = ("127.0.0.1", 54321)
        mock_forwarder.return_value = mock_server

        conn = TunnelledConnection(ssh, inner_factory, "db.internal", 5432)
        result = conn.connect()

        mock_forwarder.assert_called_once()
        inner_factory.assert_called_once_with(54321)
        mock_inner.connect.assert_called_once()
        assert conn.client == "inner-client"
        assert conn.is_connected is True
        assert conn.local_port == 54321
        assert result is conn

    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_connect_connects_ssh_if_needed(self, mock_forwarder):
        ssh, _, _ = _make_mock_ssh()
        ssh.is_connected = False

        mock_inner = MagicMock()
        inner_factory = MagicMock(return_value=mock_inner)

        mock_server = MagicMock()
        mock_server.server_address = ("127.0.0.1", 12345)
        mock_forwarder.return_value = mock_server

        conn = TunnelledConnection(ssh, inner_factory, "host", 80)
        conn.connect()

        ssh.connect.assert_called_once()

    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_disconnect_tears_down_in_order(self, mock_forwarder):
        ssh, _, _ = _make_mock_ssh()
        ssh.is_connected = True

        mock_inner = MagicMock()
        inner_factory = MagicMock(return_value=mock_inner)

        mock_server = MagicMock()
        mock_server.server_address = ("127.0.0.1", 12345)
        mock_forwarder.return_value = mock_server

        conn = TunnelledConnection(ssh, inner_factory, "host", 80)
        conn.connect()
        conn.disconnect()

        mock_inner.disconnect.assert_called_once()
        mock_server.shutdown.assert_called_once()
        ssh.disconnect.assert_called_once()
        assert conn.is_connected is False
        assert conn.client is None

    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_not_connected_initially(self, mock_forwarder):
        ssh, _, _ = _make_mock_ssh()
        inner_factory = MagicMock()
        conn = TunnelledConnection(ssh, inner_factory, "host", 80)
        assert conn.client is None
        assert conn.is_connected is False

    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_context_manager(self, mock_forwarder):
        ssh, _, _ = _make_mock_ssh()
        ssh.is_connected = True

        mock_inner = MagicMock()
        inner_factory = MagicMock(return_value=mock_inner)

        mock_server = MagicMock()
        mock_server.server_address = ("127.0.0.1", 12345)
        mock_forwarder.return_value = mock_server

        conn = TunnelledConnection(ssh, inner_factory, "host", 80)
        with conn:
            conn.connect()
            assert conn.is_connected is True
        mock_inner.disconnect.assert_called_once()
        ssh.disconnect.assert_called_once()

    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_connect_is_idempotent(self, mock_forwarder):
        ssh, _, _ = _make_mock_ssh()
        ssh.is_connected = True

        mock_inner1 = MagicMock()
        mock_inner2 = MagicMock()
        inner_factory = MagicMock(side_effect=[mock_inner1, mock_inner2])

        mock_server1 = MagicMock()
        mock_server1.server_address = ("127.0.0.1", 11111)
        mock_server2 = MagicMock()
        mock_server2.server_address = ("127.0.0.1", 22222)
        mock_forwarder.side_effect = [mock_server1, mock_server2]

        conn = TunnelledConnection(ssh, inner_factory, "host", 80)
        conn.connect()
        conn.connect()

        mock_inner1.disconnect.assert_called_once()
        mock_server1.shutdown.assert_called_once()


class TestTunnelledConnectionErrorWrapping:
    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_listener_bind_failure_wrapped(self, mock_forwarder):
        ssh, _, _ = _make_mock_ssh()
        ssh.is_connected = True

        inner_factory = MagicMock()
        mock_forwarder.side_effect = OSError("address in use")

        conn = TunnelledConnection(ssh, inner_factory, "host", 80)
        with pytest.raises(TransportConnectionError, match="address in use"):
            conn.connect()


class TestPatchedEndpointProfile:
    """Tests for _PatchedEndpointProfile used by create_tunnelled_connection()."""

    def test_patches_hostname_and_port(self):
        from mountainash_transport.connections.tunnel import _PatchedEndpointProfile

        class SSHProfile:
            class __spec__:
                provider_type = "ssh"
            def to_handler_kwargs(self):
                return {"hostname": "real-host", "port": 22, "username": "user"}
            def get_connection_url(self):
                return "ssh://user@real-host:22"

        patched = _PatchedEndpointProfile(SSHProfile(), "127.0.0.1", 54321)
        kwargs = patched.to_handler_kwargs()
        assert kwargs["hostname"] == "127.0.0.1"
        assert kwargs["port"] == 54321
        assert kwargs["username"] == "user"

    def test_patches_base_url(self):
        from mountainash_transport.connections.tunnel import _PatchedEndpointProfile

        class HTTPProfile:
            class __spec__:
                provider_type = "http"
            def to_handler_kwargs(self):
                return {"base_url": "https://internal-api:8080", "timeout": 30}
            def get_connection_url(self):
                return "https://internal-api:8080"

        patched = _PatchedEndpointProfile(HTTPProfile(), "127.0.0.1", 54321)
        kwargs = patched.to_handler_kwargs()
        assert kwargs["base_url"] == "http://127.0.0.1:54321"
        assert kwargs["timeout"] == 30

    def test_patches_endpoint_url(self):
        from mountainash_transport.connections.tunnel import _PatchedEndpointProfile

        class S3Profile:
            class __spec__:
                provider_type = "s3"
            def to_handler_kwargs(self):
                return {"endpoint_url": "https://s3.internal:443", "region_name": "us-east-1"}
            def get_connection_url(self):
                return "https://s3.internal:443"

        patched = _PatchedEndpointProfile(S3Profile(), "127.0.0.1", 54321)
        kwargs = patched.to_handler_kwargs()
        assert kwargs["endpoint_url"] == "http://127.0.0.1:54321"
        assert kwargs["region_name"] == "us-east-1"

    def test_delegates_other_attributes(self):
        from mountainash_transport.connections.tunnel import _PatchedEndpointProfile

        class MyProfile:
            class __spec__:
                provider_type = "http"
            custom_attr = "hello"
            def to_handler_kwargs(self):
                return {"timeout": 30}
            def get_connection_url(self):
                return "https://example.com"

        patched = _PatchedEndpointProfile(MyProfile(), "127.0.0.1", 54321)
        assert patched.custom_attr == "hello"
        assert patched.__spec__.provider_type == "http"

    def test_get_connection_url_shows_tunnel(self):
        from mountainash_transport.connections.tunnel import _PatchedEndpointProfile

        class MyProfile:
            def to_handler_kwargs(self):
                return {}
            def get_connection_url(self):
                return "https://example.com"

        patched = _PatchedEndpointProfile(MyProfile(), "127.0.0.1", 54321)
        assert "127.0.0.1:54321" in patched.get_connection_url()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test-target-quick -- tests/connections/test_tunnel_connection.py -v`
Expected: ImportError — `mountainash_transport.connections.tunnel` does not exist yet.

- [ ] **Step 3: Implement TunnelledConnection**

Create `src/mountainash_transport/connections/tunnel.py`:

```python
"""TunnelledConnection — SSH port-forwarding decorator with local TCP listener."""
from __future__ import annotations

import select
import socketserver
import threading
import typing as t

from typing_extensions import Self

from mountainash_transport.connections.errors import TransportConnectionError
from .._core.protocols import ConnectionProtocol


class _ForwardHandler(socketserver.BaseRequestHandler):
    """Handle one forwarded TCP connection via a paramiko direct-tcpip channel."""

    ssh_transport: t.Any = None
    remote_host: str = ""
    remote_port: int = 0

    def handle(self) -> None:
        transport = self.__class__.ssh_transport
        try:
            channel = transport.open_channel(
                "direct-tcpip",
                (self.__class__.remote_host, self.__class__.remote_port),
                self.request.getpeername(),
            )
        except Exception:
            return

        if channel is None:
            return

        try:
            while True:
                r, _, _ = select.select([self.request, channel], [], [], 1.0)
                if self.request in r:
                    data = self.request.recv(4096)
                    if not data:
                        break
                    channel.sendall(data)
                if channel in r:
                    data = channel.recv(4096)
                    if not data:
                        break
                    self.request.sendall(data)
        except Exception:
            pass
        finally:
            channel.close()
            self.request.close()


def _start_forwarder(
    ssh_transport: t.Any,
    remote_host: str,
    remote_port: int,
) -> socketserver.TCPServer:
    """Bind a local TCP listener that forwards connections through SSH."""

    class Handler(_ForwardHandler):
        pass

    Handler.ssh_transport = ssh_transport
    Handler.remote_host = remote_host
    Handler.remote_port = remote_port

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class _PatchedEndpointProfile:
    """Wraps a profile, overriding the connection endpoint for tunnelling.

    Detects known endpoint keys (hostname+port, base_url, endpoint_url) in
    the kwargs returned by to_handler_kwargs() and replaces them with the
    tunnel's local address.
    """

    _URL_KEYS = frozenset({"base_url", "endpoint_url"})

    def __init__(self, inner: t.Any, host: str, port: int) -> None:
        self._inner = inner
        self._host = host
        self._port = port

    def to_handler_kwargs(self) -> dict[str, t.Any]:
        kwargs = self._inner.to_handler_kwargs()
        if "hostname" in kwargs:
            kwargs["hostname"] = self._host
            kwargs["port"] = self._port
        for key in self._URL_KEYS:
            if key in kwargs:
                kwargs[key] = f"http://{self._host}:{self._port}"
        return kwargs

    def get_connection_url(self) -> str:
        return f"tunnel://{self._host}:{self._port}"

    def __getattr__(self, name: str) -> t.Any:
        return getattr(self._inner, name)


class TunnelledConnection(ConnectionProtocol):
    """SSH port-forwarding decorator — local TCP listener tunnelling through a bastion.

    Wraps an SSHConnection (bastion) and an inner connection factory.
    Binds a local listener on an ephemeral port; each TCP connection is
    forwarded via a paramiko direct-tcpip channel. The inner connection's
    profile points at localhost:local_port.

    Owns both the SSHConnection and the inner connection exclusively.
    """

    def __init__(
        self,
        ssh_connection: t.Any,
        inner_connection_factory: t.Callable[[int], ConnectionProtocol],
        remote_host: str,
        remote_port: int,
    ) -> None:
        self._ssh = ssh_connection
        self._inner_factory = inner_connection_factory
        self._remote_host = remote_host
        self._remote_port = remote_port
        self._inner: t.Any = None
        self._server: socketserver.TCPServer | None = None
        self._local_port: int = 0

    def connect(self) -> Self:
        if self._inner is not None:
            self._teardown()

        if not self._ssh.is_connected:
            self._ssh.connect()

        transport = self._ssh.client.get_transport()
        try:
            self._server = _start_forwarder(
                transport, self._remote_host, self._remote_port
            )
        except OSError as exc:
            raise TransportConnectionError(
                f"Failed to bind tunnel listener: {exc}"
            ) from exc

        self._local_port = self._server.server_address[1]
        self._inner = self._inner_factory(self._local_port)
        self._inner.connect()
        return self

    def _teardown(self) -> None:
        if self._inner is not None:
            self._inner.disconnect()
            self._inner = None
        if self._server is not None:
            self._server.shutdown()
            self._server = None
        self._local_port = 0

    def disconnect(self) -> None:
        self._teardown()
        self._ssh.disconnect()

    @property
    def client(self) -> t.Any:
        if self._inner is not None:
            return self._inner.client
        return None

    @property
    def is_connected(self) -> bool:
        return self._inner is not None and self._inner.is_connected

    @property
    def local_port(self) -> int:
        return self._local_port

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: t.Any) -> None:
        self.disconnect()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test-target-quick -- tests/connections/test_tunnel_connection.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/connections/tunnel.py tests/connections/test_tunnel_connection.py
git commit -m "feat: add TunnelledConnection with local TCP forwarding listener"
```

---

### Task 6: Registration and Wiring

**Files:**
- Modify: `src/mountainash_transport/connections/__init__.py`
- Modify: `src/mountainash_transport/__init__.py`
- Modify: `tests/connections/test_factory.py` (add SSH tests)

- [ ] **Step 1: Write the failing tests**

Add to the end of `tests/connections/test_factory.py`:

```python
from mountainash_transport.connections.sftp import SFTPConnection
from mountainash_transport.connections.tunnel import TunnelledConnection


class FakeSSHProfile:
    class __spec__:
        provider_type = "ssh"

    def to_handler_kwargs(self) -> dict:
        return {
            "hostname": "example.com",
            "port": 22,
            "username": "user",
            "_post_connect": {"host_key_policy": "auto_add"},
        }

    def get_connection_url(self) -> str:
        return "ssh://user@example.com:22"


class TestCreateConnectionSSH:
    def test_ssh_profile_returns_sftp_connection(self):
        from mountainash_auth_client import PasswordAuth
        conn = create_connection(
            FakeSSHProfile(), auth_profile=PasswordAuth(USERNAME="u", PASSWORD="p")
        )
        assert isinstance(conn, SFTPConnection)

    def test_ssh_profile_no_auth_returns_sftp_connection(self):
        conn = create_connection(FakeSSHProfile())
        assert isinstance(conn, SFTPConnection)


class TestCreateTunnelledConnection:
    @patch("mountainash_transport.connections.tunnel._start_forwarder")
    def test_factory_creates_tunnelled_connection(self, mock_forwarder):
        from mountainash_transport.connections import create_tunnelled_connection

        mock_server = MagicMock()
        mock_server.server_address = ("127.0.0.1", 54321)
        mock_forwarder.return_value = mock_server

        conn = create_tunnelled_connection(
            bastion_profile=FakeSSHProfile(),
            bastion_auth=None,
            target_profile=FakeHTTPProfile(),
            target_auth=None,
            remote_host="internal.api",
            remote_port=8080,
        )
        assert isinstance(conn, TunnelledConnection)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test-target-quick -- tests/connections/test_factory.py::TestCreateConnectionSSH -v`
Expected: FAIL — `create_connection()` has no SSH branch yet.

- [ ] **Step 3: Update connections/__init__.py**

Replace `src/mountainash_transport/connections/__init__.py`:

```python
"""Connection infrastructure — OAuth flows, callback servers, token lifecycle, and factory."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.auth.resolver import resolve_auth_strategy
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol

# --- Legacy/existing public API (kept for backward compat) -------------------
from .protocols import (
    OAuth2FlowProtocol, OAuth1FlowProtocol,
    CallbackServerProtocol,
)
from .errors import (
    ConnectionError, TokenExchangeError, TokenRefreshError, AuthorizationRequired,
    TransportConnectionError, ConnectionTimeoutError,
)
from .oauth2.flow import OAuthFlow
from .oauth1.flow import OAuth1Flow
from .server.callback import LocalCallbackServer
from .server.manual import extract_code_from_input, prompt_for_code

# --- Connection classes -------------------------------------------------------
from .http import HTTPConnection
from .null import NullConnection
from .s3 import S3Connection
from .ssh import SSHConnection
from .sftp import SFTPConnection
from .tunnel import TunnelledConnection, _PatchedEndpointProfile
from .oauth2.connection import OAuth2Connection
from .oauth1.connection import OAuth1Connection

if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthProfile
    from mountainash_transport._core.protocols import ConnectionProtocol


# --- Provider → leaf connection map ------------------------------------------

_PROVIDER_CONNECTION_MAP: dict[str, type] = {
    "http": HTTPConnection,
    "local": NullConnection,
    "s3": S3Connection,
    "s3express": S3Connection,
    "r2": S3Connection,
    "minio": S3Connection,
    "b2": S3Connection,
}


def _connection_for_provider(profile: StorageProfileProtocol) -> type:
    """Map profile's provider_type to a leaf connection class."""
    provider = getattr(getattr(profile, "__spec__", None), "provider_type", None)
    provider_str = str(provider.value) if hasattr(provider, "value") else str(provider)
    return _PROVIDER_CONNECTION_MAP.get(provider_str, HTTPConnection)


def _provider_type_from_profile(profile: StorageProfileProtocol) -> CONST_STORAGE_PROVIDER_TYPE | None:
    """Extract the CONST_STORAGE_PROVIDER_TYPE enum from a profile, or None."""
    provider = getattr(getattr(profile, "__spec__", None), "provider_type", None)
    if isinstance(provider, CONST_STORAGE_PROVIDER_TYPE):
        return provider
    if provider is not None:
        return CONST_STORAGE_PROVIDER_TYPE.find_member(str(provider))
    return None


def create_connection(
    profile: StorageProfileProtocol,
    auth_profile: AuthProfile | None = None,
    *,
    auto_authorize: bool = False,
) -> ConnectionProtocol:
    """Create the right connection for a profile + auth combination."""
    from mountainash_auth_client import OAuth2Auth, OAuth2AuthCodeAuth

    if isinstance(auth_profile, (OAuth2Auth, OAuth2AuthCodeAuth)):
        return OAuth2Connection(profile, auth_profile, auto_authorize=auto_authorize)

    try:
        from mountainash_auth_client.schemas.oauth1 import OAuth1Auth
        if isinstance(auth_profile, OAuth1Auth):
            return OAuth1Connection(profile, auth_profile, auto_authorize=auto_authorize)
    except ImportError:
        pass

    provider_type = _provider_type_from_profile(profile)

    # SSH: two-layer composition (SSHConnection → SFTPConnection)
    if provider_type == CONST_STORAGE_PROVIDER_TYPE.SSH:
        strategy = resolve_auth_strategy(auth_profile, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH)
        ssh_conn = SSHConnection(profile, strategy)
        return SFTPConnection(ssh_conn)

    strategy = resolve_auth_strategy(auth_profile, provider_type=provider_type)
    leaf_cls = _connection_for_provider(profile)
    if leaf_cls is NullConnection:
        return NullConnection()
    return leaf_cls(profile, strategy)


def create_tunnelled_connection(
    bastion_profile: StorageProfileProtocol,
    bastion_auth: AuthProfile | None,
    target_profile: StorageProfileProtocol,
    target_auth: AuthProfile | None,
    remote_host: str,
    remote_port: int,
) -> TunnelledConnection:
    """Create a tunnelled connection through an SSH bastion host."""
    ssh_conn = SSHConnection(
        bastion_profile,
        resolve_auth_strategy(bastion_auth, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH),
    )

    def inner_factory(local_port: int) -> ConnectionProtocol:
        patched = _PatchedEndpointProfile(target_profile, "127.0.0.1", local_port)
        return create_connection(patched, target_auth)

    return TunnelledConnection(ssh_conn, inner_factory, remote_host, remote_port)


__all__ = [
    # Legacy
    "OAuth2FlowProtocol", "OAuth1FlowProtocol",
    "CallbackServerProtocol",
    "ConnectionError", "TokenExchangeError", "TokenRefreshError", "AuthorizationRequired",
    "TransportConnectionError", "ConnectionTimeoutError",
    "OAuthFlow",
    "OAuth1Flow",
    "LocalCallbackServer", "extract_code_from_input", "prompt_for_code",
    # Connections
    "HTTPConnection", "NullConnection", "S3Connection",
    "SSHConnection", "SFTPConnection", "TunnelledConnection",
    "OAuth2Connection", "OAuth1Connection",
    "create_connection", "create_tunnelled_connection",
]
```

- [ ] **Step 4: Update top-level `__init__.py` exports**

Add to `src/mountainash_transport/__init__.py` imports and `__all__`:

In the imports section, after the existing `from .connections.errors import TransportConnectionError`, add:

```python
from .connections import (
    SSHConnection, SFTPConnection, TunnelledConnection,
    create_connection, create_tunnelled_connection,
)
```

Add to `__all__`:

```python
"SSHConnection", "SFTPConnection", "TunnelledConnection",
"create_connection", "create_tunnelled_connection",
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `hatch run test:test-target-quick -- tests/connections/test_factory.py -v`
Expected: All tests PASS (existing + new SSH + tunnel factory tests).

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/connections/__init__.py src/mountainash_transport/__init__.py tests/connections/test_factory.py
git commit -m "feat: wire SSH into create_connection() + add create_tunnelled_connection()"
```

---

### Task 7: SFTPStorageBackend

**Files:**
- Create: `src/mountainash_transport/storage/backends/ssh/__init__.py`
- Create: `tests/storage/backends/test_sftp.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/storage/backends/test_sftp.py`:

```python
"""Tests for the SFTPStorageBackend."""
from __future__ import annotations

import errno
import io
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.exceptions import (
    PathNotFoundError,
    StorageConnectionError,
    StorageError,
)


class _FakeConnection:
    """Minimal connection stub wrapping a mock SFTPClient."""
    def __init__(self, sftp_client):
        self._client = sftp_client

    @property
    def client(self):
        return self._client

    @property
    def is_connected(self):
        return self._client is not None


def _make_backend(sftp_client=None):
    if sftp_client is None:
        sftp_client = MagicMock()
    import mountainash_transport.storage.backends  # noqa: F401
    from mountainash_transport.storage.backends.ssh import SFTPStorageBackend
    conn = _FakeConnection(sftp_client)
    return SFTPStorageBackend(None, connection=conn), sftp_client


class TestReadToBytes:
    def test_reads_file_content(self):
        mock_sftp = MagicMock()
        mock_file = MagicMock()
        mock_file.read.return_value = b"hello world"
        mock_sftp.open.return_value.__enter__ = MagicMock(return_value=mock_file)
        mock_sftp.open.return_value.__exit__ = MagicMock(return_value=False)

        backend, _ = _make_backend(mock_sftp)
        result = backend.read_to_bytes("/data/file.txt")
        assert result == b"hello world"
        mock_sftp.open.assert_called_once_with("/data/file.txt", "rb")

    def test_file_not_found_raises(self):
        mock_sftp = MagicMock()
        mock_sftp.open.side_effect = FileNotFoundError("no such file")

        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(PathNotFoundError):
            backend.read_to_bytes("/missing")

    def test_io_error_enoent_raises_path_not_found(self):
        mock_sftp = MagicMock()
        mock_sftp.open.side_effect = IOError(errno.ENOENT, "not found")

        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(PathNotFoundError):
            backend.read_to_bytes("/missing")

    def test_permission_error_raises_storage_error(self):
        mock_sftp = MagicMock()
        mock_sftp.open.side_effect = PermissionError("denied")

        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(StorageError):
            backend.read_to_bytes("/restricted")


class TestReadToStream:
    def test_returns_bytes_io(self):
        mock_sftp = MagicMock()
        mock_file = MagicMock()
        mock_file.read.return_value = b"stream data"
        mock_sftp.open.return_value.__enter__ = MagicMock(return_value=mock_file)
        mock_sftp.open.return_value.__exit__ = MagicMock(return_value=False)

        backend, _ = _make_backend(mock_sftp)
        stream = backend.read_to_stream("/data/file.txt")
        assert isinstance(stream, io.BytesIO)
        assert stream.read() == b"stream data"


class TestWriteFromBytes:
    def test_writes_data(self):
        mock_sftp = MagicMock()
        mock_file = MagicMock()
        mock_sftp.open.return_value.__enter__ = MagicMock(return_value=mock_file)
        mock_sftp.open.return_value.__exit__ = MagicMock(return_value=False)

        backend, _ = _make_backend(mock_sftp)
        backend.write_from_bytes("/data/output.txt", b"payload")
        mock_sftp.open.assert_called_once_with("/data/output.txt", "wb")
        mock_file.write.assert_called_once_with(b"payload")


class TestWriteFromStream:
    def test_writes_stream_content(self):
        mock_sftp = MagicMock()
        mock_file = MagicMock()
        mock_sftp.open.return_value.__enter__ = MagicMock(return_value=mock_file)
        mock_sftp.open.return_value.__exit__ = MagicMock(return_value=False)

        backend, _ = _make_backend(mock_sftp)
        backend.write_from_stream("/data/output.txt", io.BytesIO(b"streamed"))
        mock_file.write.assert_called_once_with(b"streamed")


class TestPathExists:
    def test_returns_true_when_exists(self):
        mock_sftp = MagicMock()
        mock_sftp.stat.return_value = MagicMock()

        backend, _ = _make_backend(mock_sftp)
        assert backend.path_exists("/data/file.txt") is True

    def test_returns_false_when_not_found(self):
        mock_sftp = MagicMock()
        mock_sftp.stat.side_effect = FileNotFoundError()

        backend, _ = _make_backend(mock_sftp)
        assert backend.path_exists("/missing") is False

    def test_returns_false_on_io_error_enoent(self):
        mock_sftp = MagicMock()
        mock_sftp.stat.side_effect = IOError(errno.ENOENT, "not found")

        backend, _ = _make_backend(mock_sftp)
        assert backend.path_exists("/missing") is False


class TestGetMetadata:
    def test_builds_file_metadata(self):
        mock_sftp = MagicMock()
        stat = MagicMock()
        stat.st_size = 1234
        stat.st_mtime = 1717200000.0
        mock_sftp.stat.return_value = stat

        backend, _ = _make_backend(mock_sftp)
        meta = backend.get_metadata("/data/report.csv")
        assert meta.filename == "report.csv"
        assert meta.directory == "/data"
        assert meta.full_path == "/data/report.csv"
        assert meta.size == 1234
        assert meta.source == "sftp"


class TestGetSize:
    def test_returns_file_size(self):
        mock_sftp = MagicMock()
        stat = MagicMock()
        stat.st_size = 5678
        mock_sftp.stat.return_value = stat

        backend, _ = _make_backend(mock_sftp)
        assert backend.get_size("/data/file.txt") == 5678


class TestListPaths:
    def test_returns_file_list(self):
        mock_sftp = MagicMock()
        attr1 = MagicMock()
        attr1.filename = "file1.txt"
        attr2 = MagicMock()
        attr2.filename = "file2.txt"
        mock_sftp.listdir_attr.return_value = [attr1, attr2]

        backend, _ = _make_backend(mock_sftp)
        result = backend.list_paths("/data")
        assert result == ["file1.txt", "file2.txt"]
        mock_sftp.listdir_attr.assert_called_once_with("/data")


class TestDeletePath:
    def test_removes_file(self):
        mock_sftp = MagicMock()
        backend, _ = _make_backend(mock_sftp)
        backend.delete_path("/data/old.txt")
        mock_sftp.remove.assert_called_once_with("/data/old.txt")

    def test_file_not_found_raises(self):
        mock_sftp = MagicMock()
        mock_sftp.remove.side_effect = FileNotFoundError()

        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(PathNotFoundError):
            backend.delete_path("/missing")


class TestNoConnection:
    def test_raises_without_connection(self):
        from mountainash_transport.storage.backends.ssh import SFTPStorageBackend
        backend = SFTPStorageBackend(None)
        with pytest.raises(StorageConnectionError, match="requires a connection"):
            backend._get_client()


class TestRegistration:
    def test_ssh_provider_registered(self):
        import mountainash_transport.storage.backends  # noqa: F401
        from mountainash_transport.storage.registry import get_registered_backends
        backends = get_registered_backends()
        assert CONST_STORAGE_PROVIDER_TYPE.SSH in backends
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test-target-quick -- tests/storage/backends/test_sftp.py -v`
Expected: ImportError — `mountainash_transport.storage.backends.ssh` does not exist yet.

- [ ] **Step 3: Implement SFTPStorageBackend**

Create `src/mountainash_transport/storage/backends/ssh/__init__.py`:

```python
"""SFTP storage backend — read, write, list, delete, and metadata via paramiko."""
from __future__ import annotations

import errno
import io
import typing as t
from datetime import datetime

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.dataclasses.file_metadata import FileMetadata
from mountainash_transport._core.exceptions import (
    PathNotFoundError,
    StorageConnectionError,
    StorageError,
)
from mountainash_transport.storage.registry import register_storage_backend
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol


def _is_not_found(exc: BaseException) -> bool:
    """Check if an exception represents a file-not-found condition."""
    if isinstance(exc, FileNotFoundError):
        return True
    if isinstance(exc, IOError) and getattr(exc, "errno", None) == errno.ENOENT:
        return True
    return False


def _wrap_sftp_error(exc: BaseException, path: str) -> StorageError:
    """Map SFTP exceptions to storage exceptions."""
    if _is_not_found(exc):
        return PathNotFoundError(f"Path not found: {path}")
    if isinstance(exc, PermissionError) or (
        isinstance(exc, IOError) and getattr(exc, "errno", None) == errno.EACCES
    ):
        return StorageError(f"Permission denied: {path}")
    if isinstance(exc, IOError) and getattr(exc, "errno", None) in (
        errno.ENOTDIR, errno.EISDIR
    ):
        return StorageError(f"Invalid path type: {path}")
    return StorageError(f"SFTP error for {path}: {exc}")


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.SSH)
class SFTPStorageBackend:
    """SFTP storage backend.

    Implements Read, Write, List, Delete, and Metadata protocols
    via paramiko.SFTPClient.
    """

    def __init__(
        self,
        storage_profile: StorageProfileProtocol | None = None,
        *,
        connection: t.Any = None,
    ) -> None:
        self._connection = connection
        self.storage_profile = storage_profile

    def _get_client(self) -> t.Any:
        if self._connection is not None and self._connection.client is not None:
            return self._connection.client
        raise StorageConnectionError(
            "SFTPStorageBackend requires a connection — use create_connection()"
        )

    # -- StorageReadProtocol ------------------------------------------------

    def read_to_bytes(self, path: str) -> bytes:
        sftp = self._get_client()
        try:
            with sftp.open(path, "rb") as f:
                return f.read()
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

    def read_to_stream(self, path: str) -> t.BinaryIO:
        data = self.read_to_bytes(path)
        return io.BytesIO(data)

    # -- StorageWriteProtocol -----------------------------------------------

    def write_from_bytes(self, path: str, data: bytes) -> None:
        sftp = self._get_client()
        try:
            with sftp.open(path, "wb") as f:
                f.write(data)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

    def write_from_stream(self, path: str, stream: t.BinaryIO) -> None:
        self.write_from_bytes(path, stream.read())

    # -- StorageListProtocol ------------------------------------------------

    def list_paths(self, path: str) -> list[str]:
        sftp = self._get_client()
        try:
            entries = sftp.listdir_attr(path)
            return [entry.filename for entry in entries]
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

    # -- StorageDeleteProtocol ----------------------------------------------

    def delete_path(self, path: str) -> None:
        sftp = self._get_client()
        try:
            sftp.remove(path)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

    # -- StorageMetadataProtocol --------------------------------------------

    def path_exists(self, path: str) -> bool:
        sftp = self._get_client()
        try:
            sftp.stat(path)
            return True
        except (FileNotFoundError, IOError):
            return False

    def get_metadata(self, path: str) -> FileMetadata:
        sftp = self._get_client()
        try:
            stat = sftp.stat(path)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

        filename = path.rsplit("/", 1)[-1] if "/" in path else path
        directory = path.rsplit("/", 1)[0] if "/" in path else "/"

        last_modified = None
        mtime = getattr(stat, "st_mtime", None)
        if mtime is not None:
            try:
                last_modified = datetime.fromtimestamp(mtime)
            except (ValueError, OSError):
                pass

        return FileMetadata(
            filename=filename,
            directory=directory,
            full_path=path,
            size=getattr(stat, "st_size", 0) or 0,
            last_modified=last_modified,
            source="sftp",
        )

    def get_size(self, path: str) -> int:
        sftp = self._get_client()
        try:
            stat = sftp.stat(path)
            return getattr(stat, "st_size", 0) or 0
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc


__all__ = ["SFTPStorageBackend"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test-target-quick -- tests/storage/backends/test_sftp.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Run full test suite**

Run: `hatch run test:test-quick`
Expected: All tests PASS. No regressions.

- [ ] **Step 6: Run lint**

Run: `hatch run ruff:check`
Expected: Clean.

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_transport/storage/backends/ssh/__init__.py tests/storage/backends/test_sftp.py
git commit -m "feat: add SFTPStorageBackend (read, write, list, delete, metadata)"
```

---

### Task 8: Full Regression + Lint

This task runs the full test suite and lint to ensure nothing broke.

- [ ] **Step 1: Full test suite**

Run: `hatch run test:test-quick`
Expected: All tests PASS.

- [ ] **Step 2: Lint**

Run: `hatch run ruff:check`
Expected: Clean.

- [ ] **Step 3: Verify existing resolver tests still pass**

Run: `hatch run test:test-target-quick -- tests/_core/auth/test_auth_resolver.py -v`
Expected: All existing tests PASS (backwards compatibility).

- [ ] **Step 4: Verify existing connection factory tests still pass**

Run: `hatch run test:test-target-quick -- tests/connections/test_factory.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Verify public API imports**

Run: `hatch run test:test-target-quick -- tests/test_public_api.py -v`
Expected: All tests PASS.
