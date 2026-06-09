# OAuth Extraction from auth-client — Design Spec

> **Created:** 2026-06-09
> **Status:** Draft
> **Package:** mountainash-transport
> **Backlog:** `mountainash-central/01.principles/mountainash-utils-files/h.backlog/extract-oauth-flows-from-auth-client.md`

## Problem

mountainash-auth-client bundles two concerns in one package:

1. **Schemas** — pure pydantic profile classes (`NoAuth`, `OAuth2Auth`, etc.)
   that define credential shapes. No HTTP, no operations.
2. **Flows + mixins + server** — OAuth handshake operations, token lifecycle
   management, and httpx client creation. These are connection operations.

Layer 2 belongs in mountainash-transport's `connections/` directory — it
performs the same kind of work as the storage backends (connect, authenticate,
move bytes) and shares the same httpx dependency.

## Goals

- Populate the `connections/` stub with OAuth flow and connection mixin modules.
- Follow protocol-first TDD: define protocols, write all tests (conformance +
  behavioral), verify red, then bring implementations green.
- Fix two security issues in the copied code: CSRF state validation weakness
  and PKCE verifier overwrite race (see Security Fixes section).
- Add `[oauth1]` optional extra for authlib.
- Declare mountainash-settings and mountainash-auth-client as explicit dependencies.
- Leave auth-client untouched — no deprecation shims in this phase. Connection
  exports are internal to transport until auth-client's compatibility PR lands.

## Non-Goals

- `_core/http.py` shared client factory (follow-up work). The backlog doc lists
  this as step 1, but we extract first to reduce blast radius and consolidate
  in a follow-up — the OAuth flows work correctly with inline httpx.Client
  creation until then.
- Deprecation re-exports in auth-client (separate PR in that repo, separate release).
- Moving `CONST_AUTH_MODE` — it stays in auth-client (describes auth profiles).
- Messaging protocols or backends.

## Source Modules

All source files are in `mountainash-auth-client/src/mountainash_auth_client/`:

| Module | Class/Function | Lines | Dependencies |
|--------|---------------|-------|-------------|
| `flows/oauth2.py` | `OAuthFlow` | ~193 | httpx, ProfileSpec, errors, server |
| `flows/oauth1.py` | `OAuth1Flow` | ~127 | httpx, authlib (lazy), ProfileSpec, errors, server |
| `mixins/oauth2.py` | `OAuth2ConnectionMixin` | ~84 | httpx, ProfileSpec, get_secrets_backend, OAuthFlow, OAuth2Auth schemas, errors |
| `mixins/oauth1.py` | `OAuth1ConnectionMixin` | ~71 | httpx, authlib (lazy), ProfileSpec, get_secrets_backend, OAuth1Flow, OAuth1Auth schema, errors |
| `server/callback.py` | `LocalCallbackServer` | ~48 | stdlib only |
| `server/manual.py` | `extract_code_from_input`, `prompt_for_code` | ~26 | stdlib only |
| `errors.py` | `TokenExchangeError`, `TokenRefreshError`, `AuthorizationRequired` | ~32 | none |

**Total:** ~581 lines of source, ~581 lines of tests.

## Protocol Design

### Hierarchy

```
OAuth2FlowProtocol
  ├── build_authorize_url(client_id, redirect_uri, scope?) → tuple[str, str]
  ├── exchange_code(code, redirect_uri, client_id, client_secret, scope?, state?) → dict
  ├── refresh(refresh_token, client_id, client_secret) → dict
  ├── is_expired(token_expires_at, buffer_seconds?) → bool  [static]
  └── authorize(client_id, client_secret, redirect_mode?, scope?) → dict

OAuth1FlowProtocol
  ├── build_authorize_url(oauth_token) → str
  ├── request_token(consumer_key, consumer_secret, callback_url?) → dict
  ├── exchange_verifier(consumer_key, consumer_secret, oauth_token,
  │                     oauth_token_secret, verifier) → dict
  └── authorize(consumer_key, consumer_secret, redirect_mode?) → dict

CallbackServerProtocol
  ├── port → int  [property]
  ├── redirect_uri → str  [property]
  └── wait_for_callback() → dict[str, str]

ConnectionMixinProtocol
  ├── connect(auth, *, auto_authorize?) → Self
  ├── disconnect() → None
  ├── client → httpx.Client | None  [property]
  ├── __enter__() → Self
  └── __exit__(*args) → None
```

