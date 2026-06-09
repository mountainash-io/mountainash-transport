# OAuth Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract OAuth flow, connection mixin, and callback server modules from mountainash-auth-client into mountainash-transport's `connections/` directory, following protocol-first TDD.

**Architecture:** Copy-and-adapt extraction with security fixes. Protocol definitions come first, then all tests (red phase), then implementations until green. Four protocols (`OAuth2FlowProtocol`, `OAuth1FlowProtocol`, `CallbackServerProtocol`, `ConnectionMixinProtocol`) define the contracts. Errors gain a `ConnectionError` base class. Two security issues (CSRF state validation, PKCE verifier race) are fixed during extraction.

**Tech Stack:** Python 3.10+, httpx, pydantic, mountainash-settings (ProfileSpec, SecretsBackend), authlib (optional, OAuth1 only), typing_extensions (Self)

**Spec:** `docs/superpowers/specs/2026-06-09-oauth-extraction-design.md`

**Source (auth-client):** `/home/nathanielramm/git/mountainash-io/mountainash/mountainash-auth-client/src/mountainash_auth_client/`

---

## File Map

### New source files (connections/)

| File | Responsibility |
|------|---------------|
| `src/mountainash_transport/connections/__init__.py` | Public re-exports with `__all__` |
| `src/mountainash_transport/connections/protocols/__init__.py` | Protocol re-exports with `__all__` |
| `src/mountainash_transport/connections/protocols/prtcl_oauth2_flow.py` | `OAuth2FlowProtocol` |
| `src/mountainash_transport/connections/protocols/prtcl_oauth1_flow.py` | `OAuth1FlowProtocol` |
| `src/mountainash_transport/connections/protocols/prtcl_callback.py` | `CallbackServerProtocol` |
| `src/mountainash_transport/connections/protocols/prtcl_connection.py` | `ConnectionMixinProtocol` |
| `src/mountainash_transport/connections/errors.py` | `ConnectionError` base + 3 error classes |
| `src/mountainash_transport/connections/server/__init__.py` | Server re-exports |
| `src/mountainash_transport/connections/server/callback.py` | `LocalCallbackServer` |
| `src/mountainash_transport/connections/server/manual.py` | `extract_code_from_input`, `prompt_for_code` |
| `src/mountainash_transport/connections/oauth2/__init__.py` | OAuth2 re-exports |
| `src/mountainash_transport/connections/oauth2/flow.py` | `OAuthFlow` (with security fixes) |
| `src/mountainash_transport/connections/oauth2/mixin.py` | `OAuth2ConnectionMixin` |
| `src/mountainash_transport/connections/oauth1/__init__.py` | OAuth1 re-exports |
| `src/mountainash_transport/connections/oauth1/flow.py` | `OAuth1Flow` |
| `src/mountainash_transport/connections/oauth1/mixin.py` | `OAuth1ConnectionMixin` |

### New test files

| File | Responsibility |
|------|---------------|
| `tests/connections/__init__.py` | Package marker |
| `tests/connections/conftest.py` | `FakeSpec`, `InMemoryBackend`, fixtures |
| `tests/connections/test_protocol_shapes.py` | Conformance + alignment tests |
| `tests/connections/test_errors.py` | Error construction tests |
| `tests/connections/oauth2/__init__.py` | Package marker |
| `tests/connections/oauth2/test_flow.py` | OAuth2 flow behavioral tests |
| `tests/connections/oauth2/test_mixin.py` | OAuth2 mixin behavioral tests |
| `tests/connections/oauth1/__init__.py` | Package marker |
| `tests/connections/oauth1/test_flow.py` | OAuth1 flow behavioral tests |
| `tests/connections/oauth1/test_mixin.py` | OAuth1 mixin behavioral tests |
| `tests/connections/server/__init__.py` | Package marker |
| `tests/connections/server/test_server.py` | Callback server + manual entry tests |

### Modified files

| File | Change |
|------|--------|
| `pyproject.toml` | Add `mountainash-settings`, `mountainash-auth-client` deps; add `[oauth1]` extra |
| `hatch.toml` | Add `authlib` to test environments |

---

## Task 1: Update dependencies

**Files:**
- Modify: `pyproject.toml:25-31` (dependencies list)
- Modify: `pyproject.toml:34-62` (optional-dependencies)
- Modify: `hatch.toml:45-55` (test_github env), `hatch.toml:68-86` (test env)

- [ ] **Step 1: Add core dependencies to pyproject.toml**

In `pyproject.toml`, replace the dependencies list:

```toml
dependencies = [
    "pydantic==2.9.2",
    "pydantic-settings==2.6.1",
    "universal_pathlib==0.2.2",
    "boto3>=1.29.4,<=1.34.113",
    "httpx>=0.27",
    "mountainash-settings",
    "mountainash-auth-client",
]
```

- [ ] **Step 2: Add oauth1 optional extra to pyproject.toml**

After the existing `encryption` extra, add:

```toml
oauth1 = ["authlib>=1.3.0"]
```

Also add `"authlib>=1.3.0"` to the `all` extra list.

- [ ] **Step 3: Add authlib to test environments in hatch.toml**

In `[envs.test_github]` dependencies, add:

```toml
    "authlib>=1.3.0",
```

In `[envs.test]` dependencies, add the same:

```toml
    "authlib>=1.3.0",
```

- [ ] **Step 4: Verify the venv resolves**

Run: `hatch run test:test-target-quick -- --co -q tests/test_public_api.py 2>&1 | head -5`

Expected: test collection succeeds (existing tests still work).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml hatch.toml
git commit -m "chore: add mountainash-settings, auth-client, authlib deps for OAuth extraction"
```

---

## Task 2: Create connection protocols

**Files:**
- Create: `src/mountainash_transport/connections/protocols/__init__.py`
- Create: `src/mountainash_transport/connections/protocols/prtcl_oauth2_flow.py`
- Create: `src/mountainash_transport/connections/protocols/prtcl_oauth1_flow.py`
- Create: `src/mountainash_transport/connections/protocols/prtcl_callback.py`
- Create: `src/mountainash_transport/connections/protocols/prtcl_connection.py`

- [ ] **Step 1: Create protocols directory**

Run: `mkdir -p src/mountainash_transport/connections/protocols`

- [ ] **Step 2: Write prtcl_oauth2_flow.py**

```python
"""OAuth2 flow protocol — token exchange, refresh, PKCE."""
from __future__ import annotations

import typing as t

from typing import Protocol, runtime_checkable


@runtime_checkable
class OAuth2FlowProtocol(Protocol):
    """Interface for OAuth 2.0 Authorization Code flows."""

    def build_authorize_url(
        self,
        client_id: str,
        redirect_uri: str,
        scope: str | None = ...,
    ) -> tuple[str, str]: ...

    def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        client_id: str,
        client_secret: str,
        scope: str | None = ...,
        state: str | None = ...,
    ) -> dict[str, t.Any]: ...

    def refresh(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, t.Any]: ...

    @staticmethod
    def is_expired(
        token_expires_at: int | None,
        buffer_seconds: int = ...,
    ) -> bool: ...

    def authorize(
        self,
        client_id: str,
        client_secret: str,
        redirect_mode: str = ...,
        scope: str | None = ...,
    ) -> dict[str, t.Any]: ...
```

- [ ] **Step 3: Write prtcl_oauth1_flow.py**

```python
"""OAuth1 flow protocol — 3-legged authorization."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class OAuth1FlowProtocol(Protocol):
    """Interface for OAuth 1.0a 3-legged flows."""

    def build_authorize_url(self, oauth_token: str) -> str: ...

    def request_token(
        self,
        consumer_key: str,
        consumer_secret: str,
        callback_url: str = ...,
    ) -> dict[str, str]: ...

    def exchange_verifier(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        verifier: str,
    ) -> dict[str, str]: ...

    def authorize(
        self,
        consumer_key: str,
        consumer_secret: str,
        redirect_mode: str = ...,
    ) -> dict[str, str]: ...
```

- [ ] **Step 4: Write prtcl_callback.py**

```python
"""Callback server protocol — ephemeral OAuth redirect listener."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CallbackServerProtocol(Protocol):
    """Interface for OAuth callback servers."""

    @property
    def port(self) -> int: ...

    @property
    def redirect_uri(self) -> str: ...

    def wait_for_callback(self) -> dict[str, str]: ...
```

- [ ] **Step 5: Write prtcl_connection.py**

```python
"""Connection mixin protocol — OAuth connection lifecycle."""
from __future__ import annotations

import typing as t

