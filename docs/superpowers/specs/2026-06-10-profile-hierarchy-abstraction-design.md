# Profile Hierarchy Abstraction — Design Spec

> **Date:** 2026-06-10
> **Status:** Draft
> **Branch:** TBD (off `develop`)
> **Blocks:** #8 (provider-registry-honesty)

## Problem

`StorageProfileProtocol` is the only profile protocol in mountainash-transport.
Every consumer — connections, factory, facade — depends on it. This forces all
profiles into a storage shape, even when they represent a different concern:

- **SSH** is a connection/transport concern, not a storage provider. It needs a
  profile for host/port/auth config, but `get_connection_url()` and
  storage-specific spec fields (`handler_module`, `supports_streaming`) are
  meaningless for it.
- **Messaging** (backlog #11) will need its own profile family with
  broker-specific fields. It cannot reuse `StorageProfileProtocol`.
- **Connections** take `StorageProfileProtocol` but only call
  `to_handler_kwargs()` — they never use `get_connection_url()` or any
  storage-specific contract.

The base infrastructure in mountainash-settings (`ProfileSpec`, `Profile`,
`Registry`) is already family-agnostic. The coupling is entirely in
mountainash-transport's single-family assumption.

## Scope

Extract a base `ProfileProtocol` from `StorageProfileProtocol`. Widen the
connection factory to accept it. Prove the abstraction with the existing
storage profiles. Messaging scaffolding is out of scope — that family defines
its own protocol and registry when backlog #11 is designed.

Out of scope: connection decoupling to kwargs (that's #8), messaging profiles,
SSH profile creation, registry restructuring.

---

## 1. Profile Protocol Hierarchy

### `settings/profile_protocol.py` — restructured

The file currently defines only `StorageProfileProtocol`. Restructure to hold
both the base and the storage refinement:

```python
@t.runtime_checkable
class ProfileProtocol(Protocol):
    """Base contract for any profile in mountainash-transport.

    Every profile — storage, messaging, connection — can produce SDK-ready
    kwargs. Family-specific protocols refine this with additional methods.
    """

    def to_handler_kwargs(self) -> dict[str, t.Any]: ...


@t.runtime_checkable
class StorageProfileProtocol(ProfileProtocol, Protocol):
    """Storage-specific refinement.

    Adds ``get_connection_url()`` for diagnostics and logging. Only storage
    profiles implement this — connection and messaging profiles do not.
    """

    def get_connection_url(self) -> str: ...
```

Both are `@runtime_checkable` for isinstance checks in factories and
registries.

### Public API

Export `ProfileProtocol` from `settings/__init__.py` and the package root
`__init__.py`. `StorageProfileProtocol` remains exported as today.

---

## 2. Connection Factory Widening

### `create_connection()` signature

Change the `profile` parameter type from `StorageProfileProtocol` to
`ProfileProtocol`:

```python
def create_connection(
    profile: ProfileProtocol,
    auth_profile: AuthProfile | None = None,
    *,
    auto_authorize: bool = False,
) -> ConnectionProtocol:
```

The factory only calls `profile.to_handler_kwargs()` (via the connection) and
reads `profile.__spec__.provider_type` (via `_provider_type_from_profile()`).
Neither requires `StorageProfileProtocol`.

### `_provider_type_from_profile()` signature

Widen from `StorageProfileProtocol` to `ProfileProtocol`:

```python
def _provider_type_from_profile(
    profile: ProfileProtocol,
) -> CONST_STORAGE_PROVIDER_TYPE | None:
```

The implementation is unchanged — it reads `__spec__` via `getattr`, which
works on any `Profile` subclass regardless of family.

### `create_tunnelled_connection()` signature

Widen `bastion_profile` and `target_profile` to `ProfileProtocol`:

```python
def create_tunnelled_connection(
    bastion_profile: ProfileProtocol,
    bastion_auth: AuthProfile | None,
    target_profile: ProfileProtocol,
    target_auth: AuthProfile | None,
    remote_host: str,
    remote_port: int,
) -> TunnelledConnection:
```

### `_PatchedEndpointProfile`

This wrapper in `connections/tunnel.py` patches host/port on a target profile.
It currently assumes `StorageProfileProtocol`. Widen to `ProfileProtocol` —
it only overrides `to_handler_kwargs()`, which is on the base protocol.

If `_PatchedEndpointProfile` also delegates `get_connection_url()`, keep that
delegation but make it conditional (only delegate if the wrapped profile has
the method). This avoids breaking storage profiles while allowing non-storage
profiles to be tunnelled.

---

## 3. Type Annotation Updates

All files that import `StorageProfileProtocol` solely for the
`to_handler_kwargs()` contract should switch to `ProfileProtocol`. Files that
use `get_connection_url()` keep `StorageProfileProtocol`.

Affected imports (switch to `ProfileProtocol`):
- `connections/__init__.py` — factory functions
- `connections/tunnel.py` — `_PatchedEndpointProfile`
- `connections/ssh.py` — constructor type hint (pre-#8 decoupling; #8 removes
  this entirely)
- `connections/http.py` — same
- `connections/s3.py` — same

Keep `StorageProfileProtocol`:
- `storage/facade/facade.py` — facade legitimately needs the storage contract
- `storage/registry/registry.py` — `get_storage_backend()` takes storage
  profiles
- `settings/storage/registry.py` — `STORAGE_REGISTRY` enforces storage
  protocol

---

## 4. No Registry Changes

`STORAGE_REGISTRY` keeps `profile_type=StorageProfileProtocol`. It correctly
enforces that only storage profiles register there. Future families create
their own registries with their own protocol constraints.

The `Registry` class in mountainash-settings is already generic — no changes
needed upstream.

---

## 5. Test Strategy

### Protocol conformance tests

```python
def test_profile_protocol_is_base_of_storage():
    """StorageProfileProtocol implementations satisfy ProfileProtocol."""
    profile = S3StorageProfile(FLAVOR="aws")
    assert isinstance(profile, ProfileProtocol)
    assert isinstance(profile, StorageProfileProtocol)

def test_minimal_profile_protocol():
    """A class with only to_handler_kwargs() satisfies ProfileProtocol."""
    class MinimalProfile:
        def to_handler_kwargs(self) -> dict:
            return {"host": "example.com"}
    assert isinstance(MinimalProfile(), ProfileProtocol)
    assert not isinstance(MinimalProfile(), StorageProfileProtocol)
```

### Factory acceptance tests

```python
def test_create_connection_accepts_profile_protocol():
    """Factory accepts any ProfileProtocol, not just StorageProfileProtocol."""
    # Mock a ProfileProtocol-only implementation with __spec__
    # Verify create_connection() calls to_handler_kwargs() and succeeds
```

### Registry enforcement tests

```python
def test_storage_registry_rejects_non_storage_protocol():
    """STORAGE_REGISTRY still requires StorageProfileProtocol."""
    # Attempt to register a ProfileProtocol-only class
    # Verify it raises TypeError/ValueError
```

### Existing tests

All existing storage profile and connection tests should pass unchanged —
`StorageProfileProtocol` is a superset of `ProfileProtocol`, so all storage
profiles satisfy both.

---

## Acceptance Criteria

1. `ProfileProtocol` exists in `settings/profile_protocol.py` with
   `to_handler_kwargs()` as its sole method.
2. `StorageProfileProtocol` inherits from `ProfileProtocol` and adds
   `get_connection_url()`.
3. `create_connection()` and `create_tunnelled_connection()` accept
   `ProfileProtocol` in their type signatures.
4. `STORAGE_REGISTRY` still enforces `StorageProfileProtocol` — non-storage
   profiles cannot register there.
5. All existing tests pass without modification.
6. New conformance tests verify the protocol hierarchy and factory acceptance.
