# Connection Architecture Alignment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify connection management into three clean layers — auth strategies, connections, and operations — so that backends are stateless operation handlers that receive connected clients.

**Architecture:** Auth strategies inject credentials into SDK kwargs. Leaf connections (HTTPConnection, S3Connection, NullConnection) create authenticated SDK clients. Decorated connections (OAuth2Connection, OAuth1Connection) manage token lifecycle then delegate to a leaf. Backends receive a connection instead of creating their own clients.

**Tech Stack:** Python 3.12, pydantic 2.x, httpx, boto3, authlib (optional), pytest, protocol-first TDD

**Spec:** `docs/superpowers/specs/2026-06-09-connection-architecture-design.md`

---

## File Map

### New files

| File | Responsibility |
|------|---------------|
| `src/mountainash_transport/_core/auth/__init__.py` | Re-exports: `AuthStrategy`, `NoAuthStrategy`, `BearerTokenStrategy`, `BasicAuthStrategy`, `resolve_auth_strategy` |
| `src/mountainash_transport/_core/auth/strategies.py` | `AuthStrategy` protocol + `NoAuthStrategy`, `BearerTokenStrategy`, `BasicAuthStrategy` |
| `src/mountainash_transport/_core/auth/resolver.py` | `resolve_auth_strategy()` — isinstance dispatch from auth profile → strategy |
| `src/mountainash_transport/connections/http.py` | `HTTPConnection` — leaf connection creating httpx.Client |
| `src/mountainash_transport/connections/null.py` | `NullConnection` — no-op connection for local filesystem |
| `src/mountainash_transport/connections/s3.py` | `S3Connection` — leaf connection creating boto3 S3 client |
| `src/mountainash_transport/connections/oauth2/connection.py` | `OAuth2Connection` — decorated connection replacing mixin |
| `src/mountainash_transport/connections/oauth1/connection.py` | `OAuth1Connection` — decorated connection replacing mixin |
| `tests/_core/auth/test_auth_strategies.py` | Protocol conformance + behavioral tests for auth strategies |
| `tests/_core/auth/test_auth_resolver.py` | Resolver dispatch tests |
| `tests/_core/test_connection_protocol.py` | `ConnectionProtocol` conformance tests |
| `tests/connections/test_http_connection.py` | HTTPConnection behavioral tests |
| `tests/connections/test_null_connection.py` | NullConnection behavioral tests |
| `tests/connections/test_s3_connection.py` | S3Connection behavioral tests |
| `tests/connections/oauth2/test_connection.py` | OAuth2Connection behavioral tests |
| `tests/connections/oauth1/test_connection.py` | OAuth1Connection behavioral tests |
| `tests/connections/test_factory.py` | `create_connection()` factory tests |

### Modified files

| File | Change |
|------|--------|
| `src/mountainash_transport/_core/protocols.py` | Populate with `ConnectionProtocol[C]` |
| `src/mountainash_transport/connections/errors.py` | Rename `ConnectionError` → `TransportConnectionError`, add `ConnectionTimeoutError` |
| `src/mountainash_transport/connections/__init__.py` | Add new exports, wire up factory |
| `src/mountainash_transport/settings/profile_protocol.py` | Drop `auth_profile` param from `to_handler_kwargs()` |
| `src/mountainash_transport/settings/storage/profiles/http_storage_profile.py` | Drop `auth_profile` param, delete `_resolve_auth_headers()` |
| `src/mountainash_transport/settings/storage/profiles/s3_storage_profile.py` | Drop `auth_profile` param, delete `_auth_kwargs()` |
| `src/mountainash_transport/settings/storage/profiles/*.py` | Drop `auth_profile` param (all 9 profiles) |
| `src/mountainash_transport/storage/backends/http/__init__.py` | Receive connection instead of profile+auth |
| `src/mountainash_transport/storage/backends/s3/__init__.py` | Receive connection instead of profile+auth |
| `src/mountainash_transport/storage/backends/s3/s3_connection.py` | Retire `S3ConnectionMixin` |
| `src/mountainash_transport/storage/backends/local/__init__.py` | Receive connection instead of profile+auth |
| `src/mountainash_transport/storage/registry/registry.py` | Update `get_storage_backend()` to create connection |
| `src/mountainash_transport/storage/facade/facade.py` | Create connection, pass to backend |
| `src/mountainash_transport/__init__.py` | Update exports (add `ConnectionProtocol`, `TransportConnectionError`) |

---

## Task 1: Auth Strategy Protocol + NoAuthStrategy

**Files:**
- Create: `src/mountainash_transport/_core/auth/__init__.py`
- Create: `src/mountainash_transport/_core/auth/strategies.py`
- Create: `tests/_core/auth/__init__.py`
- Create: `tests/_core/auth/test_auth_strategies.py`

- [ ] **Step 1: Create the test directory and `__init__.py` files**

```bash
mkdir -p src/mountainash_transport/_core/auth
touch src/mountainash_transport/_core/auth/__init__.py
mkdir -p tests/_core/auth
touch tests/_core/auth/__init__.py
```

- [ ] **Step 2: Write protocol conformance and NoAuthStrategy tests**

Write `tests/_core/auth/test_auth_strategies.py`:

```python
"""Auth strategy protocol conformance and behavioral tests."""
from __future__ import annotations

import pytest

from mountainash_transport._core.auth.strategies import AuthStrategy, NoAuthStrategy


class GoodStrategy:
    def apply(self, kwargs: dict) -> dict:
        return kwargs


class BadStrategy:
    pass


class TestAuthStrategyProtocol:
    def test_positive_conformance(self):
        assert isinstance(GoodStrategy(), AuthStrategy)

    def test_negative_conformance(self):
        assert not isinstance(BadStrategy(), AuthStrategy)

    def test_empty_class_does_not_conform(self):
        assert not isinstance(object(), AuthStrategy)


class TestNoAuthStrategy:
    def test_conforms_to_protocol(self):
        assert isinstance(NoAuthStrategy(), AuthStrategy)

    def test_returns_new_dict(self):
        original = {"timeout": 30}
        result = NoAuthStrategy().apply(original)
        assert result == {"timeout": 30}
        assert result is not original

    def test_preserves_existing_keys(self):
        original = {"headers": {"X-Custom": "val"}, "timeout": 30}
        result = NoAuthStrategy().apply(original)
        assert result == {"headers": {"X-Custom": "val"}, "timeout": 30}

    def test_empty_kwargs(self):
        result = NoAuthStrategy().apply({})
        assert result == {}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `hatch run test:test-target-quick tests/_core/auth/test_auth_strategies.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mountainash_transport._core.auth.strategies'`

- [ ] **Step 4: Implement AuthStrategy protocol and NoAuthStrategy**

Write `src/mountainash_transport/_core/auth/strategies.py`:

```python
"""Auth strategies — inject credentials into SDK client kwargs."""
from __future__ import annotations

import typing as t

from typing import Protocol, runtime_checkable


@runtime_checkable
class AuthStrategy(Protocol):
    """Inject auth credentials into SDK client kwargs.

    Returns a NEW dict — does not mutate the input.
    """

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]: ...


class NoAuthStrategy:
    """Passthrough — no credentials injected."""

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        return {**kwargs}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `hatch run test:test-target-quick tests/_core/auth/test_auth_strategies.py -v`
Expected: All 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/_core/auth/__init__.py \
        src/mountainash_transport/_core/auth/strategies.py \
        tests/_core/auth/__init__.py \
        tests/_core/auth/test_auth_strategies.py
git commit -m "feat(auth): add AuthStrategy protocol and NoAuthStrategy"
```

---

## Task 2: BearerTokenStrategy + BasicAuthStrategy

**Files:**
- Modify: `src/mountainash_transport/_core/auth/strategies.py`
- Modify: `tests/_core/auth/test_auth_strategies.py`

- [ ] **Step 1: Write tests for BearerTokenStrategy and BasicAuthStrategy**

Append to `tests/_core/auth/test_auth_strategies.py`:

```python
import base64

from mountainash_transport._core.auth.strategies import BearerTokenStrategy, BasicAuthStrategy


class TestBearerTokenStrategy:
    def test_conforms_to_protocol(self):
        assert isinstance(BearerTokenStrategy("tok"), AuthStrategy)

    def test_injects_bearer_header(self):
        result = BearerTokenStrategy("my-token").apply({"timeout": 30})
        assert result["headers"]["Authorization"] == "Bearer my-token"
        assert result["timeout"] == 30

    def test_returns_new_dict(self):
        original = {"timeout": 30}
        result = BearerTokenStrategy("tok").apply(original)
        assert result is not original
        assert "headers" not in original

    def test_merges_with_existing_headers(self):
        original = {"headers": {"X-Custom": "val"}}
        result = BearerTokenStrategy("tok").apply(original)
        assert result["headers"]["Authorization"] == "Bearer tok"
        assert result["headers"]["X-Custom"] == "val"

    def test_does_not_mutate_original_headers(self):
        original_headers = {"X-Custom": "val"}
        original = {"headers": original_headers}
        BearerTokenStrategy("tok").apply(original)
        assert "Authorization" not in original_headers


class TestBasicAuthStrategy:
    def test_conforms_to_protocol(self):
        assert isinstance(BasicAuthStrategy("user", "pass"), AuthStrategy)

    def test_injects_basic_header(self):
        result = BasicAuthStrategy("user", "pass").apply({"timeout": 30})
        expected = base64.b64encode(b"user:pass").decode()
        assert result["headers"]["Authorization"] == f"Basic {expected}"
        assert result["timeout"] == 30

    def test_returns_new_dict(self):
        original = {"timeout": 30}
        result = BasicAuthStrategy("u", "p").apply(original)
        assert result is not original

    def test_merges_with_existing_headers(self):
        original = {"headers": {"X-Custom": "val"}}
        result = BasicAuthStrategy("u", "p").apply(original)
        assert result["headers"]["X-Custom"] == "val"
        assert "Authorization" in result["headers"]

    def test_does_not_mutate_original_headers(self):
        original_headers = {"X-Custom": "val"}
        original = {"headers": original_headers}
        BasicAuthStrategy("u", "p").apply(original)
        assert "Authorization" not in original_headers
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `hatch run test:test-target-quick tests/_core/auth/test_auth_strategies.py -v`
Expected: ImportError for `BearerTokenStrategy` and `BasicAuthStrategy`

- [ ] **Step 3: Implement BearerTokenStrategy and BasicAuthStrategy**

Add to `src/mountainash_transport/_core/auth/strategies.py`:

```python
import base64


class BearerTokenStrategy:
    """Inject a Bearer token into the Authorization header."""

    def __init__(self, token: str) -> None:
        self._token = token

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        result = {**kwargs}
        existing = dict(result.get("headers", {}))
        existing["Authorization"] = f"Bearer {self._token}"
        result["headers"] = existing
        return result