from typing import Protocol, runtime_checkable

from typing_extensions import Self

if t.TYPE_CHECKING:
    import httpx


@runtime_checkable
class ConnectionMixinProtocol(Protocol):
    """Interface for OAuth connection mixins (token lifecycle + client)."""

    def connect(self, auth: t.Any, *, auto_authorize: bool = ...) -> Self: ...

    def disconnect(self) -> None: ...

    @property
    def client(self) -> httpx.Client | None: ...
```

Note: `__enter__`/`__exit__` are omitted from the protocol because `@runtime_checkable` cannot enforce dunder methods. Static type checkers still enforce them. The conformance tests verify them separately.

- [ ] **Step 6: Write protocols/__init__.py**

```python
from __future__ import annotations

from mountainash_transport.connections.protocols.prtcl_oauth2_flow import OAuth2FlowProtocol
from mountainash_transport.connections.protocols.prtcl_oauth1_flow import OAuth1FlowProtocol
from mountainash_transport.connections.protocols.prtcl_callback import CallbackServerProtocol
from mountainash_transport.connections.protocols.prtcl_connection import ConnectionMixinProtocol

__all__ = [
    "OAuth2FlowProtocol",
    "OAuth1FlowProtocol",
    "CallbackServerProtocol",
    "ConnectionMixinProtocol",
]
```

- [ ] **Step 7: Verify protocols import**

Run: `hatch run test:test-target-quick -- --co -q tests/test_public_api.py 2>&1 | head -5`

Expected: no import errors from the new protocols.

- [ ] **Step 8: Commit**

```bash
git add src/mountainash_transport/connections/protocols/
git commit -m "feat: define connection protocols (OAuth2Flow, OAuth1Flow, CallbackServer, ConnectionMixin)"
```

---

## Task 3: Create connection errors

**Files:**
- Create: `src/mountainash_transport/connections/errors.py`

- [ ] **Step 1: Write errors.py**

```python
"""Connection-specific exceptions."""
from __future__ import annotations


class ConnectionError(Exception):
    """Base exception for all connection operations."""


class TokenExchangeError(ConnectionError):
    """OAuth token endpoint returned an error during code exchange."""

    def __init__(self, *, url: str, status_code: int, body: str) -> None:
        self.url = url
        self.status_code = status_code
        self.body = body
        super().__init__(f"Token exchange failed: HTTP {status_code} POST {url} — {body[:200]}")


class TokenRefreshError(ConnectionError):
    """OAuth token refresh failed."""

    def __init__(self, *, url: str, status_code: int, body: str) -> None:
        self.url = url
        self.status_code = status_code
        self.body = body
        super().__init__(f"Token refresh failed: HTTP {status_code} POST {url} — {body[:200]}")


class AuthorizationRequired(ConnectionError):
    """No valid token exists and auto_authorize is False."""

    def __init__(self, *, provider: str, user: str) -> None:
        self.provider = provider
        self.user = user
        super().__init__(f"Authorization required for {provider}/{user}")
```

- [ ] **Step 2: Commit**

```bash
git add src/mountainash_transport/connections/errors.py
git commit -m "feat: add connection error hierarchy (ConnectionError base + 3 OAuth errors)"
```

---

## Task 4: Write protocol conformance tests (RED phase)

**Files:**
- Create: `tests/connections/__init__.py`
- Create: `tests/connections/test_protocol_shapes.py`

- [ ] **Step 1: Create test directory**

Run: `mkdir -p tests/connections`

- [ ] **Step 2: Create tests/connections/__init__.py**

Empty file.

- [ ] **Step 3: Write test_protocol_shapes.py**

```python
"""Protocol conformance tests for connection protocols."""
from __future__ import annotations

import typing as t

import pytest

from mountainash_transport.connections.protocols import (
    OAuth2FlowProtocol,
    OAuth1FlowProtocol,
    CallbackServerProtocol,
    ConnectionMixinProtocol,
)


# ---------------------------------------------------------------------------
# OAuth2FlowProtocol
# ---------------------------------------------------------------------------

class GoodOAuth2Flow:
    def build_authorize_url(self, client_id, redirect_uri, scope=None): ...
    def exchange_code(self, code, redirect_uri, client_id, client_secret, scope=None, state=None): ...
    def refresh(self, refresh_token, client_id, client_secret): ...
    @staticmethod
    def is_expired(token_expires_at, buffer_seconds=300): ...
    def authorize(self, client_id, client_secret, redirect_mode="local_server", scope=None): ...


class BadOAuth2Flow:
    def build_authorize_url(self, client_id, redirect_uri, scope=None): ...
    # missing exchange_code, refresh, is_expired, authorize


class TestOAuth2FlowProtocol:
    def test_positive_conformance(self):
        assert isinstance(GoodOAuth2Flow(), OAuth2FlowProtocol)

    def test_negative_conformance(self):
        assert not isinstance(BadOAuth2Flow(), OAuth2FlowProtocol)

    def test_empty_class_does_not_conform(self):
        assert not isinstance(object(), OAuth2FlowProtocol)

    def test_real_implementation_conforms(self):
        from mountainash_transport.connections.oauth2.flow import OAuthFlow

        class FakeSpec:
            metadata = {
                "authorize_url": "https://example.com/auth",
                "token_url": "https://example.com/token",
            }

        assert isinstance(OAuthFlow(FakeSpec()), OAuth2FlowProtocol)


# ---------------------------------------------------------------------------
# OAuth1FlowProtocol
# ---------------------------------------------------------------------------

class GoodOAuth1Flow:
    def build_authorize_url(self, oauth_token): ...
    def request_token(self, consumer_key, consumer_secret, callback_url="oob"): ...
    def exchange_verifier(self, consumer_key, consumer_secret, oauth_token, oauth_token_secret, verifier): ...
    def authorize(self, consumer_key, consumer_secret, redirect_mode="local_server"): ...


class BadOAuth1Flow:
    def build_authorize_url(self, oauth_token): ...
    # missing request_token, exchange_verifier, authorize


class TestOAuth1FlowProtocol:
    def test_positive_conformance(self):
        assert isinstance(GoodOAuth1Flow(), OAuth1FlowProtocol)

    def test_negative_conformance(self):
        assert not isinstance(BadOAuth1Flow(), OAuth1FlowProtocol)

    def test_empty_class_does_not_conform(self):
        assert not isinstance(object(), OAuth1FlowProtocol)

    def test_real_implementation_conforms(self):
        from mountainash_transport.connections.oauth1.flow import OAuth1Flow

        class FakeSpec:
            metadata = {
                "request_token_url": "https://example.com/oauth/request_token",
                "authorize_url": "https://example.com/oauth/authorize",
                "access_token_url": "https://example.com/oauth/access_token",
            }

        assert isinstance(OAuth1Flow(FakeSpec()), OAuth1FlowProtocol)


# ---------------------------------------------------------------------------
# CallbackServerProtocol
# ---------------------------------------------------------------------------

class GoodCallbackServer:
    @property
    def port(self): return 0
    @property
    def redirect_uri(self): return ""
    def wait_for_callback(self): ...


class BadCallbackServer:
    @property
    def port(self): return 0
    # missing redirect_uri, wait_for_callback


class TestCallbackServerProtocol:
    def test_positive_conformance(self):
        assert isinstance(GoodCallbackServer(), CallbackServerProtocol)

    def test_negative_conformance(self):
        assert not isinstance(BadCallbackServer(), CallbackServerProtocol)

    def test_empty_class_does_not_conform(self):
        assert not isinstance(object(), CallbackServerProtocol)

    def test_real_implementation_conforms(self):
        from mountainash_transport.connections.server.callback import LocalCallbackServer

        server = LocalCallbackServer(port=0, timeout=1)
        assert isinstance(server, CallbackServerProtocol)
        server._server.server_close()


# ---------------------------------------------------------------------------
# ConnectionMixinProtocol
# ---------------------------------------------------------------------------

class GoodConnectionMixin:
    def connect(self, auth, *, auto_authorize=False): ...
    def disconnect(self): ...
    @property
    def client(self): return None


class BadConnectionMixin:
    def connect(self, auth): ...
    # missing disconnect, client


class TestConnectionMixinProtocol:
    def test_positive_conformance(self):
        assert isinstance(GoodConnectionMixin(), ConnectionMixinProtocol)

    def test_negative_conformance(self):
        assert not isinstance(BadConnectionMixin(), ConnectionMixinProtocol)

    def test_empty_class_does_not_conform(self):
        assert not isinstance(object(), ConnectionMixinProtocol)


