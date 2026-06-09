# Connection Architecture Alignment — Design Spec

> **Created:** 2026-06-09
> **Status:** Draft
> **Package:** mountainash-transport
> **Follows:** `2026-06-09-oauth-extraction-design.md` (PR #63, merged)

## Problem

After the OAuth extraction (PR #63), mountainash-transport has connection
management scattered across four locations with two incompatible connection
protocols. Auth resolution, client creation, and token lifecycle are tangled
together differently in each backend.

### Client creation in 4 places

| Location | SDK | How it creates clients |
|----------|-----|----------------------|
| `storage/backends/s3/s3_connection.py` | boto3 | `boto3.client("s3", **profile.to_handler_kwargs(auth))` |
| `storage/backends/http/__init__.py` | httpx | Lazy `httpx.Client(**profile.to_handler_kwargs(auth))` |
| `connections/oauth2/mixin.py` | httpx | `httpx.Client(headers={"Authorization": f"Bearer {token}"})` after token lifecycle |
| `connections/oauth2/flow.py` | httpx | Ephemeral `with httpx.Client() as c:` for token exchange POSTs |

### Auth resolution in 2 places

- `HTTPStorageProfile._resolve_auth_headers()` — isinstance switch over
  NoAuth/TokenAuth/PasswordAuth/OAuth2Auth → header dict
- OAuth2 mixin — inline Bearer token injection after token lifecycle

### Two incompatible connection protocols

- `StorageConnectionProtocol`: `connect() -> None`, `disconnect() -> None`,
  `is_connected() -> bool`
- `ConnectionMixinProtocol`: `connect(auth, auto_authorize) -> Self`,
  `disconnect() -> None`, `client -> httpx.Client | None`

## Goals

- Establish one connection pattern for all providers and auth modes.
- Separate three concerns that are currently tangled: auth resolution, client
  creation, and token lifecycle.
- Make backends stateless operation handlers that receive connected clients,
  rather than creating their own.
- Replace both connection protocols with a single `ConnectionProtocol`.
- Wrap raw SDK exceptions at the connection boundary.

## Non-Goals

- Messaging backends.
- SSH/paramiko connection class (future phase — same pattern, different SDK).

## Design: Three Layers

### Layer 1 — Auth Strategies (`_core/auth/`)

Small, focused objects that inject credentials into SDK client kwargs. One
strategy per auth-mode × SDK family. No token lifecycle, no client creation —
just credential resolution.

#### Protocol

```python
@runtime_checkable
class AuthStrategy(Protocol):
    def apply(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Return a new dict with auth credentials injected into SDK client kwargs.

        Does NOT mutate the input dict — returns a new dict with auth added.
        """
        ...
```

`apply()` takes SDK client kwargs and returns a **new dict** with auth
injected (no mutation — original preserved for debugging/retry). This works
for every SDK shape:
- httpx: adds/merges `headers` key (e.g., `{"Authorization": "Bearer ..."}`)
- httpx: adds `auth` key (e.g., authlib's OAuth1Auth handler for OAuth1)
- boto3: adds `aws_access_key_id`, `aws_secret_access_key`, `region_name`
- paramiko: adds `pkey` or `password` (future)

Note: OAuth1 uses httpx's `auth=` parameter (not headers) for request
signing. `apply()` operates on the full kwargs dict, so `OAuth1SignedStrategy`
injects `kwargs["auth"] = AuthlibOAuth1Auth(...)` — a different key than
headers but the same protocol.

#### Concrete strategies (initial set — httpx family)

| Strategy | Auth profile types | Produces |
|----------|-------------------|----------|
| `NoAuthStrategy` | `NoAuth`, `None` | passthrough (no mutation) |
| `BearerTokenStrategy` | `TokenAuth`, `JWTAuth`, `OAuth2Auth`, `OAuth2AuthCodeAuth` | `headers["Authorization"] = "Bearer {token}"` |
| `BasicAuthStrategy` | `PasswordAuth` | `headers["Authorization"] = "Basic {base64}"` |

S3 (`IAMCredentialStrategy`) and SSH strategies are added in Phase 5 when
those backends are refactored. Until then, S3 and SSH keep their existing
auth resolution.

#### Resolver

```python
def resolve_auth_strategy(auth_profile: AuthProfile | None) -> AuthStrategy:
    """Map an auth profile instance to its auth strategy."""
```

Single isinstance dispatch function. The switch logic currently in
`HTTPStorageProfile._resolve_auth_headers()` moves here. This is the one
place in the codebase where auth profile type → credential shape mapping
lives.

### Layer 2 — Connections (`connections/`)

Standalone objects that take a storage profile + auth strategy and create an
authenticated SDK client. One connection class per SDK family.

#### Protocol

```python
C = TypeVar("C")

@runtime_checkable
class ConnectionProtocol(Protocol[C]):
    def connect(self) -> Self: ...
    def disconnect(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *args: Any) -> None: ...

    @property
    def client(self) -> C | None: ...

    @property
    def is_connected(self) -> bool: ...
```

This single protocol replaces both `StorageConnectionProtocol` and
`ConnectionMixinProtocol`. All connections implement it: leaf connections,
OAuth decorated connections, and (eventually) tunnelled connections.

Generic `C` parameter provides compile-time type safety:
`HTTPConnection` implements `ConnectionProtocol[httpx.Client]`,
`S3Connection` implements `ConnectionProtocol[boto3.S3.Client]`. Backends
declare which client type they require — no `Any` hole for static checkers.

Context manager support (`__enter__`/`__exit__`) is part of the protocol.
`__exit__` delegates to `disconnect()`. This guarantees safe resource
cleanup via `with`.

#### Leaf connections

Direct SDK client creation from profile config + auth strategy:

```python
class HTTPConnection:
    """Creates an authenticated httpx.Client."""

    def __init__(self, profile: StorageProfileProtocol, auth_strategy: AuthStrategy) -> None:
        self._profile = profile
        self._auth_strategy = auth_strategy
        self._client: httpx.Client | None = None

    def connect(self) -> Self:
        kwargs = self._profile.to_handler_kwargs()  # SDK config only, no auth
        kwargs = self._auth_strategy.apply(kwargs)   # inject auth
        self._client = httpx.Client(**kwargs)
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
```

`S3Connection` follows the same pattern with `boto3.client("s3", **kwargs)`.

Connections take a strategy directly — the caller (or a factory) resolves it
from the auth profile. This keeps connections decoupled from the auth profile
type system.

#### Decorated connections (OAuth)

OAuth connections manage token lifecycle, then delegate to a leaf connection:

```python
class OAuth2Connection:
    """Manages OAuth2 token lifecycle, delegates client creation to HTTPConnection."""

    def __init__(
        self,
        profile: StorageProfileProtocol,
        auth_profile: OAuth2Auth | OAuth2AuthCodeAuth,
        *,
        auto_authorize: bool = False,
    ) -> None:
        self._profile = profile
        self._spec = profile.__spec__       # ProfileSpec — for token lifecycle (provider name, OAuth URLs)
        self._auth = auth_profile
        self._auto_authorize = auto_authorize
        self._inner: HTTPConnection | None = None

    def connect(self) -> Self:
        # 1. Check secrets backend for stored token
        # 2. Refresh if expired
        # 3. Authorize if missing (interactive)
        # 4. Produce BearerTokenStrategy with valid token
        access_token = self._resolve_token()
        strategy = BearerTokenStrategy(access_token)
        self._inner = HTTPConnection(self._profile, auth_strategy=strategy)
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

    def __exit__(self, *args: Any) -> None:
        self.disconnect()
```

`OAuth2Connection` takes `profile: StorageProfileProtocol` (same as leaf
connections) and accesses `profile.__spec__` for the `ProfileSpec` needed by
token lifecycle (provider name for secrets key, OAuth URLs in metadata).

`_resolve_token()` contains the same lookup → refresh → authorize → persist
logic currently in `OAuth2ConnectionMixin.connect()`. The token lifecycle
logic doesn't change — only its position in the architecture.

`OAuth1Connection` follows the same pattern, producing an
`OAuth1SignedStrategy` (wrapping authlib's OAuth1Auth handler) and delegating
to `HTTPConnection`.

The OAuth flow modules (`oauth2/flow.py`, `oauth1/flow.py`) and server
modules (`server/callback.py`, `server/manual.py`) are unchanged.

#### Downstream impact on API consumers

Downstream API consumer classes (Garmin, Fitbit, etc.) currently subclass
`OAuth2ConnectionMixin` to get a client. With this design, they instead
receive an already-authenticated connection:

```python
# Before (mixin pattern):
class GarminClient(OAuth2ConnectionMixin):
    _spec = GARMIN_SPEC
    _base_url = "https://api.garmin.com"
    # inherits connect(), client, etc.

# After (connection injection):
class GarminClient:
    def __init__(self, connection: OAuth2Connection):
        self.connection = connection
    # orchestration only — connection is infrastructure
```

Connection is infrastructure; what API consumers do with it is orchestration.
This separation is cleaner and more testable — consumers can receive a mock
connection in tests.

#### Convenience factory

Two-step dispatch: profile type → leaf connection class, auth profile type →
optional OAuth decorator.

```python
def create_connection(
    profile: StorageProfileProtocol,
    auth_profile: AuthProfile | None = None,
    *,
    auto_authorize: bool = False,
) -> ConnectionProtocol:
    """Create the right connection for a profile + auth combination."""
    # Step 1: Is this an OAuth auth profile? If so, wrap with OAuth decorator.
    if isinstance(auth_profile, (OAuth2Auth, OAuth2AuthCodeAuth)):
        return OAuth2Connection(profile, auth_profile, auto_authorize=auto_authorize)
    if isinstance(auth_profile, OAuth1Auth):
        return OAuth1Connection(profile, auth_profile, auto_authorize=auto_authorize)

    # Step 2: Static auth — resolve strategy and pick leaf connection.
    strategy = resolve_auth_strategy(auth_profile)
    LeafClass = _connection_for_provider(profile)  # HTTP→HTTPConnection, S3→S3Connection
    return LeafClass(profile, auth_strategy=strategy)
```

`_connection_for_provider()` maps `profile.__spec__.provider_type` to a leaf
connection class via a registry (same pattern as `get_storage_backend()`).

The OAuth fork happens *before* strategy resolution because OAuth connections
need the raw auth profile for token lifecycle (client_id, client_secret,
persist_key). They resolve their own strategy internally after token
lifecycle completes.

The facade and any consumer calls this rather than constructing connections
directly.

### Layer 3 — Operations (Backends)

Backends become stateless operation handlers. They receive a connection (or
its client) rather than creating their own.

```python
# Before:
backend = HTTPStorageBackend(profile, auth_profile=auth)
backend._get_client()  # creates client internally
backend.read_to_bytes(path)

# After:
conn = create_connection(profile, auth_profile=auth)
conn.connect()
backend = HTTPStorageBackend(conn)
backend.read_to_bytes(path)
```

`HTTPStorageBackend._get_client()` is deleted. The backend accesses
`self._connection.client` directly. The backend's constructor takes a
connection, not a profile + auth_profile.

### Profile Signature Change

`StorageProfileProtocol.to_handler_kwargs()` drops the `auth_profile`
parameter. Profiles return SDK config only (timeouts, SSL, endpoints,
regions). Auth injection is the strategy's job.

```python
# Before:
class StorageProfileProtocol(Protocol):
    def to_handler_kwargs(self, auth_profile=None) -> dict: ...

# After:
class StorageProfileProtocol(Protocol):
    def to_handler_kwargs(self) -> dict: ...
```

This affects all 9 storage profile classes. Each drops its `auth_profile`
parameter and any internal `_resolve_auth_headers()` logic.

## Error Handling

The connection layer wraps raw SDK exceptions at the boundary:

| Raw exception | Connection exception |
|--------------|---------------------|
| `httpx.TimeoutException` | `ConnectionTimeoutError(TransportConnectionError)` |
| `httpx.ConnectError` | `TransportConnectionError` |
| `json.JSONDecodeError` on token response | `TokenExchangeError` |
| Missing `access_token` key in response | `TokenExchangeError` |

`ConnectionTimeoutError` is a new subclass of the existing `ConnectionError`
base (from `connections/errors.py`).

The HTTP storage backend currently wraps httpx exceptions into
`StorageConnectionError`. Once it receives a connection instead of creating
its own client, the connection layer handles these and the backend just
sees connected client or `TransportConnectionError`.

Note: the existing `ConnectionError` class in `connections/errors.py` is
renamed to `TransportConnectionError` to avoid shadowing Python's builtin
`ConnectionError`. All existing subclasses (`TokenExchangeError`,
`TokenRefreshError`, `AuthorizationRequired`) re-parent to the new name.

## File Layout (after all phases)

```
_core/
  auth/
    __init__.py            # re-exports
    strategies.py          # AuthStrategy protocol + NoAuth, Bearer, Basic strategies
    resolver.py            # resolve_auth_strategy()
  protocols.py             # ConnectionProtocol (single shared protocol)

connections/
  __init__.py              # public API + create_connection() factory
  protocols/               # prtcl_* files for conformance tests
  errors.py                # TransportConnectionError + ConnectionTimeoutError + OAuth errors
  http.py                  # HTTPConnection
  s3.py                    # S3Connection (Phase 5)
  null.py                  # NullConnection (local filesystem — no-op, always connected)
  oauth2/
    connection.py          # OAuth2Connection (replaces mixin.py)
    flow.py                # OAuthFlow (unchanged)
  oauth1/
    connection.py          # OAuth1Connection (replaces mixin.py)
    flow.py                # OAuth1Flow (unchanged)
  server/                  # unchanged (callback.py, manual.py)
```

## Phased Implementation

Each phase is independently shippable and testable. Earlier phases don't
break existing code — new abstractions are added alongside, then existing
code migrates.

### Phase 1: Auth strategies

- Create `_core/auth/__init__.py`, `_core/auth/strategies.py`,
  `_core/auth/resolver.py`
- `AuthStrategy` protocol + `NoAuthStrategy`, `BearerTokenStrategy`,
  `BasicAuthStrategy`
- `resolve_auth_strategy()` function
- Protocol-first TDD: protocols → conformance tests → behavioral tests →
  implementations

### Phase 2: ConnectionProtocol + HTTPConnection

- Populate `_core/protocols.py` with `ConnectionProtocol`
- Create `connections/http.py` with `HTTPConnection`
- Add `ConnectionTimeoutError` to `connections/errors.py`
- Protocol-first TDD

### Phase 3: OAuth connection refactor

- Create `connections/oauth2/connection.py` with `OAuth2Connection`
  (decorator over HTTPConnection, token lifecycle from current mixin)
- Create `connections/oauth1/connection.py` with `OAuth1Connection`
- Add robust error handling (wrap httpx.RequestError, JSONDecodeError,
  missing keys in token responses)
- Retire `oauth2/mixin.py` and `oauth1/mixin.py`
- Update `ConnectionMixinProtocol` conformance tests → `ConnectionProtocol`

### Phase 4: Profile signature change

- Refactor `StorageProfileProtocol.to_handler_kwargs()` — remove `auth_profile`
  parameter across all 9 profile classes
- Delete `HTTPStorageProfile._resolve_auth_headers()` (logic now in auth strategies)
- Pure signature change — no backend behavioral changes yet
- Independently verifiable: profiles return SDK config only

### Phase 5: HTTP backend refactor + facade integration

- Refactor `HTTPStorageBackend` to receive a connection, not create clients
- Add `create_connection()` factory to `connections/__init__.py`
- Update facade to create connections and pass to backends

Note: between Phase 3 and Phase 4b, the codebase intentionally has two
client-creation patterns: connections (for OAuth/API consumers) and direct
backend creation (for storage operations). This is expected and temporary.

### Phase 6: S3 backend refactor

- Create `_core/auth/strategies.py` addition: `IAMCredentialStrategy`
- Create `connections/s3.py` with `S3Connection`
- Refactor `S3StorageBackend` to receive connection
- Retire `S3ConnectionMixin`

### Phase 7: Protocol consolidation + cleanup

- Retire `StorageConnectionProtocol` (`storage/protocols/prtcl_connection.py`)
- Retire `ConnectionMixinProtocol` (`connections/protocols/prtcl_connection.py`)
- Both replaced by `_core/protocols.ConnectionProtocol`
- Update all protocol conformance tests
- Update top-level `__init__.py` exports
- Clean up any remaining references to old protocols

## Verification

After each phase:
1. `hatch run test:test-quick` — all tests pass, no regressions
2. `hatch run ruff:check` — lint clean
3. Public API imports unchanged (`StorageFacade`, `read_bytes`, etc.)
4. Protocol conformance tests pass for new and migrated protocols

End state: single `ConnectionProtocol`, auth strategies as the resolution
layer, connections own client lifecycle, backends are pure operations.

## Future Considerations

- **Async connections**: Messaging backends (Kafka, WebSocket, SSE) will need
  an `AsyncConnectionProtocol` — same methods, `async def` instead of `def`.
  The sync protocol should be designed so the async variant is a straightforward
  mirror. Not needed until messaging backends arrive.
- **Token refresh for long-lived sessions**: `OAuth2Connection.connect()`
  resolves a token once. If the token expires during a long-lived session,
  there is no automatic re-connection. A future `ensure_connected()` method
  on `ConnectionProtocol` could check token validity before returning the
  client. The protocol should reserve this method when needed.
- **SSH tunnelling**: Fits the decorator pattern — `TunnelledConnection`
  wraps any leaf connection through a port-forwarded endpoint, same as OAuth
  wraps with token lifecycle.