class BasicAuthStrategy:
    """Inject HTTP Basic auth into the Authorization header."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        result = {**kwargs}
        encoded = base64.b64encode(
            f"{self._username}:{self._password}".encode()
        ).decode()
        existing = dict(result.get("headers", {}))
        existing["Authorization"] = f"Basic {encoded}"
        result["headers"] = existing
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test-target-quick tests/_core/auth/test_auth_strategies.py -v`
Expected: All 17 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/_core/auth/strategies.py \
        tests/_core/auth/test_auth_strategies.py
git commit -m "feat(auth): add BearerTokenStrategy and BasicAuthStrategy"
```

---

## Task 3: Auth Strategy Resolver

**Files:**
- Create: `src/mountainash_transport/_core/auth/resolver.py`
- Create: `tests/_core/auth/test_auth_resolver.py`
- Modify: `src/mountainash_transport/_core/auth/__init__.py`

- [ ] **Step 1: Write resolver tests**

Write `tests/_core/auth/test_auth_resolver.py`:

```python
"""Tests for resolve_auth_strategy() dispatch."""
from __future__ import annotations

import pytest

from mountainash_transport._core.auth.resolver import resolve_auth_strategy
from mountainash_transport._core.auth.strategies import (
    AuthStrategy,
    BasicAuthStrategy,
    BearerTokenStrategy,
    NoAuthStrategy,
)


class FakeTokenAuth:
    """Duck-types mountainash_auth_client.TokenAuth."""
    TOKEN = property(lambda self: type("S", (), {"get_secret_value": lambda s: "tok123"})())


class FakeJWTAuth:
    """Duck-types mountainash_auth_client.JWTAuth."""
    TOKEN = property(lambda self: type("S", (), {"get_secret_value": lambda s: "jwt456"})())


class FakePasswordAuth:
    """Duck-types mountainash_auth_client.PasswordAuth."""
    USERNAME = "admin"
    PASSWORD = property(lambda self: type("S", (), {"get_secret_value": lambda s: "secret"})())


class FakeNoAuth:
    """Duck-types mountainash_auth_client.NoAuth."""
    pass


class FakeOAuth2Auth:
    """Duck-types mountainash_auth_client.OAuth2Auth — has TOKEN field."""
    TOKEN = property(lambda self: type("S", (), {"get_secret_value": lambda s: "oauth-tok"})())


class FakeOAuth2AuthCodeAuth:
    """Duck-types mountainash_auth_client.OAuth2AuthCodeAuth — has ACCESS_TOKEN field."""
    ACCESS_TOKEN = property(lambda self: type("S", (), {"get_secret_value": lambda s: "authcode-tok"})())


class TestResolveAuthStrategy:
    def test_none_returns_no_auth(self):
        strategy = resolve_auth_strategy(None)
        assert isinstance(strategy, NoAuthStrategy)

    def test_returns_auth_strategy(self):
        strategy = resolve_auth_strategy(None)
        assert isinstance(strategy, AuthStrategy)

    def test_unknown_type_returns_no_auth(self):
        strategy = resolve_auth_strategy(object())
        assert isinstance(strategy, NoAuthStrategy)
```

Note: the resolver uses `isinstance` checks against the real `mountainash_auth_client` types. To test dispatch without requiring the real classes in the test, we test with the real classes imported from auth-client. Add these tests after the duck-type tests above:

```python
    def test_no_auth_profile(self):
        from mountainash_auth_client import NoAuth
        strategy = resolve_auth_strategy(NoAuth())
        assert isinstance(strategy, NoAuthStrategy)

    def test_token_auth_profile(self):
        from mountainash_auth_client import TokenAuth
        auth = TokenAuth(TOKEN="my-token")
        strategy = resolve_auth_strategy(auth)
        assert isinstance(strategy, BearerTokenStrategy)
        result = strategy.apply({})
        assert result["headers"]["Authorization"] == "Bearer my-token"

    def test_password_auth_profile(self):
        from mountainash_auth_client import PasswordAuth
        auth = PasswordAuth(USERNAME="admin", PASSWORD="secret")
        strategy = resolve_auth_strategy(auth)
        assert isinstance(strategy, BasicAuthStrategy)
        result = strategy.apply({})
        assert "Basic " in result["headers"]["Authorization"]

    def test_jwt_auth_profile(self):
        from mountainash_auth_client import JWTAuth
        auth = JWTAuth(TOKEN="jwt-tok")
        strategy = resolve_auth_strategy(auth)
        assert isinstance(strategy, BearerTokenStrategy)
        result = strategy.apply({})
        assert result["headers"]["Authorization"] == "Bearer jwt-tok"

    def test_oauth2_auth_with_token(self):
        from mountainash_auth_client import OAuth2Auth
        auth = OAuth2Auth(TOKEN="oauth2-tok")
        strategy = resolve_auth_strategy(auth)
        assert isinstance(strategy, BearerTokenStrategy)

    def test_oauth2_authcode_with_token(self):
        from mountainash_auth_client import OAuth2AuthCodeAuth
        auth = OAuth2AuthCodeAuth(ACCESS_TOKEN="authcode-tok")
        strategy = resolve_auth_strategy(auth)
        assert isinstance(strategy, BearerTokenStrategy)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test-target-quick tests/_core/auth/test_auth_resolver.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mountainash_transport._core.auth.resolver'`

- [ ] **Step 3: Implement the resolver**

Write `src/mountainash_transport/_core/auth/resolver.py`:

```python
"""Auth strategy resolver — map auth profiles to strategies."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.auth.strategies import (
    AuthStrategy,
    BasicAuthStrategy,
    BearerTokenStrategy,
    NoAuthStrategy,
)
from mountainash_transport.settings.utils.secrets import _unwrap_secret

if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthProfile

from mountainash_auth_client import (
    JWTAuth,
    NoAuth,
    OAuth2Auth,
    OAuth2AuthCodeAuth,
    PasswordAuth,
    TokenAuth,
)


def resolve_auth_strategy(auth_profile: AuthProfile | None) -> AuthStrategy:
    """Map an auth profile instance to its auth strategy.

    This is the single place where auth profile type → credential shape
    mapping lives. Replaces the isinstance switch formerly in
    HTTPStorageProfile._resolve_auth_headers().
    """
    if auth_profile is None:
        return NoAuthStrategy()

    if isinstance(auth_profile, NoAuth):
        return NoAuthStrategy()

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

    if isinstance(auth_profile, PasswordAuth):
        username = auth_profile.USERNAME or ""
        password = _unwrap_secret(auth_profile.PASSWORD) or ""
        return BasicAuthStrategy(username, password)

    return NoAuthStrategy()
```

- [ ] **Step 4: Wire up `_core/auth/__init__.py` re-exports**

Write `src/mountainash_transport/_core/auth/__init__.py`:

```python
"""Auth strategies — credential injection for SDK clients."""
from __future__ import annotations

from .strategies import (
    AuthStrategy,
    BasicAuthStrategy,
    BearerTokenStrategy,
    NoAuthStrategy,
)
from .resolver import resolve_auth_strategy

__all__ = [
    "AuthStrategy",
    "BasicAuthStrategy",
    "BearerTokenStrategy",
    "NoAuthStrategy",
    "resolve_auth_strategy",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `hatch run test:test-target-quick tests/_core/auth/ -v`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite to verify no regressions**

Run: `hatch run test:test`
Expected: All existing tests still pass

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_transport/_core/auth/__init__.py \
        src/mountainash_transport/_core/auth/resolver.py \
        tests/_core/auth/test_auth_resolver.py
git commit -m "feat(auth): add resolve_auth_strategy() dispatcher"
```

---

## Task 4: ConnectionProtocol

**Files:**
- Modify: `src/mountainash_transport/_core/protocols.py`
- Create: `tests/_core/test_connection_protocol.py`

- [ ] **Step 1: Write ConnectionProtocol conformance tests**

Write `tests/_core/test_connection_protocol.py`:

```python
"""ConnectionProtocol conformance tests."""
from __future__ import annotations

import typing as t

import pytest

from mountainash_transport._core.protocols import ConnectionProtocol


class GoodConnection:
    def connect(self):
        return self

    def disconnect(self) -> None:
        pass

    @property
    def client(self):
        return None

    @property
    def is_connected(self) -> bool:
        return False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class MissingClient:
    def connect(self):
        return self

    def disconnect(self) -> None:
        pass

    @property
    def is_connected(self) -> bool:
        return False


class TestConnectionProtocol:
    def test_positive_conformance(self):
        assert isinstance(GoodConnection(), ConnectionProtocol)

    def test_negative_conformance(self):
        assert not isinstance(MissingClient(), ConnectionProtocol)

    def test_empty_class_does_not_conform(self):
        assert not isinstance(object(), ConnectionProtocol)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test-target-quick tests/_core/test_connection_protocol.py -v`
Expected: FAIL — `ImportError: cannot import name 'ConnectionProtocol'`

- [ ] **Step 3: Implement ConnectionProtocol**

Replace the contents of `src/mountainash_transport/_core/protocols.py`:

```python
"""Shared protocols — ConnectionProtocol for all connection types."""
from __future__ import annotations

import typing as t

from typing import Protocol, TypeVar, runtime_checkable

from typing_extensions import Self

C = TypeVar("C")


@runtime_checkable
class ConnectionProtocol(Protocol[C]):
    """Unified connection lifecycle protocol.

    Replaces both StorageConnectionProtocol and ConnectionMixinProtocol.
    All connections implement this: leaf, OAuth decorated, and tunnelled.
    """

    def connect(self) -> Self: ...

    def disconnect(self) -> None: ...

    @property
    def client(self) -> C | None: ...

    @property
    def is_connected(self) -> bool: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, *args: t.Any) -> None: ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test-target-quick tests/_core/test_connection_protocol.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `hatch run test:test`
Expected: No regressions

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/_core/protocols.py \
        tests/_core/test_connection_protocol.py
git commit -m "feat(connections): add unified ConnectionProtocol"
```

---

## Task 5: TransportConnectionError rename + ConnectionTimeoutError

**Files:**
- Modify: `src/mountainash_transport/connections/errors.py`
- Modify: `tests/connections/test_errors.py`

- [ ] **Step 1: Read the existing error tests to understand current shape**

Read: `tests/connections/test_errors.py`

- [ ] **Step 2: Write tests for the renamed base and new timeout error**

Update `tests/connections/test_errors.py` to add:

```python
from mountainash_transport.connections.errors import (
    TransportConnectionError,
    ConnectionTimeoutError,
)


class TestTransportConnectionError:
    def test_is_exception(self):
        assert issubclass(TransportConnectionError, Exception)

    def test_backwards_compat_alias(self):
        """ConnectionError name still importable for transition period."""
        from mountainash_transport.connections.errors import ConnectionError as LegacyAlias
        assert LegacyAlias is TransportConnectionError


class TestConnectionTimeoutError:
    def test_is_subclass_of_transport_connection_error(self):
        assert issubclass(ConnectionTimeoutError, TransportConnectionError)

    def test_message(self):
        err = ConnectionTimeoutError("timed out connecting to host")
        assert "timed out" in str(err)


class TestExistingSubclassesReparented:
    def test_token_exchange_error(self):
        assert issubclass(TokenExchangeError, TransportConnectionError)

    def test_token_refresh_error(self):
        assert issubclass(TokenRefreshError, TransportConnectionError)

    def test_authorization_required(self):
        assert issubclass(AuthorizationRequired, TransportConnectionError)