All protocols are `@runtime_checkable`. Note: `@runtime_checkable` only checks
method *existence*, not signatures or dunder methods. `__enter__`/`__exit__`
on `ConnectionMixinProtocol` are enforced by static type checkers only, not
by runtime `isinstance`. `inspect.signature` tests in the conformance suite
provide the arity/type enforcement layer.

### Design rationale

- **No shared base for flows**: OAuth2 and OAuth1 have incompatible signatures
  for both `build_authorize_url()` and `authorize()` (`client_id` vs
  `consumer_key`, different arity). A marker-only base would match *every*
  class via `isinstance` (a protocol with no methods is satisfied by anything),
  providing no discrimination. Instead, use a Union type
  (`OAuth2FlowProtocol | OAuth1FlowProtocol`) where family identity is needed.
- **Single ConnectionMixinProtocol**: Both OAuth2 and OAuth1 mixins have the same
  public interface (`connect`, `disconnect`, `client`, context manager). The
  `auth` parameter type differs but the protocol uses `Any` — runtime type
  checking happens inside the implementation. `client` returns
  `httpx.Client | None` (None before `connect()` is called). `disconnect()`
  is included — both `__exit__` implementations delegate to it.
- **ConnectionMixinProtocol vs StorageConnectionProtocol**: The existing
  `StorageConnectionProtocol` (`storage/protocols/prtcl_connection.py`) defines
  `connect() -> None` with no parameters. `ConnectionMixinProtocol` defines
  `connect(auth, auto_authorize) -> Self`. These are distinct protocols for
  distinct domains — storage backends connect via profile kwargs at construction
  time, while OAuth mixins connect via auth profiles at call time. When
  `_core/protocols.py` introduces a shared `ConnectionProtocol`, these two will
  be reconciled. Until then, they coexist as domain-specific contracts.
- **No protocol for manual entry**: `prompt_for_code` and `extract_code_from_input`
  are pure functions, not classes. Protocols don't add value for standalone functions.

### Implementation additions beyond copy-and-adapt

The following methods must be **created** during extraction — they are called by
the existing code but not defined in the source modules:

- **`disconnect()`** on both `OAuth2ConnectionMixin` and `OAuth1ConnectionMixin`:
  `__exit__` calls `self.disconnect()` but neither class defines it. Add:
  close `self._client` if not None, set `self._client = None`.