# ---------------------------------------------------------------------------
# Bidirectional alignment: no rogue public methods on implementations
# ---------------------------------------------------------------------------

def _public_methods(cls: type) -> set[str]:
    """Return public non-dunder method/property names from a class."""
    result = set()
    for name in dir(cls):
        if name.startswith("_"):
            continue
        attr = getattr(cls, name, None)
        if callable(attr) or isinstance(attr, property):
            result.add(name)
    return result


def _protocol_methods(protocol_cls: type) -> set[str]:
    """Return method names declared directly on a Protocol class."""
    result = set()
    for name, val in protocol_cls.__dict__.items():
        if name.startswith("_"):
            continue
        if callable(val) or isinstance(val, (property, staticmethod, classmethod)):
            result.add(name)
    return result


class TestBidirectionalAlignment:
    def test_oauth2_flow_no_rogue_methods(self):
        from mountainash_transport.connections.oauth2.flow import OAuthFlow

        protocol_names = _protocol_methods(OAuth2FlowProtocol)
        impl_names = _public_methods(OAuthFlow)
        rogue = impl_names - protocol_names
        assert not rogue, f"Rogue public methods on OAuthFlow: {rogue}"

    def test_oauth1_flow_no_rogue_methods(self):
        from mountainash_transport.connections.oauth1.flow import OAuth1Flow

        protocol_names = _protocol_methods(OAuth1FlowProtocol)
        impl_names = _public_methods(OAuth1Flow)
        rogue = impl_names - protocol_names
        assert not rogue, f"Rogue public methods on OAuth1Flow: {rogue}"

    def test_callback_server_no_rogue_methods(self):
        from mountainash_transport.connections.server.callback import LocalCallbackServer

        protocol_names = _protocol_methods(CallbackServerProtocol)
        impl_names = _public_methods(LocalCallbackServer)
        rogue = impl_names - protocol_names
        assert not rogue, f"Rogue public methods on LocalCallbackServer: {rogue}"
```

- [ ] **Step 4: Run tests to verify RED**

Run: `hatch run test:test-target-quick -- tests/connections/test_protocol_shapes.py -v 2>&1 | tail -20`

Expected: `test_real_implementation_conforms` tests and `TestBidirectionalAlignment` tests FAIL with `ModuleNotFoundError` (implementations don't exist yet). The dummy-class conformance tests (Good/Bad) should PASS since they only need the protocol definitions.

- [ ] **Step 5: Commit**

```bash
git add tests/connections/
git commit -m "test: add connection protocol conformance tests (RED — implementations pending)"
```

---

## Task 5: Write all behavioral tests (RED phase)

**Files:**
- Create: `tests/connections/conftest.py`
- Create: `tests/connections/test_errors.py`
- Create: `tests/connections/server/__init__.py`
- Create: `tests/connections/server/test_server.py`
- Create: `tests/connections/oauth2/__init__.py`
- Create: `tests/connections/oauth2/test_flow.py`
- Create: `tests/connections/oauth2/test_mixin.py`
- Create: `tests/connections/oauth1/__init__.py`
- Create: `tests/connections/oauth1/test_flow.py`
- Create: `tests/connections/oauth1/test_mixin.py`

- [ ] **Step 1: Create directories**

Run: `mkdir -p tests/connections/oauth2 tests/connections/oauth1 tests/connections/server`

- [ ] **Step 2: Create __init__.py files**

Create empty `__init__.py` in each: `tests/connections/oauth2/__init__.py`, `tests/connections/oauth1/__init__.py`, `tests/connections/server/__init__.py`.

- [ ] **Step 3: Write conftest.py**

```python
"""Shared fixtures for connection tests."""
from __future__ import annotations

import typing as t
from contextlib import contextmanager

import pytest

from mountainash_settings.secrets.registry import (
    clear_secrets_registry,
    register_secrets_backend,
)


class FakeOAuth2Spec:
    """Duck-types ProfileSpec for OAuth2 flow tests."""
    name = "testprovider"

    def __init__(self, metadata=None):
        self._metadata = metadata or {
            "authorize_url": "https://auth.example.com/authorize",
            "token_url": "https://auth.example.com/token",
        }

    @property
    def metadata(self):
        return self._metadata


class FakeOAuth1Spec:
    """Duck-types ProfileSpec for OAuth1 flow tests."""
    name = "testprovider_oauth1"

    def __init__(self, metadata=None):
        self._metadata = metadata or {
            "request_token_url": "https://auth.example.com/oauth/request_token",
            "authorize_url": "https://auth.example.com/oauth/authorize",
            "access_token_url": "https://auth.example.com/oauth/access_token",
        }

    @property
    def metadata(self):
        return self._metadata


class InMemoryBackend:
    """Minimal SecretsBackend for testing."""

    def __init__(self):
        self._store: dict[str, dict[str, t.Any]] = {}

    def get(self, key: str) -> dict[str, t.Any] | None:
        return self._store.get(key)

    def set(self, key: str, data: dict[str, t.Any]) -> None:
        self._store[key] = data

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    @contextmanager
    def transaction(self, key: str):
        yield


class FakeOAuth2Auth:
    """Duck-types OAuth2Auth for mixin tests."""
    CLIENT_ID = "cid"
    CLIENT_SECRET = property(lambda self: type("S", (), {"get_secret_value": lambda s: "csec"})())
    SCOPE = "read"
    SETTINGS_SOURCE_SECRETS_PROVIDER = "test_mem"

    def persist_key(self):
        return "test.oauth2"


class FakeOAuth1Auth:
    """Duck-types OAuth1Auth for mixin tests."""
    CONSUMER_KEY = "consumer_key"
    CONSUMER_SECRET = property(lambda self: type("S", (), {"get_secret_value": lambda s: "consumer_secret"})())
    SETTINGS_SOURCE_SECRETS_PROVIDER = "test_mem"

    def persist_key(self):
        return "test.oauth1"


@pytest.fixture
def fake_oauth2_spec():
    return FakeOAuth2Spec()


@pytest.fixture
def fake_oauth1_spec():
    return FakeOAuth1Spec()


@pytest.fixture(autouse=True)
def clean_secrets_registry():
    clear_secrets_registry()
    yield
    clear_secrets_registry()


@pytest.fixture
def memory_backend():
    b = InMemoryBackend()
    register_secrets_backend("test_mem", b)
    return b
```

- [ ] **Step 4: Write test_errors.py**

```python
"""Tests for connection error types."""
from __future__ import annotations

import pytest

from mountainash_transport.connections.errors import (
    AuthorizationRequired,
    ConnectionError,
    TokenExchangeError,
    TokenRefreshError,
)


class TestConnectionErrorBase:
    def test_all_errors_inherit_from_connection_error(self):
        assert issubclass(TokenExchangeError, ConnectionError)
        assert issubclass(TokenRefreshError, ConnectionError)
        assert issubclass(AuthorizationRequired, ConnectionError)

    def test_connection_error_is_exception(self):
        assert issubclass(ConnectionError, Exception)


class TestTokenExchangeError:
    def test_attributes_stored(self):
        err = TokenExchangeError(url="https://example.com/token", status_code=400, body='{"error":"invalid_grant"}')
        assert err.url == "https://example.com/token"
        assert err.status_code == 400
        assert err.body == '{"error":"invalid_grant"}'

    def test_str_contains_status_code(self):
        err = TokenExchangeError(url="https://example.com/token", status_code=401, body="Unauthorized")
        assert "401" in str(err)

    def test_str_contains_url(self):
        err = TokenExchangeError(url="https://example.com/token", status_code=400, body="bad")
        assert "https://example.com/token" in str(err)

    def test_body_truncated_in_str(self):
        long_body = "Z" * 500
        err = TokenExchangeError(url="https://auth.test/token", status_code=400, body=long_body)
        assert str(err).count("Z") <= 200

    def test_can_be_raised_and_caught(self):
        with pytest.raises(TokenExchangeError) as exc_info:
            raise TokenExchangeError(url="https://example.com/token", status_code=500, body="server error")
        assert exc_info.value.status_code == 500

    def test_catchable_as_connection_error(self):
        with pytest.raises(ConnectionError):
            raise TokenExchangeError(url="https://example.com/token", status_code=400, body="err")