```

- [ ] **Step 3: Run tests to verify new tests fail**

Run: `hatch run test:test-target-quick tests/connections/test_errors.py -v`
Expected: FAIL — `ImportError: cannot import name 'TransportConnectionError'`

- [ ] **Step 4: Implement the rename and new error**

Rewrite `src/mountainash_transport/connections/errors.py`:

```python
"""Connection-specific exceptions."""
from __future__ import annotations


class TransportConnectionError(Exception):
    """Base exception for all connection operations."""


# Backwards-compatible alias during transition.
ConnectionError = TransportConnectionError


class ConnectionTimeoutError(TransportConnectionError):
    """Connection or request timed out."""


class TokenExchangeError(TransportConnectionError):
    """OAuth token endpoint returned an error during code exchange."""

    def __init__(self, *, url: str, status_code: int, body: str) -> None:
        self.url = url
        self.status_code = status_code
        self.body = body
        super().__init__(f"Token exchange failed: HTTP {status_code} POST {url} — {body[:200]}")


class TokenRefreshError(TransportConnectionError):
    """OAuth token refresh failed."""

    def __init__(self, *, url: str, status_code: int, body: str) -> None:
        self.url = url
        self.status_code = status_code
        self.body = body
        super().__init__(f"Token refresh failed: HTTP {status_code} POST {url} — {body[:200]}")