- **`client` property** on `OAuth1ConnectionMixin`: only has `_client` class
  variable, no public property. Add a `@property` returning `self._client`
  (matching `OAuth2ConnectionMixin`'s existing property).

## File Layout

### Source

```
src/mountainash_transport/connections/
  __init__.py              # Public re-exports
  protocols/
    __init__.py            # Re-exports all protocol classes (__all__ list)
    prtcl_oauth2_flow.py   # OAuth2FlowProtocol
    prtcl_oauth1_flow.py   # OAuth1FlowProtocol
    prtcl_callback.py      # CallbackServerProtocol
    prtcl_connection.py    # ConnectionMixinProtocol
  errors.py                # ConnectionError base, TokenExchangeError, TokenRefreshError, AuthorizationRequired
  oauth2/
    __init__.py            # Re-exports OAuthFlow, OAuth2ConnectionMixin
    flow.py                # OAuthFlow
    mixin.py               # OAuth2ConnectionMixin
  oauth1/
    __init__.py            # Re-exports OAuth1Flow, OAuth1ConnectionMixin
    flow.py                # OAuth1Flow
    mixin.py               # OAuth1ConnectionMixin
  server/
    __init__.py            # Re-exports LocalCallbackServer, prompt_for_code, extract_code_from_input
    callback.py            # LocalCallbackServer
    manual.py              # extract_code_from_input, prompt_for_code
```

### Tests

```
tests/connections/
  __init__.py
  conftest.py              # FakeSpec, InMemoryBackend fixtures
  test_protocol_shapes.py  # Surface-area, conformance, alignment tests
  test_errors.py           # Exception construction and message tests
  oauth2/
    __init__.py
    test_flow.py           # OAuth2 flow behavioral tests
    test_mixin.py          # OAuth2 connection mixin behavioral tests
  oauth1/
    __init__.py
    test_flow.py           # OAuth1 flow behavioral tests
    test_mixin.py          # OAuth1 connection mixin behavioral tests
  server/
    __init__.py
    test_server.py         # Callback server + manual entry tests
```

## Import Adaptations

When copying from auth-client, these import paths change:

| auth-client import | transport import |
|---|---|
| `from mountainash_auth_client.errors import ...` | `from mountainash_transport.connections.errors import ...` |
| `from mountainash_auth_client.server.callback import ...` | `from mountainash_transport.connections.server.callback import ...` |
| `from mountainash_auth_client.server.manual import ...` | `from mountainash_transport.connections.server.manual import ...` |
| `from mountainash_auth_client.flows.oauth2 import OAuthFlow` | `from mountainash_transport.connections.oauth2.flow import OAuthFlow` |
| `from mountainash_auth_client.flows.oauth1 import OAuth1Flow` | `from mountainash_transport.connections.oauth1.flow import OAuth1Flow` |

These imports stay unchanged (schemas remain in auth-client):

| Import | Reason |
|---|---|
| `from mountainash_settings import ProfileSpec` | Runtime dependency, already used by transport |
| `from mountainash_settings.secrets.registry import get_secrets_backend` | Token persistence |
| `from mountainash_auth_client.schemas.oauth2 import OAuth2Auth` | TYPE_CHECKING only |
| `from mountainash_auth_client.schemas.oauth1 import OAuth1Auth` | TYPE_CHECKING only |

## Test Infrastructure

### conftest.py fixtures

Copied from auth-client's test patterns:

- **`FakeSpec`** — duck-types `ProfileSpec` with `.name` and `.metadata` dict
  containing `authorize_url`, `token_url`, `use_pkce`, `default_scope`,
  `callback_port`.
- **`InMemoryBackend`** — implements `SecretsBackend` protocol with a dict
  backend. Methods: `get`, `set`, `delete`, `transaction` (context manager).
- **Fixtures**: `fake_spec`, `memory_backend` (registered via
  `register_secrets_backend`, cleaned up via `clear_secrets_registry`).

### Protocol conformance tests (test_protocol_shapes.py)

Following the pattern in `tests/storage/protocols/test_protocol_shapes.py`:

1. **Surface-area tests** — verify each protocol defines the expected methods.
2. **Positive conformance** — `isinstance(OAuthFlow(...), OAuth2FlowProtocol)`.
3. **Negative conformance** — dummy class missing methods fails `isinstance`.
4. **Bidirectional alignment** — no rogue public methods on implementations
   beyond what the protocol declares.

### Behavioral tests

Adapted from auth-client's existing test files with import path updates:

- `test_flow.py` (OAuth2): authorize URL building, PKCE, code exchange
  (mocked httpx), token refresh, expiration checking. **New tests**: CSRF state
  validation (missing/mismatched/correct), PKCE verifier keyed by state
  (sequential and concurrent).
- `test_flow.py` (OAuth1): authorize URL building, authlib import error
  handling.
- `test_mixin.py` (OAuth2): token lifecycle with InMemoryBackend, client
  creation, bearer header injection, auto-authorize flow.
- `test_mixin.py` (OAuth1): stored-token connect, missing-token
  AuthorizationRequired, auto-authorize persistence, signed httpx.Client
  creation, authlib-missing ImportError.
- `test_server.py`: port assignment, redirect_uri format, real HTTP callback
  via threading, code extraction from URLs.
- `test_errors.py`: exception construction, message formatting, attributes.

## Dependencies

### pyproject.toml changes

```toml
dependencies = [
    "pydantic==2.9.2",
    "pydantic-settings==2.6.1",
    "universal_pathlib==0.2.2",
    "boto3>=1.29.4,<=1.34.113",
    "httpx>=0.27",
    "mountainash-settings",        # NEW — already a runtime import
    "mountainash-auth-client",     # NEW — already a runtime import (schemas, CONST_AUTH_MODE)
]

[project.optional-dependencies]
oauth1 = ["authlib>=1.3.0"]       # NEW — for OAuth1 3-legged flow
```

### hatch.toml changes

Add `authlib` to test environments so OAuth1 tests can run.

## Security Fixes

Two issues in the auth-client OAuth code will be fixed during extraction
rather than copied as-is.

### 1. CSRF state validation weakness

**Current**: `OAuthFlow.authorize()` only checks for state mismatch when state
is present in the callback params. A callback with no `state` parameter bypasses
the check entirely.

**Fix**: Require `params.get("state") == state` — reject callbacks where state
is missing or mismatched. Add tests for: missing state, mismatched state, and
correct state.

### 2. PKCE verifier overwrite race

**Current**: `OAuthFlow` stores `_code_verifier` as a single instance field.
If `build_authorize_url()` is called twice before the first code is exchanged,
the verifier for the first request is silently overwritten.

**Fix**: Key pending PKCE verifiers by state token in a dict
(`_pending_verifiers: dict[str, str]`). `build_authorize_url()` returns the
state token as part of the tuple; `exchange_code()` accepts an optional
`state` parameter to look up the correct verifier and consumes it exactly once.
When `state` is not provided, falls back to the most recently stored verifier
(preserving backward compatibility for single-flow usage). Add tests for:
sequential authorize/exchange, concurrent authorize URLs with independent
exchange.

Note: `exchange_code`'s protocol signature gains an optional `state` parameter:
`exchange_code(code, redirect_uri, client_id, client_secret, scope?, state?) → dict`.

## Compatibility

### Python 3.10

Auth-client mixins use `from typing import Self` (Python 3.11+). Transport
supports `>=3.10`. Since `typing_extensions` is already a transitive dependency
via pydantic, use unconditionally:

```python
from __future__ import annotations
from typing_extensions import Self
```

## TDD Workflow

### Phase 1: Red

1. Create `connections/protocols/` directory with 4 `prtcl_*.py` protocol files
   and `__init__.py` with `__all__`.
2. Create `connections/errors.py` (leaf module, no internal deps).
3. Create `tests/connections/test_protocol_shapes.py` — conformance tests
   that import the protocol classes and reference the (not-yet-existing)
   implementation classes.
4. Create all behavioral test files that import from `connections.oauth2.flow`,
   `connections.oauth1.flow`, etc. These will fail with `ImportError` since the
   implementations don't exist yet.
5. **Run the test suite** — confirm all new tests fail (import errors or
   assertion failures). Existing tests must still pass.

### Phase 2: Green

6. Copy `server/callback.py` and `server/manual.py` (stdlib-only, no adaptations
   needed beyond module docstring).
7. Copy and adapt `oauth2/flow.py` — update internal imports per the table above.
   Apply security fixes: strict state validation, PKCE verifiers keyed by state.
8. Copy and adapt `oauth1/flow.py` — same import updates.
9. Copy and adapt `oauth2/mixin.py` — update internal imports, use TYPE_CHECKING
   guard for schema imports from auth-client. Use `typing_extensions.Self` for
   Python 3.10 compat. Add `disconnect()` method (see "Implementation additions"
   section above).
10. Copy and adapt `oauth1/mixin.py` — same pattern (TYPE_CHECKING + Self compat).
    Add missing `client` property and `disconnect()` method (see "Implementation
    additions" section above).
11. Create `conftest.py` with FakeSpec and InMemoryBackend.
12. Copy and adapt all behavioral test files.
13. Create `__init__.py` files with appropriate re-exports.
14. **Run the test suite** — all tests green, no regressions.

### Phase 3: Verify

15. `hatch run ruff:check` — lint clean.
16. `hatch build` — wheel builds.
17. `python -c "from mountainash_transport.connections import ..."` — public
    API accessible.

## Public API Additions

Add to `connections/__init__.py`:

```python
__all__ = [
    # Protocols
    "OAuth2FlowProtocol", "OAuth1FlowProtocol",
    "CallbackServerProtocol", "ConnectionMixinProtocol",
    # Errors
    "ConnectionError", "TokenExchangeError", "TokenRefreshError", "AuthorizationRequired",
    # Implementations
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

Whether to also re-export from the top-level `mountainash_transport/__init__.py`
is a judgment call. The storage public API has 27 items there already. Recommend
keeping connection exports in `connections/__init__.py` only for now — users
import via `from mountainash_transport.connections import OAuthFlow`.

## Follow-Up Work (not in this PR)

1. **`_core/http.py` shared client factory** — consolidate HTTPStorageBackend's
   auth resolution with the OAuth mixins' httpx.Client creation.
2. **Deprecation re-exports in auth-client** — requires auth-client to depend
   on transport; needs careful release coordination.
3. **CONST_AUTH_MODE location** — if deprecation shims are needed, this enum
   may need to move to mountainash-settings to break the circular dependency.
4. **ConnectionProtocol in `_core/protocols.py`** — the shared base protocol
   for any connection type (storage backends, OAuth, SSH tunnels).
5. **Robust error handling in flows** — wrap `httpx.RequestError`, timeout,
   invalid JSON, and missing token fields in connection-specific exceptions
   rather than leaking raw httpx/JSON errors.