class TestTokenRefreshError:
    def test_attributes_stored(self):
        err = TokenRefreshError(url="https://example.com/refresh", status_code=401, body="expired")
        assert err.url == "https://example.com/refresh"
        assert err.status_code == 401
        assert err.body == "expired"

    def test_str_contains_status_code(self):
        err = TokenRefreshError(url="https://example.com/refresh", status_code=403, body="forbidden")
        assert "403" in str(err)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(TokenRefreshError) as exc_info:
            raise TokenRefreshError(url="https://example.com/refresh", status_code=401, body="expired")
        assert exc_info.value.url == "https://example.com/refresh"


class TestAuthorizationRequired:
    def test_attributes_stored(self):
        err = AuthorizationRequired(provider="fitbit", user="alice")
        assert err.provider == "fitbit"
        assert err.user == "alice"

    def test_str_contains_provider(self):
        err = AuthorizationRequired(provider="whoop", user="bob")
        assert "whoop" in str(err)

    def test_str_contains_user(self):
        err = AuthorizationRequired(provider="fitbit", user="charlie")
        assert "charlie" in str(err)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(AuthorizationRequired) as exc_info:
            raise AuthorizationRequired(provider="oura", user="eve")
        assert exc_info.value.provider == "oura"
```

- [ ] **Step 5: Write server/test_server.py**

```python
"""Tests for callback server and manual auth utilities."""
from __future__ import annotations

import threading
import urllib.request

from mountainash_transport.connections.server.callback import LocalCallbackServer
from mountainash_transport.connections.server.manual import (
    extract_code_from_input,
    prompt_for_code,
)


class TestLocalCallbackServer:
    def test_port_is_assigned(self):
        server = LocalCallbackServer(port=0)
        assert server.port > 0
        server._server.server_close()

    def test_redirect_uri_format(self):
        server = LocalCallbackServer(port=0)
        assert server.redirect_uri == f"http://localhost:{server.port}/callback"
        server._server.server_close()

    def test_receives_callback_with_code(self):
        server = LocalCallbackServer(port=0, timeout=5)
        port = server.port

        def send_request():
            url = f"http://localhost:{port}/callback?code=auth_code_123&state=mystate"
            try:
                urllib.request.urlopen(url, timeout=3)
            except Exception:
                pass

        t = threading.Thread(target=send_request)
        t.start()
        params = server.wait_for_callback()
        t.join(timeout=5)

        assert params["code"] == "auth_code_123"
        assert params["state"] == "mystate"

    def test_callback_returns_html_response(self):
        server = LocalCallbackServer(port=0, timeout=5)
        port = server.port
        response_body = []

        def send_request():
            url = f"http://localhost:{port}/callback?code=xyz"
            try:
                resp = urllib.request.urlopen(url, timeout=3)
                response_body.append(resp.read())
            except Exception:
                pass

        t = threading.Thread(target=send_request)
        t.start()
        server.wait_for_callback()
        t.join(timeout=5)

        assert len(response_body) > 0
        assert b"Authorization complete" in response_body[0]


class TestExtractCodeFromInput:
    def test_bare_code(self):
        assert extract_code_from_input("myauthcode123") == {"code": "myauthcode123"}

    def test_bare_code_stripped(self):
        assert extract_code_from_input("  myauthcode123  ") == {"code": "myauthcode123"}

    def test_full_redirect_url_with_code_and_state(self):
        url = "http://localhost:8080/callback?code=abc123&state=xyz"
        result = extract_code_from_input(url)
        assert result["code"] == "abc123"
        assert result["state"] == "xyz"

    def test_full_redirect_url_code_only(self):
        url = "http://localhost:8080/callback?code=abc123"
        result = extract_code_from_input(url)
        assert result["code"] == "abc123"
        assert "state" not in result

    def test_https_redirect_url(self):
        url = "https://myapp.example.com/callback?code=def456&state=statetoken"
        result = extract_code_from_input(url)
        assert result["code"] == "def456"
        assert result["state"] == "statetoken"


class TestPromptForCode:
    def test_prompt_for_code_is_callable(self):
        assert callable(prompt_for_code)