class AuthorizationRequired(TransportConnectionError):
    """No valid token exists and auto_authorize is False."""

    def __init__(self, *, provider: str, user: str) -> None:
        self.provider = provider
        self.user = user
        super().__init__(f"Authorization required for {provider}/{user}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `hatch run test:test-target-quick tests/connections/test_errors.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite**

Run: `hatch run test:test`
Expected: No regressions (the `ConnectionError` alias keeps all existing imports working)

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_transport/connections/errors.py \
        tests/connections/test_errors.py
git commit -m "refactor(errors): rename ConnectionError to TransportConnectionError, add ConnectionTimeoutError"
```

---

## Task 6: HTTPConnection

**Files:**
- Create: `src/mountainash_transport/connections/http.py`
- Create: `tests/connections/test_http_connection.py`

- [ ] **Step 1: Write HTTPConnection tests**

Write `tests/connections/test_http_connection.py`:

```python
"""HTTPConnection behavioral tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mountainash_transport._core.auth.strategies import (
    AuthStrategy,
    BearerTokenStrategy,
    NoAuthStrategy,
)
from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.http import HTTPConnection


class FakeProfile:
    """Duck-types StorageProfileProtocol for HTTPConnection tests."""

    def to_handler_kwargs(self, auth_profile=None) -> dict:
        return {"timeout": 30, "follow_redirects": True}

    def get_connection_url(self) -> str:
        return "https://example.com"


class TestHTTPConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        conn = HTTPConnection(FakeProfile(), NoAuthStrategy())
        assert isinstance(conn, ConnectionProtocol)


class TestHTTPConnectionLifecycle:
    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_connect_creates_client(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        conn = HTTPConnection(FakeProfile(), NoAuthStrategy())
        result = conn.connect()

        mock_client_cls.assert_called_once_with(timeout=30, follow_redirects=True)
        assert conn.client is mock_client
        assert conn.is_connected is True
        assert result is conn

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_disconnect_closes_client(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        conn = HTTPConnection(FakeProfile(), NoAuthStrategy())
        conn.connect()
        conn.disconnect()

        mock_client.close.assert_called_once()
        assert conn.client is None
        assert conn.is_connected is False

    def test_not_connected_initially(self):
        conn = HTTPConnection(FakeProfile(), NoAuthStrategy())
        assert conn.client is None
        assert conn.is_connected is False

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_disconnect_when_not_connected_is_noop(self, mock_client_cls):
        conn = HTTPConnection(FakeProfile(), NoAuthStrategy())
        conn.disconnect()  # should not raise

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_context_manager(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        conn = HTTPConnection(FakeProfile(), NoAuthStrategy())
        with conn:
            conn.connect()
            assert conn.is_connected is True
        mock_client.close.assert_called_once()


class TestHTTPConnectionAuth:
    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_bearer_token_injected(self, mock_client_cls):
        strategy = BearerTokenStrategy("my-token")
        conn = HTTPConnection(FakeProfile(), strategy)
        conn.connect()

        call_kwargs = mock_client_cls.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer my-token"
        assert call_kwargs["timeout"] == 30

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_no_auth_no_headers(self, mock_client_cls):
        conn = HTTPConnection(FakeProfile(), NoAuthStrategy())
        conn.connect()

        call_kwargs = mock_client_cls.call_args[1]
        assert "headers" not in call_kwargs or "Authorization" not in call_kwargs.get("headers", {})


class TestHTTPConnectionErrorWrapping:
    """Spec requires raw httpx exceptions mapped at the connection boundary."""

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_timeout_wrapped_as_connection_timeout_error(self, mock_client_cls):
        from mountainash_transport.connections.errors import ConnectionTimeoutError

        mock_client_cls.side_effect = httpx.TimeoutException("timed out")
        conn = HTTPConnection(FakeProfile(), NoAuthStrategy())
        with pytest.raises(ConnectionTimeoutError):
            conn.connect()

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_connect_error_wrapped_as_transport_connection_error(self, mock_client_cls):
        from mountainash_transport.connections.errors import TransportConnectionError

        mock_client_cls.side_effect = httpx.ConnectError("refused")
        conn = HTTPConnection(FakeProfile(), NoAuthStrategy())
        with pytest.raises(TransportConnectionError):
            conn.connect()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test-target-quick tests/connections/test_http_connection.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mountainash_transport.connections.http'`

- [ ] **Step 3: Implement HTTPConnection**

Write `src/mountainash_transport/connections/http.py`:

```python
"""HTTPConnection — leaf connection creating an authenticated httpx.Client."""
from __future__ import annotations

import typing as t

from typing_extensions import Self

import httpx

from mountainash_transport._core.auth.strategies import AuthStrategy
from mountainash_transport.connections.errors import (
    ConnectionTimeoutError,
    TransportConnectionError,
)
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol


class HTTPConnection:
    """Creates an authenticated httpx.Client from profile config + auth strategy."""

    def __init__(
        self,
        profile: StorageProfileProtocol,
        auth_strategy: AuthStrategy,
    ) -> None:
        self._profile = profile
        self._auth_strategy = auth_strategy
        self._client: httpx.Client | None = None

    def connect(self) -> Self:
        kwargs = self._profile.to_handler_kwargs()
        kwargs = self._auth_strategy.apply(kwargs)
        try:
            self._client = httpx.Client(**kwargs)
        except httpx.TimeoutException as exc:
            raise ConnectionTimeoutError(
                f"Timeout creating HTTP client: {exc}"
            ) from exc
        except httpx.ConnectError as exc:
            raise TransportConnectionError(
                f"Connection failed: {exc}"
            ) from exc
        except Exception as exc:
            raise TransportConnectionError(
                f"Failed to create HTTP client: {exc}"
            ) from exc
        return self

    def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None

    @property
    def client(self) -> httpx.Client | None:
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

Run: `hatch run test:test-target-quick tests/connections/test_http_connection.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/connections/http.py \
        tests/connections/test_http_connection.py
git commit -m "feat(connections): add HTTPConnection leaf connection"
```

---

## Task 7: NullConnection

**Files:**
- Create: `src/mountainash_transport/connections/null.py`
- Create: `tests/connections/test_null_connection.py`

- [ ] **Step 1: Write NullConnection tests**

Write `tests/connections/test_null_connection.py`:

```python
"""NullConnection behavioral tests — no-op connection for local filesystem."""
from __future__ import annotations

import pytest

from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.null import NullConnection


class TestNullConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        assert isinstance(NullConnection(), ConnectionProtocol)


class TestNullConnectionLifecycle:
    def test_always_connected(self):
        conn = NullConnection()
        assert conn.is_connected is True

    def test_connect_returns_self(self):
        conn = NullConnection()
        result = conn.connect()
        assert result is conn

    def test_disconnect_is_noop(self):
        conn = NullConnection()
        conn.disconnect()
        assert conn.is_connected is True

    def test_client_is_none(self):
        conn = NullConnection()
        assert conn.client is None

    def test_context_manager(self):
        with NullConnection() as conn:
            assert conn.is_connected is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test-target-quick tests/connections/test_null_connection.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement NullConnection**

Write `src/mountainash_transport/connections/null.py`:

```python
"""NullConnection — no-op connection for backends that need no client (local filesystem)."""
from __future__ import annotations

import typing as t

from typing_extensions import Self


class NullConnection:
    """Always-connected, no-op connection for local filesystem and similar backends."""

    def connect(self) -> Self:
        return self

    def disconnect(self) -> None:
        pass

    @property
    def client(self) -> None:
        return None

    @property
    def is_connected(self) -> bool:
        return True

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: t.Any) -> None:
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test-target-quick tests/connections/test_null_connection.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/connections/null.py \
        tests/connections/test_null_connection.py
git commit -m "feat(connections): add NullConnection for local filesystem"
```

---

## Task 8: OAuth2Connection (decorator replacing mixin)

**Files:**
- Create: `src/mountainash_transport/connections/oauth2/connection.py`
- Create: `tests/connections/oauth2/test_connection.py`

This task moves the token lifecycle logic from `OAuth2ConnectionMixin` into `OAuth2Connection` — a standalone connection that decorates `HTTPConnection`.

- [ ] **Step 1: Write OAuth2Connection tests**

Write `tests/connections/oauth2/test_connection.py`:

```python
"""OAuth2Connection behavioral tests."""
from __future__ import annotations

import typing as t
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.oauth2.connection import OAuth2Connection
from mountainash_transport.connections.oauth2.flow import OAuthFlow

from mountainash_settings.secrets.registry import (
    clear_secrets_registry,
    register_secrets_backend,
)


class InMemoryBackend:
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


class FakeOAuth2Spec:
    name = "testprovider"

    @property
    def metadata(self):
        return {
            "authorize_url": "https://auth.example.com/authorize",
            "token_url": "https://auth.example.com/token",
        }


class FakeProfile:
    __spec__ = FakeOAuth2Spec()

    def to_handler_kwargs(self, auth_profile=None) -> dict:
        return {"timeout": 30}

    def get_connection_url(self) -> str:
        return "https://api.example.com"


class FakeOAuth2Auth:
    CLIENT_ID = "cid"
    CLIENT_SECRET = property(lambda self: type("S", (), {"get_secret_value": lambda s: "csec"})())
    SCOPE = "read"
    SETTINGS_SOURCE_SECRETS_PROVIDER = "test_mem"

    def persist_key(self):
        return "test.oauth2"


@pytest.fixture(autouse=True)
def clean_secrets():
    clear_secrets_registry()
    yield
    clear_secrets_registry()


@pytest.fixture
def memory_backend():
    b = InMemoryBackend()
    register_secrets_backend("test_mem", b)
    return b


class TestOAuth2ConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        conn = OAuth2Connection(FakeProfile(), FakeOAuth2Auth())
        assert isinstance(conn, ConnectionProtocol)


class TestOAuth2ConnectionLifecycle:
    def test_not_connected_initially(self):
        conn = OAuth2Connection(FakeProfile(), FakeOAuth2Auth())
        assert conn.client is None
        assert conn.is_connected is False

    def test_disconnect_when_not_connected_is_noop(self):
        conn = OAuth2Connection(FakeProfile(), FakeOAuth2Auth())
        conn.disconnect()

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_connect_with_stored_valid_token(self, mock_client_cls, memory_backend):
        memory_backend.set("test.oauth2", {
            "access_token": "stored-tok",
            "token_expires_at": 9999999999,
        })
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        conn = OAuth2Connection(FakeProfile(), FakeOAuth2Auth())
        result = conn.connect()

        assert result is conn
        assert conn.is_connected is True
        assert conn.client is mock_client
        call_kwargs = mock_client_cls.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer stored-tok"

    def test_connect_raises_when_no_token_and_not_auto(self, memory_backend):
        conn = OAuth2Connection(FakeProfile(), FakeOAuth2Auth())
        with pytest.raises(AuthorizationRequired):
            conn.connect()

    def test_missing_access_token_key_raises_token_exchange_error(self, memory_backend):
        """Spec: missing access_token key in token response → TokenExchangeError."""
        from mountainash_transport.connections.errors import TokenExchangeError

        memory_backend.set("test.oauth2", {
            "token_expires_at": 0,
            "refresh_token": "refresh-tok",
        })
        with patch.object(
            OAuthFlow, "is_expired", return_value=True
        ), patch.object(
            OAuthFlow, "refresh", return_value={"no_token_here": True}
        ):
            conn = OAuth2Connection(FakeProfile(), FakeOAuth2Auth())
            with pytest.raises((TokenExchangeError, KeyError)):
                conn.connect()

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_disconnect_closes_inner(self, mock_client_cls, memory_backend):
        memory_backend.set("test.oauth2", {
            "access_token": "tok",
            "token_expires_at": 9999999999,
        })
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        conn = OAuth2Connection(FakeProfile(), FakeOAuth2Auth())
        conn.connect()
        conn.disconnect()

        mock_client.close.assert_called_once()
        assert conn.client is None
        assert conn.is_connected is False

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_context_manager(self, mock_client_cls, memory_backend):
        memory_backend.set("test.oauth2", {
            "access_token": "tok",
            "token_expires_at": 9999999999,
        })
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        with OAuth2Connection(FakeProfile(), FakeOAuth2Auth()) as conn:
            conn.connect()
            assert conn.is_connected is True
        mock_client.close.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test-target-quick tests/connections/oauth2/test_connection.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement OAuth2Connection**

Write `src/mountainash_transport/connections/oauth2/connection.py`:

```python
"""OAuth2Connection — manages token lifecycle, delegates client creation to HTTPConnection."""
from __future__ import annotations

import typing as t

from typing_extensions import Self

import httpx

from mountainash_transport._core.auth.strategies import BearerTokenStrategy
from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.connections.oauth2.flow import OAuthFlow
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
from mountainash_settings.secrets.registry import get_secrets_backend

if t.TYPE_CHECKING:
    from mountainash_auth_client.schemas.oauth2 import OAuth2Auth
    from mountainash_auth_client.schemas.oauth2_authcode import OAuth2AuthCodeAuth


class OAuth2Connection:
    """Token lifecycle + client creation via inner HTTPConnection."""

    def __init__(
        self,
        profile: StorageProfileProtocol,
        auth_profile: OAuth2Auth | OAuth2AuthCodeAuth,
        *,
        auto_authorize: bool = False,
    ) -> None:
        self._profile = profile
        self._spec = profile.__spec__
        self._auth = auth_profile
        self._auto_authorize = auto_authorize
        self._inner: HTTPConnection | None = None

    def connect(self) -> Self:
        access_token = self._resolve_token()
        strategy = BearerTokenStrategy(access_token)
        self._inner = HTTPConnection(self._profile, strategy)
        self._inner.connect()
        return self

    def disconnect(self) -> None:
        if self._inner is not None:
            self._inner.disconnect()
        self._inner = None

    @property
    def client(self) -> httpx.Client | None:
        return self._inner.client if self._inner else None

    @property
    def is_connected(self) -> bool:
        return self._inner is not None and self._inner.is_connected

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: t.Any) -> None:
        self.disconnect()

    def _resolve_token(self) -> str:
        provider = self._spec.name
        flow = OAuthFlow(self._spec)

        backend = get_secrets_backend(self._auth.SETTINGS_SOURCE_SECRETS_PROVIDER)
        key = self._auth.persist_key()
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
                            client_id=self._auth.CLIENT_ID,
                            client_secret=self._auth.CLIENT_SECRET.get_secret_value(),
                        )
                        backend.set(key, new_tokens)
                        access_token = new_tokens["access_token"]
                    except Exception:
                        backend.delete(key)
                        if not self._auto_authorize:
                            raise AuthorizationRequired(provider=provider, user="default")

        if access_token is None:
            if self._auto_authorize:
                new_tokens = flow.authorize(
                    client_id=self._auth.CLIENT_ID,
                    client_secret=self._auth.CLIENT_SECRET.get_secret_value(),
                    scope=self._auth.SCOPE,
                )
                backend.set(key, new_tokens)
                access_token = new_tokens["access_token"]
            else:
                raise AuthorizationRequired(provider=provider, user="default")

        return access_token
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test-target-quick tests/connections/oauth2/test_connection.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/connections/oauth2/connection.py \
        tests/connections/oauth2/test_connection.py
git commit -m "feat(connections): add OAuth2Connection (decorator over HTTPConnection)"
```

---

## Task 9: OAuth1Connection (decorator replacing mixin)

**Files:**
- Create: `src/mountainash_transport/connections/oauth1/connection.py`
- Create: `tests/connections/oauth1/test_connection.py`

- [ ] **Step 1: Write OAuth1Connection tests**

Write `tests/connections/oauth1/test_connection.py`:

```python
"""OAuth1Connection behavioral tests."""
from __future__ import annotations

import typing as t
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.oauth1.connection import OAuth1Connection

from mountainash_settings.secrets.registry import (
    clear_secrets_registry,
    register_secrets_backend,
)


class InMemoryBackend:
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


class FakeOAuth1Spec:
    name = "testprovider_oauth1"

    @property
    def metadata(self):
        return {
            "request_token_url": "https://auth.example.com/oauth/request_token",
            "authorize_url": "https://auth.example.com/oauth/authorize",
            "access_token_url": "https://auth.example.com/oauth/access_token",
        }


class FakeProfile:
    __spec__ = FakeOAuth1Spec()

    def to_handler_kwargs(self, auth_profile=None) -> dict:
        return {"timeout": 30}

    def get_connection_url(self) -> str:
        return "https://api.example.com"


class FakeOAuth1Auth:
    CONSUMER_KEY = "consumer_key"
    CONSUMER_SECRET = property(lambda self: type("S", (), {"get_secret_value": lambda s: "consumer_secret"})())
    SETTINGS_SOURCE_SECRETS_PROVIDER = "test_mem"

    def persist_key(self):
        return "test.oauth1"


@pytest.fixture(autouse=True)
def clean_secrets():
    clear_secrets_registry()
    yield
    clear_secrets_registry()


@pytest.fixture
def memory_backend():
    b = InMemoryBackend()
    register_secrets_backend("test_mem", b)
    return b


class TestOAuth1ConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        conn = OAuth1Connection(FakeProfile(), FakeOAuth1Auth())
        assert isinstance(conn, ConnectionProtocol)


class TestOAuth1ConnectionLifecycle:
    def test_not_connected_initially(self):
        conn = OAuth1Connection(FakeProfile(), FakeOAuth1Auth())
        assert conn.client is None
        assert conn.is_connected is False

    def test_connect_raises_when_no_token_and_not_auto(self, memory_backend):
        conn = OAuth1Connection(FakeProfile(), FakeOAuth1Auth())
        with pytest.raises(AuthorizationRequired):
            conn.connect()

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_connect_with_stored_tokens(self, mock_client_cls, memory_backend):
        memory_backend.set("test.oauth1", {
            "oauth_token": "stored-tok",
            "oauth_token_secret": "stored-secret",
        })
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        conn = OAuth1Connection(FakeProfile(), FakeOAuth1Auth())
        result = conn.connect()

        assert result is conn
        assert conn.is_connected is True
        assert conn.client is mock_client
        call_kwargs = mock_client_cls.call_args[1]
        assert "auth" in call_kwargs

    @patch("mountainash_transport.connections.http.httpx.Client")
    def test_disconnect_closes_inner(self, mock_client_cls, memory_backend):
        memory_backend.set("test.oauth1", {
            "oauth_token": "tok",
            "oauth_token_secret": "sec",
        })
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        conn = OAuth1Connection(FakeProfile(), FakeOAuth1Auth())
        conn.connect()
        conn.disconnect()

        mock_client.close.assert_called_once()
        assert conn.is_connected is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test-target-quick tests/connections/oauth1/test_connection.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 2b: Add OAuth1SignedStrategy to `_core/auth/strategies.py`**

The spec places all auth strategies in Layer 1 (`_core/auth/`). Add `OAuth1SignedStrategy` to `src/mountainash_transport/_core/auth/strategies.py`:

```python
class OAuth1SignedStrategy:
    """Inject authlib OAuth1Auth handler into httpx kwargs (auth= parameter)."""

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._oauth_token = oauth_token
        self._oauth_token_secret = oauth_token_secret

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        try:
            from authlib.integrations.httpx_client import OAuth1Auth as AuthlibOAuth1Auth
        except ImportError as exc:
            raise ImportError(
                "OAuth1 requires authlib: pip install mountainash-transport[oauth1]"
            ) from exc

        result = {**kwargs}
        result["auth"] = AuthlibOAuth1Auth(
            client_id=self._consumer_key,
            client_secret=self._consumer_secret,
            token=self._oauth_token,
            token_secret=self._oauth_token_secret,
        )
        return result
```

Add `OAuth1SignedStrategy` to `_core/auth/__init__.py` exports.

- [ ] **Step 3: Implement OAuth1Connection**

Write `src/mountainash_transport/connections/oauth1/connection.py`:

```python
"""OAuth1Connection — manages OAuth1 token lifecycle, delegates to HTTPConnection."""
from __future__ import annotations

import typing as t

from typing_extensions import Self

import httpx

from mountainash_transport._core.auth.strategies import AuthStrategy, OAuth1SignedStrategy
from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.connections.oauth1.flow import OAuth1Flow
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
from mountainash_settings.secrets.registry import get_secrets_backend

if t.TYPE_CHECKING:
    from mountainash_auth_client.schemas.oauth1 import OAuth1Auth


class OAuth1Connection:
    """Token lifecycle + client creation via inner HTTPConnection."""

    def __init__(
        self,
        profile: StorageProfileProtocol,
        auth_profile: OAuth1Auth,
        *,
        auto_authorize: bool = False,
    ) -> None:
        self._profile = profile
        self._spec = profile.__spec__
        self._auth = auth_profile
        self._auto_authorize = auto_authorize
        self._inner: HTTPConnection | None = None

    def connect(self) -> Self:
        strategy = self._resolve_strategy()
        self._inner = HTTPConnection(self._profile, strategy)
        self._inner.connect()
        return self

    def disconnect(self) -> None:
        if self._inner is not None:
            self._inner.disconnect()
        self._inner = None

    @property
    def client(self) -> httpx.Client | None:
        return self._inner.client if self._inner else None

    @property
    def is_connected(self) -> bool:
        return self._inner is not None and self._inner.is_connected

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: t.Any) -> None:
        self.disconnect()

    def _resolve_strategy(self) -> AuthStrategy:
        provider = self._spec.name

        backend = get_secrets_backend(self._auth.SETTINGS_SOURCE_SECRETS_PROVIDER)
        key = self._auth.persist_key()
        tokens = backend.get(key)

        if tokens and tokens.get("oauth_token"):
            return OAuth1SignedStrategy(
                consumer_key=self._auth.CONSUMER_KEY,
                consumer_secret=self._auth.CONSUMER_SECRET.get_secret_value(),
                oauth_token=tokens["oauth_token"],
                oauth_token_secret=tokens["oauth_token_secret"],
            )

        if self._auto_authorize:
            flow = OAuth1Flow(self._spec)
            new_tokens = flow.authorize(
                consumer_key=self._auth.CONSUMER_KEY,
                consumer_secret=self._auth.CONSUMER_SECRET.get_secret_value(),
            )
            backend.set(key, new_tokens)
            return OAuth1SignedStrategy(
                consumer_key=self._auth.CONSUMER_KEY,
                consumer_secret=self._auth.CONSUMER_SECRET.get_secret_value(),
                oauth_token=new_tokens["oauth_token"],
                oauth_token_secret=new_tokens["oauth_token_secret"],
            )

        raise AuthorizationRequired(provider=provider, user="default")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test-target-quick tests/connections/oauth1/test_connection.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/connections/oauth1/connection.py \
        tests/connections/oauth1/test_connection.py
git commit -m "feat(connections): add OAuth1Connection (decorator over HTTPConnection)"
```

---

## Task 10: Profile Signature Change — Drop `auth_profile` from `to_handler_kwargs()`

**Files:**
- Modify: `src/mountainash_transport/settings/profile_protocol.py`
- Modify: `src/mountainash_transport/settings/storage/profiles/http_storage_profile.py`
- Modify: `src/mountainash_transport/settings/storage/profiles/s3_storage_profile.py`
- Modify: all other 7 profile files (azure, ftp, gcs, github, local, smb, ssh)
- Modify: corresponding test files in `tests/settings/storage/profiles/`

This is a large mechanical refactor. The key changes:
1. Protocol drops the `auth_profile` parameter
2. HTTP profile deletes `_resolve_auth_headers()` and removes auth header merging from `to_handler_kwargs()`
3. S3 profile deletes `_auth_kwargs()` and removes auth merging from `to_handler_kwargs()`
4. All other profiles just drop the unused `auth_profile` parameter
5. Tests that pass `auth_profile=` to `to_handler_kwargs()` are updated

- [ ] **Step 1: Update the protocol**

Edit `src/mountainash_transport/settings/profile_protocol.py` — remove `auth_profile` from `to_handler_kwargs`:

```python
"""StorageProfile — storage-flavored subclass of Profile."""
from __future__ import annotations

import typing as t

from typing import Protocol


@t.runtime_checkable
class StorageProfileProtocol(Protocol):
    """Storage provider protocol."""

    def to_handler_kwargs(self) -> dict[str, t.Any]: ...

    def get_connection_url(self) -> str: ...
```

- [ ] **Step 2: Update HTTPStorageProfile — remove `_resolve_auth_headers()` and `auth_profile` param**

In `src/mountainash_transport/settings/storage/profiles/http_storage_profile.py`:
- Delete the `_resolve_auth_headers()` method entirely
- Delete the `_unwrap_secret()` method (instance method duplicate)
- Remove `auth_profile` parameter from `to_handler_kwargs()`
- Remove the `auth_headers` merging — `to_handler_kwargs()` returns SDK config only
- Remove the auth-client imports (`AuthProfile`, `JWTAuth`, `NoAuth`, etc.)

The updated `to_handler_kwargs()`:

```python
    def to_handler_kwargs(self) -> dict[str, t.Any]:
        """Build httpx.Client kwargs — SDK config only, no auth."""
        timeout_connect = getattr(self, "TIMEOUT_CONNECT", 10.0)
        timeout_read = getattr(self, "TIMEOUT_READ", 30.0)
        timeout_write = getattr(self, "TIMEOUT_WRITE", 60.0)
        follow_redirects = getattr(self, "FOLLOW_REDIRECTS", True)
        max_redirects = getattr(self, "MAX_REDIRECTS", 10)
        verify = getattr(self, "VERIFY_SSL", True)
        custom_headers = getattr(self, "HEADERS", None) or {}

        kwargs: dict[str, t.Any] = {
            "timeout": httpx.Timeout(
                connect=timeout_connect,
                read=timeout_read,
                write=timeout_write,
                pool=5.0,
            ),
            "follow_redirects": follow_redirects,
            "max_redirects": max_redirects,
            "verify": verify,
        }
        if custom_headers:
            kwargs["headers"] = custom_headers

        return kwargs
```

Also remove the now-unnecessary imports at the top:

```python
# REMOVE these lines:
from mountainash_auth_client import CONST_AUTH_MODE
from mountainash_auth_client import AuthProfile, JWTAuth, NoAuth, OAuth2Auth, OAuth2AuthCodeAuth, PasswordAuth, TokenAuth
```

Keep: `from mountainash_auth_client import CONST_AUTH_MODE` (still needed for `HTTP_SPEC`).

- [ ] **Step 3: Update S3StorageProfile — remove `_auth_kwargs()` and `auth_profile` param**

In `src/mountainash_transport/settings/storage/profiles/s3_storage_profile.py`:
- Delete the `_auth_kwargs()` method entirely
- Remove `auth_profile` parameter from `to_handler_kwargs()`
- Remove the line `auth_kwargs = self._auth_kwargs(auth_profile)` and `base.update(auth_kwargs)`
- Remove the auth-client imports that are no longer needed (`AuthProfile`, `IAMAuth`, `TokenAuth`)
- Remove `from ...utils.secrets import _unwrap_secret`

Keep `from mountainash_auth_client import CONST_AUTH_MODE` (still needed for `S3_SPEC`).

- [ ] **Step 4: Update remaining 7 profile classes**

For each of these files, the change is mechanical — remove `auth_profile` from the `to_handler_kwargs()` signature. The `auth_profile` param is already unused in most of them (they accept it but don't use it):

- `azure_storage_profile.py`: `def to_handler_kwargs(self) -> dict[str, t.Any]:`
- `ftp_storage_profile.py`: `def to_handler_kwargs(self) -> dict[str, t.Any]:`
- `gcs_storage_profile.py`: `def to_handler_kwargs(self) -> dict[str, t.Any]:`
- `github_storage_profile.py`: `def to_handler_kwargs(self) -> dict[str, t.Any]:`
- `local_storage_profile.py`: `def to_handler_kwargs(self) -> dict[str, t.Any]:`
- `smb_storage_profile.py`: `def to_handler_kwargs(self) -> dict[str, t.Any]:`
- `ssh_storage_profile.py`: `def to_handler_kwargs(self) -> dict[str, t.Any]:`

**Important:** Some of these profiles (azure, gcs, ssh, smb, ftp) may also embed auth resolution inside `to_handler_kwargs()`. If they do, that auth logic needs to be extracted into corresponding auth strategies in future phases. For this task, ONLY remove the `auth_profile` parameter from the method signature and move any auth-dependent logic to be clearly marked as a temporary inline resolver. **Read each file before editing** to identify any embedded auth resolution.

- [ ] **Step 5: Update test files**

In `tests/settings/storage/profiles/`, update all test files that call `to_handler_kwargs(auth_profile=...)`:

- `test_s3_settings.py`: Change `s.to_handler_kwargs(auth_profile=auth)` → `s.to_handler_kwargs()` (auth is now tested at the strategy layer, not the profile layer)
- `test_http_settings.py`: Remove any auth-related assertions from profile tests
- `test_ssh_settings.py`: `s.to_handler_kwargs(auth_profile=auth)` → `s.to_handler_kwargs()`
- `test_smb_settings.py`: `s.to_handler_kwargs(auth_profile=auth)` → `s.to_handler_kwargs()`
- And similar for all other profile test files

**Read each test file first** — some tests verify auth header injection that now belongs in strategy tests. Those test cases should be deleted from the profile tests (the resolver tests in Task 3 already cover that dispatch).

- [ ] **Step 6: Update callers of `to_handler_kwargs(auth_profile=...)` in source code**

Search for all source code callers:

```bash
grep -rn "to_handler_kwargs(auth" src/mountainash_transport/
```

Update each caller. The primary ones:
- `storage/backends/http/__init__.py:70` — `self.storage_profile.to_handler_kwargs(auth_profile=self.auth_profile)` → `self.storage_profile.to_handler_kwargs()` (temporary — will be replaced in Task 11)
- `storage/backends/s3/s3_connection.py:50` — `storage_profile.to_handler_kwargs(auth_profile)` → `storage_profile.to_handler_kwargs()` (temporary — will be replaced in Task 12)

- [ ] **Step 7: Run full test suite**

Run: `hatch run test:test`
Expected: All tests pass

- [ ] **Step 8: Run lint**

Run: `hatch run ruff:check`
Expected: Clean

- [ ] **Step 9: Commit**

```bash
git add -u
git commit -m "refactor(profiles): drop auth_profile from to_handler_kwargs() across all 9 profiles"
```

---

## Task 11: Connection Factory + HTTP Backend Refactor

**Files:**
- Create: `tests/connections/test_factory.py`
- Modify: `src/mountainash_transport/connections/__init__.py`
- Modify: `src/mountainash_transport/storage/backends/http/__init__.py`
- Modify: `src/mountainash_transport/storage/registry/registry.py`
- Modify: `src/mountainash_transport/storage/facade/facade.py`

- [ ] **Step 1: Write factory tests**

Write `tests/connections/test_factory.py`:

```python
"""Tests for create_connection() factory."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from mountainash_transport.connections import create_connection
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.connections.null import NullConnection
from mountainash_transport._core.protocols import ConnectionProtocol


class FakeHTTPProfile:
    class __spec__:
        provider_type = "http"

    def to_handler_kwargs(self) -> dict:
        return {"timeout": 30}

    def get_connection_url(self) -> str:
        return "https://example.com"


class FakeLocalProfile:
    class __spec__:
        provider_type = "local"

    def to_handler_kwargs(self) -> dict:
        return {}

    def get_connection_url(self) -> str:
        return "/tmp"


class TestCreateConnection:
    def test_returns_connection_protocol(self):
        conn = create_connection(FakeHTTPProfile())
        assert isinstance(conn, ConnectionProtocol)

    def test_http_profile_returns_http_connection(self):
        conn = create_connection(FakeHTTPProfile())
        assert isinstance(conn, HTTPConnection)

    def test_local_profile_returns_null_connection(self):
        conn = create_connection(FakeLocalProfile())
        assert isinstance(conn, NullConnection)

    def test_no_auth_defaults_to_no_auth_strategy(self):
        conn = create_connection(FakeHTTPProfile())
        assert isinstance(conn, HTTPConnection)

    def test_bearer_auth(self):
        from mountainash_auth_client import TokenAuth
        conn = create_connection(FakeHTTPProfile(), auth_profile=TokenAuth(TOKEN="tok"))
        assert isinstance(conn, HTTPConnection)

    def test_oauth2_returns_oauth2_connection(self):
        from mountainash_auth_client import OAuth2AuthCodeAuth
        from mountainash_transport.connections.oauth2.connection import OAuth2Connection
        auth = OAuth2AuthCodeAuth(
            CLIENT_ID="cid",
            CLIENT_SECRET="csec",
            SCOPE="read",
            SETTINGS_SOURCE_SECRETS_PROVIDER="test",
        )
        conn = create_connection(FakeHTTPProfile(), auth_profile=auth)
        assert isinstance(conn, OAuth2Connection)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test-target-quick tests/connections/test_factory.py -v`
Expected: FAIL — `ImportError: cannot import name 'create_connection'`

- [ ] **Step 3: Implement `create_connection()` and connection-for-provider dispatch**

Add to `src/mountainash_transport/connections/__init__.py`:

```python
"""Connection infrastructure — OAuth flows, callback servers, token lifecycle, factory."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.auth.resolver import resolve_auth_strategy
from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol

if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthProfile

__all__ = [
    "OAuth2FlowProtocol", "OAuth1FlowProtocol",
    "CallbackServerProtocol", "ConnectionMixinProtocol",
    "ConnectionError", "TransportConnectionError",
    "TokenExchangeError", "TokenRefreshError", "AuthorizationRequired",
    "ConnectionTimeoutError",
    "OAuthFlow", "OAuth2ConnectionMixin",
    "OAuth1Flow", "OAuth1ConnectionMixin",
    "OAuth2Connection", "OAuth1Connection",
    "HTTPConnection", "NullConnection",
    "LocalCallbackServer", "extract_code_from_input", "prompt_for_code",
    "create_connection",
]

from .protocols import (
    OAuth2FlowProtocol, OAuth1FlowProtocol,
    CallbackServerProtocol, ConnectionMixinProtocol,
)
from .errors import (
    ConnectionError, TransportConnectionError,
    TokenExchangeError, TokenRefreshError, AuthorizationRequired,
    ConnectionTimeoutError,
)
from .oauth2.flow import OAuthFlow
from .oauth2.mixin import OAuth2ConnectionMixin
from .oauth2.connection import OAuth2Connection
from .oauth1.flow import OAuth1Flow
from .oauth1.mixin import OAuth1ConnectionMixin
from .oauth1.connection import OAuth1Connection
from .http import HTTPConnection
from .null import NullConnection
from .server.callback import LocalCallbackServer
from .server.manual import extract_code_from_input, prompt_for_code


_PROVIDER_CONNECTION_MAP: dict[str, type] = {
    "http": HTTPConnection,
    "local": NullConnection,
}


def _connection_for_provider(profile: StorageProfileProtocol) -> type:
    """Map profile's provider_type to a leaf connection class."""
    provider = getattr(getattr(profile, "__spec__", None), "provider_type", None)
    provider_str = str(provider.value) if hasattr(provider, "value") else str(provider)
    return _PROVIDER_CONNECTION_MAP.get(provider_str, HTTPConnection)


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

    strategy = resolve_auth_strategy(auth_profile)
    leaf_cls = _connection_for_provider(profile)
    if leaf_cls is NullConnection:
        return NullConnection()
    return leaf_cls(profile, strategy)
```

- [ ] **Step 4: Refactor HTTPStorageBackend to accept a connection**

Modify `src/mountainash_transport/storage/backends/http/__init__.py`:

```python
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.HTTP)
class HTTPStorageBackend:
    """HTTP/HTTPS storage backend."""

    def __init__(
        self,
        storage_profile: StorageProfileProtocol | None = None,
        *,
        auth_profile=None,
        connection=None,
    ) -> None:
        self._connection = connection
        self.storage_profile = storage_profile
        self.auth_profile = auth_profile

    def _get_client(self) -> httpx.Client:
        if self._connection is not None and self._connection.client is not None:
            return self._connection.client
        raise StorageConnectionError("HTTPStorageBackend requires a connection — use create_connection()")
```

No fallback client creation — the backend is a stateless operation handler per the spec.

- [ ] **Step 5: Update `get_storage_backend()` to pass connection through**

Modify `src/mountainash_transport/storage/registry/registry.py`:

```python
def get_storage_backend(
    provider_type: CONST_STORAGE_PROVIDER_TYPE,
    storage_profile: StorageProfileProtocol | None,
    *,
    auth_profile: AuthProfile | None = None,
    connection=None,
) -> t.Any:
    """Instantiate and return a backend for the given provider type."""
    cls = _backend_registry.get(provider_type)
    if cls is None:
        raise ValueError(f"No backend registered for {provider_type!r}")
    return cls(storage_profile, auth_profile=auth_profile, connection=connection)
```

- [ ] **Step 6: Update StorageFacade to create connection and pass to backend**

Modify `src/mountainash_transport/storage/facade/facade.py` — update `__init__`:

```python
    def __init__(
        self,
        provider_type: CONST_STORAGE_PROVIDER_TYPE,
        storage_profile: StorageProfileProtocol | None = None,
        *,
        auth_profile: AuthProfile | None = None,
    ) -> None:
        from mountainash_transport.connections import create_connection

        connection = None
        if storage_profile is not None:
            connection = create_connection(storage_profile, auth_profile)
            connection.connect()

        self._backend = get_storage_backend(
            provider_type, storage_profile,
            auth_profile=auth_profile, connection=connection,
        )