```

- [ ] **Step 6: Write oauth2/test_flow.py**

```python
"""Tests for OAuthFlow (OAuth2 authorization code flow)."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from mountainash_transport.connections.errors import TokenExchangeError, TokenRefreshError
from mountainash_transport.connections.oauth2.flow import OAuthFlow


class TestBuildAuthorizeUrl:
    def test_returns_url_with_client_id(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        url, state = flow.build_authorize_url(
            client_id="my_client",
            redirect_uri="http://localhost:8080/callback",
        )
        assert "client_id=my_client" in url
        assert "https://auth.example.com/authorize" in url

    def test_returns_url_with_state(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        url, state = flow.build_authorize_url(
            client_id="my_client",
            redirect_uri="http://localhost:8080/callback",
        )
        assert state in url
        assert len(state) > 0

    def test_no_pkce_by_default(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        url, _ = flow.build_authorize_url(
            client_id="my_client",
            redirect_uri="http://localhost:8080/callback",
        )
        assert "code_challenge" not in url

    def test_pkce_adds_code_challenge_and_s256(self):
        from tests.connections.conftest import FakeOAuth2Spec

        spec = FakeOAuth2Spec(metadata={
            "authorize_url": "https://auth.example.com/authorize",
            "token_url": "https://auth.example.com/token",
            "use_pkce": True,
        })
        flow = OAuthFlow(spec)
        url, _ = flow.build_authorize_url(
            client_id="pkce_client",
            redirect_uri="http://localhost:8080/callback",
        )
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url

    def test_scope_included_when_provided(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        url, _ = flow.build_authorize_url(
            client_id="my_client",
            redirect_uri="http://localhost/cb",
            scope="read write",
        )
        assert "scope=" in url


class TestExchangeCode:
    def test_raises_token_exchange_error_on_http_error(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with patch("mountainash_transport.connections.oauth2.flow.httpx.Client") as MockClient:
            mock_client_instance = MockClient.return_value.__enter__.return_value
            mock_client_instance.post.side_effect = httpx.HTTPStatusError(
                "error", request=MagicMock(), response=mock_response
            )

            with pytest.raises(TokenExchangeError) as exc_info:
                flow.exchange_code(
                    code="authcode",
                    redirect_uri="http://localhost/cb",
                    client_id="cid",
                    client_secret="csec",
                )
            assert exc_info.value.status_code == 400

    def test_returns_token_dict_on_success(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "access_tok",
            "refresh_token": "refresh_tok",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("mountainash_transport.connections.oauth2.flow.httpx.Client") as MockClient:
            mock_client_instance = MockClient.return_value.__enter__.return_value
            mock_client_instance.post.return_value = mock_response

            result = flow.exchange_code(
                code="code123",
                redirect_uri="http://localhost/cb",
                client_id="cid",
                client_secret="csec",
            )
        assert result["access_token"] == "access_tok"
        assert result["refresh_token"] == "refresh_tok"
        assert result["token_expires_at"] is not None


class TestRefresh:
    def test_raises_token_refresh_error_on_http_error(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("mountainash_transport.connections.oauth2.flow.httpx.Client") as MockClient:
            mock_client_instance = MockClient.return_value.__enter__.return_value
            mock_client_instance.post.side_effect = httpx.HTTPStatusError(
                "error", request=MagicMock(), response=mock_response
            )

            with pytest.raises(TokenRefreshError) as exc_info:
                flow.refresh(
                    refresh_token="old_refresh",
                    client_id="cid",
                    client_secret="csec",
                )
            assert exc_info.value.status_code == 401


class TestIsExpired:
    def test_none_returns_false(self):
        assert OAuthFlow.is_expired(None) is False

    def test_past_timestamp_returns_true(self):
        assert OAuthFlow.is_expired(int(time.time()) - 1000) is True

    def test_far_future_returns_false(self):
        assert OAuthFlow.is_expired(int(time.time()) + 10000) is False

    def test_near_future_returns_true_due_to_buffer(self):
        assert OAuthFlow.is_expired(int(time.time()) + 100) is True


class TestCsrfStateValidation:
    """Security fix: state must be validated strictly."""

    def test_missing_state_in_callback_raises(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        url, state = flow.build_authorize_url("cid", "http://localhost/cb")
        with pytest.raises(ValueError, match="[Ss]tate"):
            flow._validate_callback_state({}, state)

    def test_mismatched_state_raises(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        url, state = flow.build_authorize_url("cid", "http://localhost/cb")
        with pytest.raises(ValueError, match="[Ss]tate"):
            flow._validate_callback_state({"state": "wrong"}, state)

    def test_correct_state_passes(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        url, state = flow.build_authorize_url("cid", "http://localhost/cb")
        flow._validate_callback_state({"state": state}, state)


class TestPkceVerifierByState:
    """Security fix: PKCE verifiers keyed by state token."""

    def test_sequential_authorize_exchange(self):
        from tests.connections.conftest import FakeOAuth2Spec

        spec = FakeOAuth2Spec(metadata={
            "authorize_url": "https://auth.example.com/authorize",
            "token_url": "https://auth.example.com/token",
            "use_pkce": True,
        })
        flow = OAuthFlow(spec)
        _, state1 = flow.build_authorize_url("cid", "http://localhost/cb")
        assert flow._pending_verifiers.get(state1) is not None

    def test_concurrent_authorize_urls_have_independent_verifiers(self):
        from tests.connections.conftest import FakeOAuth2Spec

        spec = FakeOAuth2Spec(metadata={
            "authorize_url": "https://auth.example.com/authorize",
            "token_url": "https://auth.example.com/token",
            "use_pkce": True,
        })
        flow = OAuthFlow(spec)
        _, state1 = flow.build_authorize_url("cid", "http://localhost/cb")
        _, state2 = flow.build_authorize_url("cid", "http://localhost/cb")
        assert state1 != state2
        assert flow._pending_verifiers[state1] != flow._pending_verifiers[state2]
```

- [ ] **Step 7: Write oauth2/test_mixin.py**

```python
"""Tests for OAuth2ConnectionMixin."""
from __future__ import annotations

import time

import pytest

from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.oauth2.mixin import OAuth2ConnectionMixin


class FakeProvider(OAuth2ConnectionMixin):
    _spec = type("S", (), {
        "name": "testprovider",
        "metadata": {
            "authorize_url": "https://auth.example.com/authorize",
            "token_url": "https://auth.example.com/token",
        },
    })()
    _base_url = "https://api.example.com"
    _client = None


class TestOAuth2MixinNoToken:
    def test_raises_authorization_required_when_no_token(self, memory_backend):
        from tests.connections.conftest import FakeOAuth2Auth

        provider = FakeProvider()
        with pytest.raises(AuthorizationRequired) as exc_info:
            provider.connect(FakeOAuth2Auth())
        assert exc_info.value.provider == "testprovider"


class TestOAuth2MixinWithToken:
    def test_connects_with_valid_stored_token(self, memory_backend):
        from tests.connections.conftest import FakeOAuth2Auth

        memory_backend.set("test.oauth2", {
            "access_token": "tok_abc",
            "refresh_token": "refresh_xyz",
            "token_expires_at": int(time.time()) + 3600,
        })
        provider = FakeProvider()
        result = provider.connect(FakeOAuth2Auth())
        assert result is provider
        provider.disconnect()

    def test_client_is_set_after_connect(self, memory_backend):
        from tests.connections.conftest import FakeOAuth2Auth

        memory_backend.set("test.oauth2", {
            "access_token": "tok_abc",
            "refresh_token": "refresh_xyz",
            "token_expires_at": int(time.time()) + 3600,
        })
        provider = FakeProvider()
        provider.connect(FakeOAuth2Auth())
        assert provider.client is not None
        provider.disconnect()

    def test_client_has_bearer_auth_header(self, memory_backend):
        from tests.connections.conftest import FakeOAuth2Auth

        memory_backend.set("test.oauth2", {
            "access_token": "tok_abc",
            "refresh_token": "refresh_xyz",
            "token_expires_at": int(time.time()) + 3600,
        })
        provider = FakeProvider()
        provider.connect(FakeOAuth2Auth())
        auth_header = provider.client.headers.get("authorization", "")
        assert "Bearer tok_abc" in auth_header
        provider.disconnect()


class TestOAuth2MixinExpiredToken:
    def test_raises_when_expired_no_refresh(self, memory_backend):
        from tests.connections.conftest import FakeOAuth2Auth

        memory_backend.set("test.oauth2", {
            "access_token": "old_tok",
            "refresh_token": None,
            "token_expires_at": int(time.time()) - 1000,
        })
        provider = FakeProvider()
        with pytest.raises(AuthorizationRequired):
            provider.connect(FakeOAuth2Auth())


class TestOAuth2MixinDisconnect:
    def test_disconnect_sets_client_to_none(self, memory_backend):
        from tests.connections.conftest import FakeOAuth2Auth

        memory_backend.set("test.oauth2", {
            "access_token": "tok",
            "refresh_token": "ref",
            "token_expires_at": int(time.time()) + 3600,
        })
        provider = FakeProvider()
        provider.connect(FakeOAuth2Auth())
        assert provider.client is not None
        provider.disconnect()
        assert provider.client is None

    def test_context_manager_calls_disconnect(self, memory_backend):
        from tests.connections.conftest import FakeOAuth2Auth

        memory_backend.set("test.oauth2", {
            "access_token": "tok",
            "refresh_token": "ref",
            "token_expires_at": int(time.time()) + 3600,
        })
        provider = FakeProvider()
        provider.connect(FakeOAuth2Auth())
        provider.__enter__()
        provider.__exit__(None, None, None)
        assert provider.client is None


class TestClientProperty:
    def test_client_none_before_connect(self):
        provider = FakeProvider()
        assert provider.client is None
```

- [ ] **Step 8: Write oauth1/test_flow.py**

```python
"""Tests for OAuth1Flow."""
from __future__ import annotations

import pytest

from mountainash_transport.connections.oauth1.flow import OAuth1Flow


class TestOAuth1FlowBuildAuthorizeUrl:
    def test_contains_oauth_token_param(self, fake_oauth1_spec):
        flow = OAuth1Flow(fake_oauth1_spec)
        url = flow.build_authorize_url("test_oauth_token_123")
        assert "oauth_token=test_oauth_token_123" in url

    def test_contains_authorize_base_url(self, fake_oauth1_spec):
        flow = OAuth1Flow(fake_oauth1_spec)
        url = flow.build_authorize_url("tok")
        assert "https://auth.example.com/oauth/authorize" in url

    def test_properties_read_from_metadata(self, fake_oauth1_spec):
        flow = OAuth1Flow(fake_oauth1_spec)
        assert flow.request_token_url == "https://auth.example.com/oauth/request_token"
        assert flow.authorize_url == "https://auth.example.com/oauth/authorize"
        assert flow.access_token_url == "https://auth.example.com/oauth/access_token"


class TestOAuth1FlowAuthlib:
    def test_request_token_requires_authlib(self, fake_oauth1_spec, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "authlib.integrations.httpx_client":
                raise ImportError("No module named 'authlib'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        flow = OAuth1Flow(fake_oauth1_spec)
        with pytest.raises(ImportError, match="authlib"):
            flow.request_token("consumer_key", "consumer_secret")

    def test_exchange_verifier_requires_authlib(self, fake_oauth1_spec, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "authlib.integrations.httpx_client":
                raise ImportError("No module named 'authlib'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        flow = OAuth1Flow(fake_oauth1_spec)
        with pytest.raises(ImportError, match="authlib"):
            flow.exchange_verifier("ck", "cs", "tok", "tok_sec", "verifier")
```

- [ ] **Step 9: Write oauth1/test_mixin.py**

```python
"""Tests for OAuth1ConnectionMixin."""
from __future__ import annotations

import pytest

from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.oauth1.mixin import OAuth1ConnectionMixin


class FakeOAuth1Provider(OAuth1ConnectionMixin):
    _spec = type("S", (), {
        "name": "testprovider_oauth1",
        "metadata": {
            "request_token_url": "https://auth.example.com/oauth/request_token",
            "authorize_url": "https://auth.example.com/oauth/authorize",
            "access_token_url": "https://auth.example.com/oauth/access_token",
        },
    })()
    _base_url = "https://api.example.com"
    _client = None


class TestOAuth1MixinNoToken:
    def test_raises_authorization_required_when_no_token(self, memory_backend):
        from tests.connections.conftest import FakeOAuth1Auth

        provider = FakeOAuth1Provider()
        with pytest.raises(AuthorizationRequired) as exc_info:
            provider.connect(FakeOAuth1Auth())
        assert exc_info.value.provider == "testprovider_oauth1"


class TestOAuth1MixinClientProperty:
    def test_client_none_before_connect(self):
        provider = FakeOAuth1Provider()
        assert provider.client is None


class TestOAuth1MixinDisconnect:
    def test_disconnect_sets_client_to_none(self):
        import httpx

        provider = FakeOAuth1Provider()
        provider._client = httpx.Client()
        assert provider.client is not None
        provider.disconnect()
        assert provider.client is None

    def test_context_manager_calls_disconnect(self):
        import httpx

        provider = FakeOAuth1Provider()
        provider._client = httpx.Client()
        provider.__enter__()
        provider.__exit__(None, None, None)
        assert provider.client is None


class TestOAuth1MixinAuthlibRequired:
    def test_build_client_requires_authlib(self, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "authlib.integrations.httpx_client":
                raise ImportError("No module named 'authlib'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        from tests.connections.conftest import FakeOAuth1Auth

        provider = FakeOAuth1Provider()
        with pytest.raises(ImportError, match="authlib"):
            provider._build_client(
                {"oauth_token": "tok", "oauth_token_secret": "sec"},
                FakeOAuth1Auth(),
            )
```

- [ ] **Step 10: Run tests to verify RED**

Run: `hatch run test:test-target-quick -- tests/connections/ -v --ignore=tests/connections/test_protocol_shapes.py 2>&1 | tail -30`

Expected: All tests FAIL with `ModuleNotFoundError` (implementations don't exist yet).

- [ ] **Step 11: Commit**

```bash
git add tests/connections/
git commit -m "test: add all connection behavioral tests (RED — implementations pending)"
```

---

## Task 6: Implement server modules (GREEN phase — leaf deps first)

**Files:**
- Create: `src/mountainash_transport/connections/server/__init__.py`
- Create: `src/mountainash_transport/connections/server/callback.py`
- Create: `src/mountainash_transport/connections/server/manual.py`

- [ ] **Step 1: Create server directory**

Run: `mkdir -p src/mountainash_transport/connections/server`

- [ ] **Step 2: Write server/callback.py**

Copy verbatim from auth-client — stdlib only, no import changes needed:

```python
from __future__ import annotations

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        self.server._callback_params = {k: v[0] for k, v in params.items()}
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body><h1>Authorization complete.</h1>"
                         b"<p>You can close this window.</p></body></html>")

    def log_message(self, format, *args) -> None:
        pass


class LocalCallbackServer:
    """Ephemeral HTTP server that captures a single OAuth callback."""

    def __init__(self, port: int = 0, timeout: int = 120) -> None:
        self._server = HTTPServer(("localhost", port), _CallbackHandler)
        self._server._callback_params = None
        self._timeout = timeout

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def redirect_uri(self) -> str:
        return f"http://localhost:{self.port}/callback"

    def wait_for_callback(self) -> dict[str, str]:
        """Block until a callback is received or timeout expires."""
        self._server.timeout = self._timeout
        self._server.handle_request()
        if self._server._callback_params is None:
            raise TimeoutError("No callback received within timeout")
        try:
            return self._server._callback_params
        finally:
            self._server.server_close()
```

- [ ] **Step 3: Write server/manual.py**

Copy verbatim — stdlib only:

```python
from __future__ import annotations

from urllib.parse import urlparse, parse_qs


def extract_code_from_input(user_input: str) -> dict[str, str]:
    """Parse authorization code from user input (URL or bare code)."""
    user_input = user_input.strip()
    if user_input.startswith("http"):
        parsed = urlparse(user_input)
        params = parse_qs(parsed.query)
        result: dict[str, str] = {}
        if "code" in params:
            result["code"] = params["code"][0]
        if "state" in params:
            result["state"] = params["state"][0]
        return result
    return {"code": user_input}


def prompt_for_code(authorize_url: str) -> dict[str, str]:
    """Print auth URL and prompt user for the callback URL or code."""
    print(f"\nOpen this URL in your browser to authorize:\n\n  {authorize_url}\n")
    user_input = input("Paste the redirect URL or authorization code: ")
    return extract_code_from_input(user_input)
```

- [ ] **Step 4: Write server/__init__.py**

```python
from __future__ import annotations

from mountainash_transport.connections.server.callback import LocalCallbackServer
from mountainash_transport.connections.server.manual import (
    extract_code_from_input,
    prompt_for_code,
)

__all__ = ["LocalCallbackServer", "extract_code_from_input", "prompt_for_code"]
```

- [ ] **Step 5: Run server tests**

Run: `hatch run test:test-target-quick -- tests/connections/server/ -v`

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/connections/server/
git commit -m "feat: add OAuth callback server and manual entry modules"
```

---

## Task 7: Implement OAuth2 flow (with security fixes)

**Files:**
- Create: `src/mountainash_transport/connections/oauth2/__init__.py`
- Create: `src/mountainash_transport/connections/oauth2/flow.py`

- [ ] **Step 1: Create oauth2 directory**

Run: `mkdir -p src/mountainash_transport/connections/oauth2`

- [ ] **Step 2: Write oauth2/flow.py**

Adapted from auth-client with import changes and security fixes:

```python
"""OAuth 2.0 Authorization Code flow with PKCE support."""
from __future__ import annotations

import hashlib
import base64
import secrets
import time
from typing import Literal
from urllib.parse import urlencode

import httpx

from mountainash_transport.connections.errors import TokenExchangeError, TokenRefreshError
from mountainash_transport.connections.server.callback import LocalCallbackServer
from mountainash_transport.connections.server.manual import prompt_for_code
from mountainash_settings import ProfileSpec


class OAuthFlow:
    """Runs OAuth 2.0 Authorization Code flow for an OAuth2 provider."""

    def __init__(self, spec: ProfileSpec) -> None:
        self._spec = spec
        self._metadata = spec.metadata
        self._pending_verifiers: dict[str, str] = {}
        self._last_state: str | None = None

    @property
    def authorize_url(self) -> str:
        return self._metadata["authorize_url"]

    @property
    def token_url(self) -> str:
        return self._metadata["token_url"]

    @property
    def use_pkce(self) -> bool:
        return self._metadata.get("use_pkce", False)

    @property
    def default_scope(self) -> str | None:
        return self._metadata.get("default_scope")

    def build_authorize_url(
        self,
        client_id: str,
        redirect_uri: str,
        scope: str | None = None,
    ) -> tuple[str, str]:
        """Build the authorization URL and generate state token."""
        state = secrets.token_urlsafe(32)
        self._last_state = state
        params: dict[str, str] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }
        effective_scope = scope or self.default_scope
        if effective_scope:
            params["scope"] = effective_scope

        if self.use_pkce:
            verifier = secrets.token_urlsafe(64)
            self._pending_verifiers[state] = verifier
            challenge = base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode()).digest()
            ).rstrip(b"=").decode()
            params["code_challenge"] = challenge
            params["code_challenge_method"] = "S256"

        url = f"{self.authorize_url}?{urlencode(params)}"
        return url, state

    def _validate_callback_state(
        self, params: dict[str, str], expected_state: str
    ) -> None:
        """Validate state parameter from OAuth callback. Raises ValueError on mismatch."""
        if params.get("state") != expected_state:
            raise ValueError("OAuth state mismatch — possible CSRF attack")

    def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        client_id: str,
        client_secret: str,
        scope: str | None = None,
        state: str | None = None,
    ) -> dict[str, str | int | None]:
        """Exchange authorization code for tokens. Returns flat token dict."""
        data: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        lookup_state = state or self._last_state
        if self.use_pkce and lookup_state and lookup_state in self._pending_verifiers:
            data["code_verifier"] = self._pending_verifiers.pop(lookup_state)

        with httpx.Client() as client:
            try:
                resp = client.post(self.token_url, data=data)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise TokenExchangeError(
                    url=self.token_url,
                    status_code=exc.response.status_code,
                    body=exc.response.text[:2000],
                ) from exc
            token_data = resp.json()

        expires_at: int | None = None
        if "expires_in" in token_data:
            expires_at = int(time.time()) + int(token_data["expires_in"])

        return {
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token", ""),
            "token_expires_at": expires_at,
            "scope": scope or self.default_scope,
        }

    def refresh(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, str | int | None]:
        """Refresh an expired access token. Returns flat token dict."""
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        with httpx.Client() as client:
            try:
                resp = client.post(self.token_url, data=data)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise TokenRefreshError(
                    url=self.token_url,
                    status_code=exc.response.status_code,
                    body=exc.response.text[:2000],
                ) from exc
            token_data = resp.json()

        expires_at: int | None = None
        if "expires_in" in token_data:
            expires_at = int(time.time()) + int(token_data["expires_in"])

        return {
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token", refresh_token),
            "token_expires_at": expires_at,
        }

    @staticmethod
    def is_expired(token_expires_at: int | None, buffer_seconds: int = 300) -> bool:
        """Check if the access token is expired or about to expire."""
        if token_expires_at is None:
            return False
        return time.time() >= (token_expires_at - buffer_seconds)

    def authorize(
        self,
        client_id: str,
        client_secret: str,
        redirect_mode: Literal["local_server", "manual"] = "local_server",
        scope: str | None = None,
    ) -> dict[str, str | int | None]:
        """Run the full authorization code flow end-to-end."""
        if redirect_mode == "local_server":
            port = self._metadata.get("callback_port", 0)
            server = LocalCallbackServer(port=port)
            redirect_uri = server.redirect_uri
        else:
            redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

        url, state = self.build_authorize_url(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
        )

        if redirect_mode == "local_server":
            import webbrowser
            webbrowser.open(url)
            params = server.wait_for_callback()
        else:
            params = prompt_for_code(url)

        self._validate_callback_state(params, state)

        return self.exchange_code(
            code=params["code"],
            redirect_uri=redirect_uri,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
            state=state,
        )
```

- [ ] **Step 3: Write oauth2/__init__.py**

```python
from __future__ import annotations

from mountainash_transport.connections.oauth2.flow import OAuthFlow

__all__ = ["OAuthFlow"]
```

(OAuth2ConnectionMixin will be added after Task 8.)

- [ ] **Step 4: Run OAuth2 flow tests**

Run: `hatch run test:test-target-quick -- tests/connections/oauth2/test_flow.py -v`

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/connections/oauth2/
git commit -m "feat: add OAuth2 flow with CSRF state fix and PKCE verifier-by-state fix"
```

---

## Task 8: Implement OAuth2 connection mixin

**Files:**
- Create: `src/mountainash_transport/connections/oauth2/mixin.py`
- Modify: `src/mountainash_transport/connections/oauth2/__init__.py`

- [ ] **Step 1: Write oauth2/mixin.py**

```python
"""OAuth2ConnectionMixin — reusable connect/refresh for OAuth2 providers."""
from __future__ import annotations

import typing as t
from typing import ClassVar

from typing_extensions import Self

import httpx

from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.oauth2.flow import OAuthFlow
from mountainash_settings import ProfileSpec
from mountainash_settings.secrets.registry import get_secrets_backend

if t.TYPE_CHECKING:
    from mountainash_auth_client.schemas.oauth2 import OAuth2Auth
    from mountainash_auth_client.schemas.oauth2_authcode import OAuth2AuthCodeAuth


class OAuth2ConnectionMixin:
    _spec: ClassVar[ProfileSpec]
    _base_url: ClassVar[str]
    _client: httpx.Client | None

    @property
    def client(self) -> httpx.Client | None:
        return self._client

    def connect(
        self,
        auth: OAuth2Auth | OAuth2AuthCodeAuth,
        *,
        auto_authorize: bool = False,
    ) -> Self:
        provider = self._spec.name
        flow = OAuthFlow(self._spec)

        backend = get_secrets_backend(auth.SETTINGS_SOURCE_SECRETS_PROVIDER)
        key = auth.persist_key()
        tokens = backend.get(key)

        access_token: str | None = None

        if tokens and not flow.is_expired(tokens.get("token_expires_at")):
            access_token = tokens["access_token"]
        elif tokens and tokens.get("refresh_token"):
            with backend.transaction(key):
                tokens = backend.get(key)
                if tokens and not flow.is_expired(tokens.get("token_expires_at")):
                    access_token = tokens["access_token"]
                else:
                    try:
                        new_tokens = flow.refresh(
                            refresh_token=tokens["refresh_token"],
                            client_id=auth.CLIENT_ID,
                            client_secret=auth.CLIENT_SECRET.get_secret_value(),
                        )
                        backend.set(key, new_tokens)
                        access_token = new_tokens["access_token"]
                    except Exception:
                        backend.delete(key)
                        if not auto_authorize:
                            raise AuthorizationRequired(provider=provider, user="default")

        if access_token is None:
            if auto_authorize:
                new_tokens = flow.authorize(
                    client_id=auth.CLIENT_ID,
                    client_secret=auth.CLIENT_SECRET.get_secret_value(),
                    scope=auth.SCOPE,
                )
                backend.set(key, new_tokens)
                access_token = new_tokens["access_token"]
            else:
                raise AuthorizationRequired(provider=provider, user="default")

        self._client = httpx.Client(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )
        return self

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: t.Any) -> None:
        self.disconnect()
```

- [ ] **Step 2: Update oauth2/__init__.py**

```python
from __future__ import annotations

from mountainash_transport.connections.oauth2.flow import OAuthFlow
from mountainash_transport.connections.oauth2.mixin import OAuth2ConnectionMixin

__all__ = ["OAuthFlow", "OAuth2ConnectionMixin"]
```

- [ ] **Step 3: Run OAuth2 mixin tests**

Run: `hatch run test:test-target-quick -- tests/connections/oauth2/test_mixin.py -v`

Expected: All PASS.

- [ ] **Step 4: Commit**

```bash
git add src/mountainash_transport/connections/oauth2/
git commit -m "feat: add OAuth2ConnectionMixin with disconnect() and token lifecycle"
```

---

## Task 9: Implement OAuth1 flow

**Files:**
- Create: `src/mountainash_transport/connections/oauth1/__init__.py`
- Create: `src/mountainash_transport/connections/oauth1/flow.py`

- [ ] **Step 1: Create oauth1 directory**

Run: `mkdir -p src/mountainash_transport/connections/oauth1`

- [ ] **Step 2: Write oauth1/flow.py**

```python
"""OAuth1 3-legged flow for providers like Garmin Health API."""
from __future__ import annotations

from typing import Literal
from urllib.parse import urlencode

import httpx

from mountainash_transport.connections.errors import TokenExchangeError
from mountainash_transport.connections.server.callback import LocalCallbackServer
from mountainash_transport.connections.server.manual import prompt_for_code
from mountainash_settings import ProfileSpec


class OAuth1Flow:
    """Runs OAuth 1.0a 3-legged authorization flow."""

    def __init__(self, spec: ProfileSpec) -> None:
        self._metadata = spec.metadata

    @property
    def request_token_url(self) -> str:
        return self._metadata["request_token_url"]

    @property
    def authorize_url(self) -> str:
        return self._metadata["authorize_url"]

    @property
    def access_token_url(self) -> str:
        return self._metadata["access_token_url"]

    def build_authorize_url(self, oauth_token: str) -> str:
        return f"{self.authorize_url}?{urlencode({'oauth_token': oauth_token})}"

    def request_token(
        self,
        consumer_key: str,
        consumer_secret: str,
        callback_url: str = "oob",
    ) -> dict[str, str]:
        try:
            from authlib.integrations.httpx_client import OAuth1Client
        except ImportError as exc:
            raise ImportError(
                "OAuth1 requires authlib: pip install mountainash-transport[oauth1]"
            ) from exc

        client = OAuth1Client(client_id=consumer_key, client_secret=consumer_secret)
        try:
            token = client.fetch_request_token(
                self.request_token_url, params={"oauth_callback": callback_url}
            )
        except httpx.HTTPStatusError as exc:
            raise TokenExchangeError(
                url=self.request_token_url,
                status_code=exc.response.status_code,
                body=exc.response.text[:2000],
            ) from exc
        return token

    def exchange_verifier(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        verifier: str,
    ) -> dict[str, str]:
        try:
            from authlib.integrations.httpx_client import OAuth1Client
        except ImportError as exc:
            raise ImportError(
                "OAuth1 requires authlib: pip install mountainash-transport[oauth1]"
            ) from exc

        client = OAuth1Client(
            client_id=consumer_key,
            client_secret=consumer_secret,
            token=oauth_token,
            token_secret=oauth_token_secret,
        )
        try:
            token = client.fetch_access_token(self.access_token_url, verifier=verifier)
        except httpx.HTTPStatusError as exc:
            raise TokenExchangeError(
                url=self.access_token_url,
                status_code=exc.response.status_code,
                body=exc.response.text[:2000],
            ) from exc
        return {
            "oauth_token": token["oauth_token"],
            "oauth_token_secret": token["oauth_token_secret"],
        }

    def authorize(
        self,
        consumer_key: str,
        consumer_secret: str,
        redirect_mode: Literal["local_server", "manual"] = "local_server",
    ) -> dict[str, str]:
        if redirect_mode == "local_server":
            server = LocalCallbackServer(port=0)
            callback_url = server.redirect_uri
        else:
            callback_url = "oob"

        request_token = self.request_token(consumer_key, consumer_secret, callback_url)
        url = self.build_authorize_url(request_token["oauth_token"])

        if redirect_mode == "local_server":
            import webbrowser
            webbrowser.open(url)
            params = server.wait_for_callback()
            verifier = params.get("oauth_verifier", "")
        else:
            params = prompt_for_code(url)
            verifier = params.get("oauth_verifier", params.get("code", ""))

        return self.exchange_verifier(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            oauth_token=request_token["oauth_token"],
            oauth_token_secret=request_token["oauth_token_secret"],
            verifier=verifier,
        )
```

- [ ] **Step 3: Write oauth1/__init__.py**

```python
from __future__ import annotations

from mountainash_transport.connections.oauth1.flow import OAuth1Flow

__all__ = ["OAuth1Flow"]
```

- [ ] **Step 4: Run OAuth1 flow tests**

Run: `hatch run test:test-target-quick -- tests/connections/oauth1/test_flow.py -v`

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/connections/oauth1/
git commit -m "feat: add OAuth1 flow (3-legged authorization, authlib optional)"
```

---

## Task 10: Implement OAuth1 connection mixin

**Files:**
- Create: `src/mountainash_transport/connections/oauth1/mixin.py`
- Modify: `src/mountainash_transport/connections/oauth1/__init__.py`

- [ ] **Step 1: Write oauth1/mixin.py**

```python
"""OAuth1ConnectionMixin — connect/auth for OAuth1 providers."""
from __future__ import annotations

import typing as t
from typing import ClassVar

from typing_extensions import Self

import httpx

from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.oauth1.flow import OAuth1Flow
from mountainash_settings import ProfileSpec
from mountainash_settings.secrets.registry import get_secrets_backend

if t.TYPE_CHECKING:
    from mountainash_auth_client.schemas.oauth1 import OAuth1Auth


class OAuth1ConnectionMixin:
    _spec: ClassVar[ProfileSpec]
    _base_url: ClassVar[str]
    _client: httpx.Client | None

    @property
    def client(self) -> httpx.Client | None:
        return self._client

    def connect(
        self,
        auth: OAuth1Auth,
        *,
        auto_authorize: bool = False,
    ) -> Self:
        provider = self._spec.name

        backend = get_secrets_backend(auth.SETTINGS_SOURCE_SECRETS_PROVIDER)
        key = auth.persist_key()
        tokens = backend.get(key)

        if tokens and tokens.get("oauth_token"):
            self._build_client(tokens, auth)
            return self

        if auto_authorize:
            flow = OAuth1Flow(self._spec)
            new_tokens = flow.authorize(
                consumer_key=auth.CONSUMER_KEY,
                consumer_secret=auth.CONSUMER_SECRET.get_secret_value(),
            )
            backend.set(key, new_tokens)
            self._build_client(new_tokens, auth)
            return self

        raise AuthorizationRequired(provider=provider, user="default")

    def _build_client(self, tokens: dict[str, str], auth_settings: OAuth1Auth) -> None:
        try:
            from authlib.integrations.httpx_client import OAuth1Auth as AuthlibOAuth1Auth
        except ImportError as exc:
            raise ImportError(
                "OAuth1 requires authlib: pip install mountainash-transport[oauth1]"
            ) from exc

        self._client = httpx.Client(
            base_url=self._base_url,
            auth=AuthlibOAuth1Auth(
                client_id=auth_settings.CONSUMER_KEY,
                client_secret=auth_settings.CONSUMER_SECRET.get_secret_value(),
                token=tokens["oauth_token"],
                token_secret=tokens["oauth_token_secret"],
            ),
            timeout=30.0,
        )

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: t.Any) -> None:
        self.disconnect()
```

Note: The authlib import is renamed to `AuthlibOAuth1Auth` to avoid shadowing the `OAuth1Auth` schema type annotation.

- [ ] **Step 2: Update oauth1/__init__.py**

```python
from __future__ import annotations

from mountainash_transport.connections.oauth1.flow import OAuth1Flow
from mountainash_transport.connections.oauth1.mixin import OAuth1ConnectionMixin

__all__ = ["OAuth1Flow", "OAuth1ConnectionMixin"]
```

- [ ] **Step 3: Run OAuth1 mixin tests**

Run: `hatch run test:test-target-quick -- tests/connections/oauth1/test_mixin.py -v`

Expected: All PASS.

- [ ] **Step 4: Commit**

```bash
git add src/mountainash_transport/connections/oauth1/
git commit -m "feat: add OAuth1ConnectionMixin with client property and disconnect()"
```

---

## Task 11: Wire up connections/__init__.py and run full suite

**Files:**
- Modify: `src/mountainash_transport/connections/__init__.py`

- [ ] **Step 1: Write connections/__init__.py**

Replace the existing stub:

```python
"""Connection infrastructure — OAuth flows, callback servers, token lifecycle."""
from __future__ import annotations

__all__ = [
    "OAuth2FlowProtocol", "OAuth1FlowProtocol",
    "CallbackServerProtocol", "ConnectionMixinProtocol",
    "ConnectionError", "TokenExchangeError", "TokenRefreshError", "AuthorizationRequired",
    "OAuthFlow", "OAuth2ConnectionMixin",
    "OAuth1Flow", "OAuth1ConnectionMixin",
    "LocalCallbackServer", "extract_code_from_input", "prompt_for_code",
]

from .protocols import (
    OAuth2FlowProtocol, OAuth1FlowProtocol,
    CallbackServerProtocol, ConnectionMixinProtocol,
)
from .errors import ConnectionError, TokenExchangeError, TokenRefreshError, AuthorizationRequired
from .oauth2.flow import OAuthFlow
from .oauth2.mixin import OAuth2ConnectionMixin
from .oauth1.flow import OAuth1Flow
from .oauth1.mixin import OAuth1ConnectionMixin
from .server.callback import LocalCallbackServer
from .server.manual import extract_code_from_input, prompt_for_code
```

- [ ] **Step 2: Run ALL connection tests**

Run: `hatch run test:test-target-quick -- tests/connections/ -v`

Expected: All tests PASS.

- [ ] **Step 3: Run FULL test suite to check for regressions**

Run: `hatch run test:test-target-quick -- -v 2>&1 | tail -30`

Expected: All existing tests still pass. No regressions.

- [ ] **Step 4: Run linter**

Run: `hatch run ruff:check`

Expected: Clean.

- [ ] **Step 5: Verify public API**

Run: `hatch run test:test-target-quick -- -c "from mountainash_transport.connections import OAuthFlow, OAuth2ConnectionMixin, OAuth1Flow, OAuth1ConnectionMixin, LocalCallbackServer, OAuth2FlowProtocol, ConnectionError; print('OK')"`

Or simpler: `python -c "from mountainash_transport.connections import OAuthFlow, OAuth2ConnectionMixin, OAuth1Flow, OAuth1ConnectionMixin, LocalCallbackServer; print('All imports OK')"`

Expected: `All imports OK`

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/connections/__init__.py
git commit -m "feat: wire up connections/__init__.py with full public API re-exports"
```

---

## Task 12: Final verification and PR

- [ ] **Step 1: Run full test suite with coverage**

Run: `hatch run test:test`

Expected: All tests pass. Coverage report generated.

- [ ] **Step 2: Build the wheel**

Run: `hatch build`

Expected: Build succeeds.

- [ ] **Step 3: Create feature branch and PR**

The work should already be on a feature branch (e.g., `feature/oauth-extraction`). Push and create PR targeting `develop`:

```bash
git push -u origin feature/oauth-extraction
gh pr create --base develop --title "feat: extract OAuth flows from auth-client into connections/" --body "$(cat <<'EOF'
## Summary
- Populate `connections/` with OAuth2/OAuth1 flow, connection mixin, callback server, and manual entry modules
- Define 4 connection protocols (OAuth2FlowProtocol, OAuth1FlowProtocol, CallbackServerProtocol, ConnectionMixinProtocol)
- Add ConnectionError base exception hierarchy
- Fix CSRF state validation weakness (strict state check)
- Fix PKCE verifier overwrite race (verifiers keyed by state)
- Add `disconnect()` to both mixins, `client` property to OAuth1 mixin
- Add mountainash-settings, mountainash-auth-client as explicit deps; authlib as [oauth1] optional extra

## Test plan
- [ ] `hatch run test:test` — all tests pass (existing + new connection tests)
- [ ] `hatch run ruff:check` — lint clean
- [ ] `hatch build` — wheel builds
- [ ] Protocol conformance tests verify isinstance checks and bidirectional alignment
- [ ] Security fix tests verify strict state validation and PKCE verifier isolation

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Verify CI passes**

Check: `gh pr checks <PR_NUMBER>`

Expected: pytest, ruff, radon all green.