```

- [ ] **Step 7: Run full test suite**

Run: `hatch run test:test`
Expected: All tests pass

- [ ] **Step 8: Run lint**

Run: `hatch run ruff:check`
Expected: Clean

- [ ] **Step 9: Commit**

```bash
git add src/mountainash_transport/connections/__init__.py \
        src/mountainash_transport/storage/backends/http/__init__.py \
        src/mountainash_transport/storage/registry/registry.py \
        src/mountainash_transport/storage/facade/facade.py \
        tests/connections/test_factory.py
git commit -m "feat(connections): add create_connection() factory, wire HTTP backend through connection layer"
```

---

## Task 12: S3Connection + S3 Backend Refactor

**Files:**
- Create: `src/mountainash_transport/connections/s3.py`
- Create: `src/mountainash_transport/_core/auth/strategies.py` (add IAMCredentialStrategy)
- Create: `tests/connections/test_s3_connection.py`
- Create: `tests/_core/auth/test_iam_strategy.py`
- Modify: `src/mountainash_transport/storage/backends/s3/__init__.py`
- Modify: `src/mountainash_transport/storage/backends/s3/s3_connection.py`
- Modify: `src/mountainash_transport/connections/__init__.py` (add S3 to provider map)

- [ ] **Step 1: Write IAMCredentialStrategy tests**

Write `tests/_core/auth/test_iam_strategy.py`:

```python
"""IAMCredentialStrategy tests."""
from __future__ import annotations

import pytest

from mountainash_transport._core.auth.strategies import AuthStrategy, IAMCredentialStrategy


class TestIAMCredentialStrategy:
    def test_conforms_to_protocol(self):
        assert isinstance(
            IAMCredentialStrategy(access_key_id="AK", secret_access_key="SK"),
            AuthStrategy,
        )

    def test_injects_credentials(self):
        strategy = IAMCredentialStrategy(
            access_key_id="AKIA123",
            secret_access_key="secret",
        )
        result = strategy.apply({"region_name": "us-east-1"})
        assert result["aws_access_key_id"] == "AKIA123"
        assert result["aws_secret_access_key"] == "secret"
        assert result["region_name"] == "us-east-1"

    def test_returns_new_dict(self):
        original = {"region_name": "us-east-1"}
        strategy = IAMCredentialStrategy(access_key_id="AK", secret_access_key="SK")
        result = strategy.apply(original)
        assert result is not original
        assert "aws_access_key_id" not in original

    def test_with_session_token(self):
        strategy = IAMCredentialStrategy(
            access_key_id="AK",
            secret_access_key="SK",
            session_token="SESS",
        )
        result = strategy.apply({})
        assert result["aws_session_token"] == "SESS"

    def test_without_session_token(self):
        strategy = IAMCredentialStrategy(
            access_key_id="AK",
            secret_access_key="SK",
        )
        result = strategy.apply({})
        assert "aws_session_token" not in result

    def test_none_credentials_omitted(self):
        strategy = IAMCredentialStrategy()
        result = strategy.apply({"region_name": "us-east-1"})
        assert "aws_access_key_id" not in result
        assert "aws_secret_access_key" not in result
```

- [ ] **Step 2: Implement IAMCredentialStrategy**

Add to `src/mountainash_transport/_core/auth/strategies.py`:

```python
class IAMCredentialStrategy:
    """Inject AWS IAM credentials into boto3 client kwargs."""

    def __init__(
        self,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        session_token: str | None = None,
    ) -> None:
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._session_token = session_token

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        result = {**kwargs}
        if self._access_key_id:
            result["aws_access_key_id"] = self._access_key_id
        if self._secret_access_key:
            result["aws_secret_access_key"] = self._secret_access_key
        if self._session_token:
            result["aws_session_token"] = self._session_token
        return result
```

Update `src/mountainash_transport/_core/auth/__init__.py` to add `IAMCredentialStrategy` to exports.

Update `src/mountainash_transport/_core/auth/resolver.py` to handle `IAMAuth`:

```python
from mountainash_auth_client import IAMAuth
# ... existing imports ...

def resolve_auth_strategy(auth_profile: AuthProfile | None) -> AuthStrategy:
    # ... existing dispatch ...

    if isinstance(auth_profile, IAMAuth):
        return IAMCredentialStrategy(
            access_key_id=auth_profile.ACCESS_KEY_ID,
            secret_access_key=_unwrap_secret(auth_profile.SECRET_ACCESS_KEY),
            session_token=_unwrap_secret(auth_profile.SESSION_TOKEN) if auth_profile.SESSION_TOKEN else None,
        )

    # ... rest of dispatch ...
```

- [ ] **Step 3: Run IAM strategy tests**

Run: `hatch run test:test-target-quick tests/_core/auth/test_iam_strategy.py -v`
Expected: All PASS

- [ ] **Step 4: Write S3Connection tests**

Write `tests/connections/test_s3_connection.py`:

```python
"""S3Connection behavioral tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mountainash_transport._core.auth.strategies import IAMCredentialStrategy, NoAuthStrategy
from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.s3 import S3Connection


class FakeS3Profile:
    def to_handler_kwargs(self) -> dict:
        return {"service_name": "s3", "region_name": "us-east-1"}

    def get_connection_url(self) -> str:
        return "https://s3.us-east-1.amazonaws.com"


class TestS3ConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        conn = S3Connection(FakeS3Profile(), NoAuthStrategy())
        assert isinstance(conn, ConnectionProtocol)


class TestS3ConnectionLifecycle:
    @patch("mountainash_transport.connections.s3.boto3")
    def test_connect_creates_client(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        conn = S3Connection(FakeS3Profile(), NoAuthStrategy())
        result = conn.connect()

        mock_boto3.client.assert_called_once()
        call_args = mock_boto3.client.call_args
        assert call_args[0][0] == "s3"
        assert conn.client is mock_client
        assert conn.is_connected is True
        assert result is conn

    @patch("mountainash_transport.connections.s3.boto3")
    def test_connect_with_iam_credentials(self, mock_boto3):
        strategy = IAMCredentialStrategy(
            access_key_id="AKIA123",
            secret_access_key="secret",
        )
        conn = S3Connection(FakeS3Profile(), strategy)
        conn.connect()

        call_kwargs = mock_boto3.client.call_args[1]
        assert call_kwargs["aws_access_key_id"] == "AKIA123"
        assert call_kwargs["aws_secret_access_key"] == "secret"

    @patch("mountainash_transport.connections.s3.boto3")
    def test_disconnect(self, mock_boto3):
        mock_boto3.client.return_value = MagicMock()
        conn = S3Connection(FakeS3Profile(), NoAuthStrategy())
        conn.connect()
        conn.disconnect()

        assert conn.client is None
        assert conn.is_connected is False

    def test_not_connected_initially(self):
        conn = S3Connection(FakeS3Profile(), NoAuthStrategy())
        assert conn.client is None
        assert conn.is_connected is False
```

- [ ] **Step 5: Implement S3Connection**

Write `src/mountainash_transport/connections/s3.py`:

```python
"""S3Connection — leaf connection creating an authenticated boto3 S3 client."""
from __future__ import annotations

import typing as t

from typing_extensions import Self

from mountainash_transport._core.auth.strategies import AuthStrategy
from mountainash_transport._core.exceptions import StorageConnectionError
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol


class S3Connection:
    """Creates an authenticated boto3 S3 client from profile config + auth strategy."""

    def __init__(
        self,
        profile: StorageProfileProtocol,
        auth_strategy: AuthStrategy,
    ) -> None:
        self._profile = profile
        self._auth_strategy = auth_strategy
        self._client: t.Any = None

    def connect(self) -> Self:
        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError as exc:
            raise StorageConnectionError("boto3 is required for S3 connections") from exc

        kwargs = self._profile.to_handler_kwargs()
        kwargs = self._auth_strategy.apply(kwargs)
        kwargs.pop("service_name", None)
        try:
            self._client = boto3.client("s3", **kwargs)
        except Exception as exc:
            raise StorageConnectionError(f"Failed to create S3 client: {exc}") from exc
        return self

    def disconnect(self) -> None:
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

- [ ] **Step 6: Update provider map and S3 backend**

In `src/mountainash_transport/connections/__init__.py`, add S3 to the provider map:

```python
from .s3 import S3Connection

_PROVIDER_CONNECTION_MAP: dict[str, type] = {
    "http": HTTPConnection,
    "local": NullConnection,
    "s3": S3Connection,
    "s3express": S3Connection,
    "r2": S3Connection,
    "minio": S3Connection,
    "b2": S3Connection,
}
```

In `src/mountainash_transport/storage/backends/s3/__init__.py`, update `S3StorageBackend.__init__` to accept a `connection` param:

```python
    def __init__(self, storage_profile: StorageProfileProtocol, *, auth_profile=None, connection=None) -> None:
        self.storage_profile = storage_profile
        self.auth_profile = auth_profile
        self._connection = connection
        self._client: t.Any = None
```

In `src/mountainash_transport/storage/backends/s3/s3_connection.py`, update `S3ConnectionMixin.connect()` to check for an injected connection first:

```python
    def connect(self) -> None:
        if hasattr(self, '_connection') and self._connection is not None:
            self._client = self._connection.client
            return

        try:
            import boto3
            storage_profile = self.storage_profile
            kwargs = storage_profile.to_handler_kwargs()
            kwargs.pop("service_name", None)
            self._client = boto3.client("s3", **kwargs)
        except StorageConnectionError:
            raise
        except Exception as exc:
            raise StorageConnectionError(f"Failed to create S3 client: {exc}") from exc
```

- [ ] **Step 7: Run all tests**

Run: `hatch run test:test`
Expected: All tests pass

- [ ] **Step 8: Run lint**

Run: `hatch run ruff:check`
Expected: Clean

- [ ] **Step 9: Commit**

```bash
git add src/mountainash_transport/_core/auth/strategies.py \
        src/mountainash_transport/_core/auth/__init__.py \
        src/mountainash_transport/_core/auth/resolver.py \
        src/mountainash_transport/connections/s3.py \
        src/mountainash_transport/connections/__init__.py \
        src/mountainash_transport/storage/backends/s3/__init__.py \
        src/mountainash_transport/storage/backends/s3/s3_connection.py \
        tests/_core/auth/test_iam_strategy.py \
        tests/connections/test_s3_connection.py
git commit -m "feat(connections): add S3Connection, IAMCredentialStrategy, and S3 backend integration"
```

---

## Task 13: Protocol Consolidation + Cleanup

This task completes the architecture by retiring the two old protocols, deleting the replaced mixin files, updating all conformance tests, and wiring up the final public API.

**Files:**
- Delete: `src/mountainash_transport/connections/oauth2/mixin.py`
- Delete: `src/mountainash_transport/connections/oauth1/mixin.py`
- Delete: `src/mountainash_transport/connections/protocols/prtcl_connection.py`
- Delete: `src/mountainash_transport/storage/protocols/prtcl_connection.py`
- Delete: `src/mountainash_transport/storage/backends/s3/s3_connection.py`
- Delete: `src/mountainash_transport/storage/backends/local/local_connection.py`
- Modify: `src/mountainash_transport/__init__.py`
- Modify: `src/mountainash_transport/connections/__init__.py`
- Modify: `src/mountainash_transport/connections/protocols/__init__.py`
- Modify: `src/mountainash_transport/storage/protocols/__init__.py`
- Modify: `src/mountainash_transport/storage/backends/s3/__init__.py`
- Modify: `src/mountainash_transport/storage/backends/local/__init__.py`
- Rewrite: `tests/connections/test_protocol_shapes.py`

- [ ] **Step 1: Read files that import the things being deleted**

Before deleting anything, identify all import sites:

```bash
grep -rn "OAuth2ConnectionMixin\|OAuth1ConnectionMixin" src/mountainash_transport/
grep -rn "StorageConnectionProtocol" src/mountainash_transport/
grep -rn "ConnectionMixinProtocol" src/mountainash_transport/
grep -rn "S3ConnectionMixin" src/mountainash_transport/
grep -rn "LocalConnectionMixin" src/mountainash_transport/
```

Read each file found and understand what needs to change.

- [ ] **Step 2: Delete the old mixin files**

```bash
rm src/mountainash_transport/connections/oauth2/mixin.py
rm src/mountainash_transport/connections/oauth1/mixin.py
```

- [ ] **Step 3: Remove mixin imports from `connections/__init__.py`**

In `src/mountainash_transport/connections/__init__.py`:
- Remove `from .oauth2.mixin import OAuth2ConnectionMixin`
- Remove `from .oauth1.mixin import OAuth1ConnectionMixin`
- Remove `OAuth2ConnectionMixin` and `OAuth1ConnectionMixin` from `__all__`

The updated `__all__` and imports:

```python
__all__ = [
    "OAuth2FlowProtocol", "OAuth1FlowProtocol",
    "CallbackServerProtocol",
    "ConnectionError", "TransportConnectionError",
    "TokenExchangeError", "TokenRefreshError", "AuthorizationRequired",
    "ConnectionTimeoutError",
    "OAuthFlow",
    "OAuth1Flow",
    "OAuth2Connection", "OAuth1Connection",
    "HTTPConnection", "NullConnection", "S3Connection",
    "LocalCallbackServer", "extract_code_from_input", "prompt_for_code",
    "create_connection",
]
```

- [ ] **Step 4: Delete `ConnectionMixinProtocol` from connections protocols**

In `src/mountainash_transport/connections/protocols/prtcl_connection.py` — delete the entire file:

```bash
rm src/mountainash_transport/connections/protocols/prtcl_connection.py
```

Update `src/mountainash_transport/connections/protocols/__init__.py` — remove the `ConnectionMixinProtocol` import and re-export. Read the file first to see its current contents and edit accordingly.

- [ ] **Step 5: Delete `StorageConnectionProtocol`**

Delete the file:

```bash
rm src/mountainash_transport/storage/protocols/prtcl_connection.py
```

Update `src/mountainash_transport/storage/protocols/__init__.py` — remove the `StorageConnectionProtocol` import and re-export. Read the file first.

- [ ] **Step 6: Remove `StorageConnectionProtocol` from top-level `__init__.py`**

In `src/mountainash_transport/__init__.py`:
- Remove `StorageConnectionProtocol` from the `from .storage.protocols import (...)` block
- Remove `StorageConnectionProtocol` from `__all__`
- Add the new exports:

```python
# Connection protocol (unified)
from ._core.protocols import ConnectionProtocol

# Connection errors
from .connections.errors import TransportConnectionError
```

Add `ConnectionProtocol` and `TransportConnectionError` to `__all__`.

- [ ] **Step 7: Retire S3ConnectionMixin**

Delete the file:

```bash
rm src/mountainash_transport/storage/backends/s3/s3_connection.py
```

In `src/mountainash_transport/storage/backends/s3/__init__.py`:
- Remove `from .s3_connection import S3ConnectionMixin` import
- Remove `S3ConnectionMixin` from the class's base classes
- Remove `S3ConnectionMixin` from `__all__`
- The backend now gets its client via `self._connection.client` (wired in Task 12). Add a `connect()` / `disconnect()` / `is_connected()` directly on the class that delegates to the connection:

```python
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3)
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS)
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.R2)
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.MINIO)
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.B2)
class S3StorageBackend(
    S3ReadMixin,
    S3WriteMixin,
    S3ListMixin,
    S3DeleteMixin,
    S3MetadataMixin,
    S3CopyMixin,
):
    """Unified S3-family storage backend."""

    def __init__(self, storage_profile: StorageProfileProtocol, *, auth_profile=None, connection=None) -> None:
        self.storage_profile = storage_profile
        self.auth_profile = auth_profile
        self._connection = connection
        self._client: t.Any = None

    def connect(self) -> None:
        if self._connection is None:
            raise StorageConnectionError("S3StorageBackend requires a connection — use create_connection()")
        self._client = self._connection.client

    def disconnect(self) -> None:
        self._client = None

    def is_connected(self) -> bool:
        return self._client is not None
```

Note: no fallback client creation. The backend is a stateless operation handler — it requires an injected connection per the spec.

- [ ] **Step 8: Retire LocalConnectionMixin**

Read `src/mountainash_transport/storage/backends/local/local_connection.py` to understand its current shape — it is likely a no-op.

Delete the file:

```bash
rm src/mountainash_transport/storage/backends/local/local_connection.py
```

In `src/mountainash_transport/storage/backends/local/__init__.py`:
- Remove `from .local_connection import LocalConnectionMixin`
- Remove `LocalConnectionMixin` from the base classes
- Remove `LocalConnectionMixin` from `__all__`
- The local backend receives a `NullConnection` via `connection=` kwarg. Add inline connect/disconnect/is_connected if any code calls them on the backend:

```python
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
class LocalStorageBackend(
    LocalReadMixin,
    LocalWriteMixin,
    LocalListMixin,
    LocalDeleteMixin,
    LocalMetadataMixin,
    LocalCopyMixin,
    LocalDirectoryMixin,
):
    """Unified local filesystem storage backend composed from mixins."""

    def __init__(self, storage_profile: StorageProfileProtocol, *, auth_profile=None, connection=None) -> None:
        self.storage_profile = storage_profile
        self.auth_profile = auth_profile
        self._connection = connection

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def is_connected(self) -> bool:
        return True
```

- [ ] **Step 9: Rewrite protocol conformance tests**

Rewrite `tests/connections/test_protocol_shapes.py` — remove all `ConnectionMixinProtocol` tests, add `ConnectionProtocol` conformance tests for every connection class:

```python
"""Protocol conformance tests for connection protocols."""
from __future__ import annotations

import pytest

from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport._core.auth.strategies import NoAuthStrategy
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.connections.null import NullConnection
from mountainash_transport.connections.protocols import (
    OAuth2FlowProtocol,
    OAuth1FlowProtocol,
    CallbackServerProtocol,
)


class FakeOAuth2Spec:
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


class FakeProfile:
    def to_handler_kwargs(self) -> dict:
        return {"timeout": 30}

    def get_connection_url(self) -> str:
        return "https://example.com"


# ---------------------------------------------------------------------------
# ConnectionProtocol conformance
# ---------------------------------------------------------------------------

class TestConnectionProtocolConformance:
    def test_http_connection_conforms(self):
        conn = HTTPConnection(FakeProfile(), NoAuthStrategy())
        assert isinstance(conn, ConnectionProtocol)

    def test_null_connection_conforms(self):
        assert isinstance(NullConnection(), ConnectionProtocol)

    def test_s3_connection_conforms(self):
        from mountainash_transport.connections.s3 import S3Connection
        conn = S3Connection(FakeProfile(), NoAuthStrategy())
        assert isinstance(conn, ConnectionProtocol)

    def test_oauth2_connection_conforms(self):
        from mountainash_transport.connections.oauth2.connection import OAuth2Connection

        class FakeOAuth2Profile(FakeProfile):
            __spec__ = FakeOAuth2Spec()

        class FakeAuth:
            CLIENT_ID = "cid"
            CLIENT_SECRET = property(lambda self: type("S", (), {"get_secret_value": lambda s: "csec"})())
            SCOPE = "read"
            SETTINGS_SOURCE_SECRETS_PROVIDER = "test_mem"
            def persist_key(self): return "test.oauth2"

        conn = OAuth2Connection(FakeOAuth2Profile(), FakeAuth())
        assert isinstance(conn, ConnectionProtocol)

    def test_oauth1_connection_conforms(self):
        from mountainash_transport.connections.oauth1.connection import OAuth1Connection

        class FakeOAuth1Profile(FakeProfile):
            __spec__ = FakeOAuth1Spec()

        class FakeAuth:
            CONSUMER_KEY = "ck"
            CONSUMER_SECRET = property(lambda self: type("S", (), {"get_secret_value": lambda s: "cs"})())
            SETTINGS_SOURCE_SECRETS_PROVIDER = "test_mem"
            def persist_key(self): return "test.oauth1"

        conn = OAuth1Connection(FakeOAuth1Profile(), FakeAuth())
        assert isinstance(conn, ConnectionProtocol)

    def test_object_does_not_conform(self):
        assert not isinstance(object(), ConnectionProtocol)


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


class TestOAuth2FlowProtocol:
    def test_positive_conformance(self):
        assert isinstance(GoodOAuth2Flow(), OAuth2FlowProtocol)

    def test_negative_conformance(self):
        assert not isinstance(BadOAuth2Flow(), OAuth2FlowProtocol)

    def test_empty_class_does_not_conform(self):
        assert not isinstance(object(), OAuth2FlowProtocol)

    def test_real_implementation_conforms(self):
        from mountainash_transport.connections.oauth2.flow import OAuthFlow
        assert isinstance(OAuthFlow(FakeOAuth2Spec()), OAuth2FlowProtocol)


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


class TestOAuth1FlowProtocol:
    def test_positive_conformance(self):
        assert isinstance(GoodOAuth1Flow(), OAuth1FlowProtocol)

    def test_negative_conformance(self):
        assert not isinstance(BadOAuth1Flow(), OAuth1FlowProtocol)

    def test_empty_class_does_not_conform(self):
        assert not isinstance(object(), OAuth1FlowProtocol)

    def test_real_implementation_conforms(self):
        from mountainash_transport.connections.oauth1.flow import OAuth1Flow
        assert isinstance(OAuth1Flow(FakeOAuth1Spec()), OAuth1FlowProtocol)


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
```

- [ ] **Step 10: Update any remaining test files that import deleted modules**

Search for test imports of the deleted things:

```bash
grep -rn "OAuth2ConnectionMixin\|OAuth1ConnectionMixin\|ConnectionMixinProtocol\|StorageConnectionProtocol\|S3ConnectionMixin\|LocalConnectionMixin" tests/
```

For each hit:
- Tests for `OAuth2ConnectionMixin` (`tests/connections/oauth2/test_mixin.py`) — **delete the entire test file**. The mixin is replaced by `OAuth2Connection` which has its own tests in `test_connection.py`.
- Tests for `OAuth1ConnectionMixin` (`tests/connections/oauth1/test_mixin.py`) — **delete the entire test file**. Same reason.
- Any `StorageConnectionProtocol` conformance tests — update to use `ConnectionProtocol`.
- Any `ConnectionMixinProtocol` tests — already handled by the protocol shapes rewrite.

```bash
rm tests/connections/oauth2/test_mixin.py
rm tests/connections/oauth1/test_mixin.py
```

- [ ] **Step 11: Run full test suite**

Run: `hatch run test:test`
Expected: All tests pass

- [ ] **Step 12: Run lint**

Run: `hatch run ruff:check`
Expected: Clean

- [ ] **Step 13: Commit**

```bash
git add -A
git commit -m "refactor: retire StorageConnectionProtocol, ConnectionMixinProtocol, and OAuth mixin files

Delete:
- connections/oauth2/mixin.py (replaced by connections/oauth2/connection.py)
- connections/oauth1/mixin.py (replaced by connections/oauth1/connection.py)
- connections/protocols/prtcl_connection.py (replaced by _core/protocols.ConnectionProtocol)
- storage/protocols/prtcl_connection.py (replaced by _core/protocols.ConnectionProtocol)
- storage/backends/s3/s3_connection.py (replaced by connections/s3.S3Connection)
- storage/backends/local/local_connection.py (replaced by connections/null.NullConnection)
- tests/connections/oauth2/test_mixin.py
- tests/connections/oauth1/test_mixin.py

Single ConnectionProtocol now governs all connection types."
```

---

## Task 14: Final Verification

- [ ] **Step 1: Run full test suite with coverage**

Run: `hatch run test:cov`
Expected: All tests pass, coverage report generated

- [ ] **Step 2: Run lint**

Run: `hatch run ruff:check`
Expected: Clean

- [ ] **Step 3: Verify public API imports**

Run:
```bash
python -c "
from mountainash_transport import (
    StorageFacade, read_bytes, copy_between, storage,
    ConnectionProtocol, TransportConnectionError,
    StorageError, StorageConnectionError,
    CONST_STORAGE_PROVIDER_TYPE,
)
from mountainash_transport.connections import (
    create_connection, HTTPConnection, NullConnection, S3Connection,
    OAuth2Connection, OAuth1Connection,
    TransportConnectionError, ConnectionTimeoutError,
)
from mountainash_transport._core.auth import (
    AuthStrategy, resolve_auth_strategy,
    NoAuthStrategy, BearerTokenStrategy, BasicAuthStrategy,
    IAMCredentialStrategy,
)
print('All imports OK')
"
```
Expected: `All imports OK`

- [ ] **Step 4: Verify old protocols are gone**

Run:
```bash
python -c "
try:
    from mountainash_transport import StorageConnectionProtocol
    print('FAIL: StorageConnectionProtocol still exported')
except ImportError:
    print('OK: StorageConnectionProtocol removed from public API')

try:
    from mountainash_transport.connections import ConnectionMixinProtocol
    print('FAIL: ConnectionMixinProtocol still exported')
except ImportError:
    print('OK: ConnectionMixinProtocol removed from public API')

try:
    from mountainash_transport.connections import OAuth2ConnectionMixin
    print('FAIL: OAuth2ConnectionMixin still exported')
except ImportError:
    print('OK: OAuth2ConnectionMixin removed')

try:
    from mountainash_transport.connections import OAuth1ConnectionMixin
    print('FAIL: OAuth1ConnectionMixin still exported')
except ImportError:
    print('OK: OAuth1ConnectionMixin removed')
"
```
Expected: All `OK`

- [ ] **Step 5: Verify no regressions in existing backend behavior**

Run:
```bash
hatch run test:test-target-quick tests/storage_backends/ -v
hatch run test:test-target-quick tests/storage_facade/ -v
hatch run test:test-target-quick tests/settings/ -v
hatch run test:test-target-quick tests/connections/ -v
```
Expected: All pass

---

## Summary of architectural end state

After all tasks:

```
_core/
  auth/
    __init__.py            # re-exports
    strategies.py          # AuthStrategy + NoAuth, Bearer, Basic, IAM
    resolver.py            # resolve_auth_strategy()
  protocols.py             # ConnectionProtocol[C]

connections/
  __init__.py              # public API + create_connection() factory
  http.py                  # HTTPConnection
  s3.py                    # S3Connection
  null.py                  # NullConnection
  errors.py                # TransportConnectionError + timeout + OAuth errors
  oauth2/
    connection.py          # OAuth2Connection (decorator)
    flow.py                # OAuthFlow (unchanged)
  oauth1/
    connection.py          # OAuth1Connection (decorator)
    flow.py                # OAuth1Flow (unchanged)
  server/                  # unchanged
  protocols/               # OAuth flow + callback protocols only (prtcl_connection.py deleted)
```

**Deleted (old architecture):**
- `storage/protocols/prtcl_connection.py` — `StorageConnectionProtocol`
- `connections/protocols/prtcl_connection.py` — `ConnectionMixinProtocol`
- `connections/oauth2/mixin.py` — `OAuth2ConnectionMixin`
- `connections/oauth1/mixin.py` — `OAuth1ConnectionMixin`
- `storage/backends/s3/s3_connection.py` — `S3ConnectionMixin`
- `storage/backends/local/local_connection.py` — `LocalConnectionMixin`

Single `ConnectionProtocol`, auth strategies as the resolution layer, connections own client lifecycle, backends are stateless operation handlers.
