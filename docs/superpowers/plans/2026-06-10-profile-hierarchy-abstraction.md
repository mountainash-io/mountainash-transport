# Profile Hierarchy Abstraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract `ProfileProtocol` as the base protocol for all profiles, refine `StorageProfileProtocol` to inherit from it, and widen the connection factory to accept any `ProfileProtocol`.

**Architecture:** The existing `StorageProfileProtocol` is split into a base `ProfileProtocol` (with `to_handler_kwargs()`) and a storage refinement (adding `get_connection_url()`). Connection classes and factories widen their type hints from `StorageProfileProtocol` to `ProfileProtocol`. No runtime behaviour changes — this is purely a type-level refactoring.

**Tech Stack:** Python typing, `Protocol`, `runtime_checkable`, pytest

**Spec:** `docs/superpowers/specs/2026-06-10-profile-hierarchy-abstraction-design.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `src/mountainash_transport/settings/profile_protocol.py` | Extract `ProfileProtocol`, refine `StorageProfileProtocol` |
| Modify | `src/mountainash_transport/__init__.py` | Export `ProfileProtocol` |
| Modify | `src/mountainash_transport/connections/__init__.py` | Widen factory signatures to `ProfileProtocol` |
| Modify | `src/mountainash_transport/connections/ssh.py` | Widen `__init__` type hint |
| Modify | `src/mountainash_transport/connections/http.py` | Widen `__init__` type hint |
| Modify | `src/mountainash_transport/connections/s3.py` | Widen `__init__` type hint |
| Modify | `src/mountainash_transport/connections/tunnel.py` | Widen `_PatchedEndpointProfile`, conditional `get_connection_url()` |
| Modify | `tests/settings/test_profile_protocol.py` | Add `ProfileProtocol` conformance tests |
| Create | `tests/connections/test_factory_profile_protocol.py` | Factory acceptance tests for `ProfileProtocol`-only profiles |

---

### Task 1: Extract ProfileProtocol and Refine StorageProfileProtocol

**Files:**
- Modify: `src/mountainash_transport/settings/profile_protocol.py:1-21`
- Test: `tests/settings/test_profile_protocol.py`

- [ ] **Step 1: Write failing tests for the new protocol hierarchy**

Add to `tests/settings/test_profile_protocol.py`:

```python
from mountainash_transport.settings.profile_protocol import (
    ProfileProtocol,
    StorageProfileProtocol,
)


@pytest.mark.unit
class TestProfileProtocolHierarchy:
    def test_minimal_profile_satisfies_profile_protocol(self):
        """A class with only to_handler_kwargs() satisfies ProfileProtocol."""

        class MinimalProfile:
            def to_handler_kwargs(self) -> dict:
                return {"host": "example.com"}

        assert isinstance(MinimalProfile(), ProfileProtocol)

    def test_minimal_profile_does_not_satisfy_storage_protocol(self):
        """A ProfileProtocol-only class does NOT satisfy StorageProfileProtocol."""

        class MinimalProfile:
            def to_handler_kwargs(self) -> dict:
                return {"host": "example.com"}

        assert not isinstance(MinimalProfile(), StorageProfileProtocol)

    def test_storage_profile_satisfies_both_protocols(self):
        """StorageProfileProtocol implementations satisfy ProfileProtocol too."""
        from mountainash_auth_client import NoAuth
        from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
        from mountainash_transport.settings.storage.profiles import (
            LocalStorageProfile,
        )

        p = LocalStorageProfile(
            PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.LOCAL,
            ROOT_PATH="/tmp/files",
            auth=NoAuth(),
        )
        assert isinstance(p, ProfileProtocol)
        assert isinstance(p, StorageProfileProtocol)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/settings/test_profile_protocol.py::TestProfileProtocolHierarchy -v`
Expected: `ImportError: cannot import name 'ProfileProtocol'`

- [ ] **Step 3: Implement the protocol hierarchy**

Replace the entire contents of `src/mountainash_transport/settings/profile_protocol.py`:

```python
"""Profile protocols — base contract and storage-specific refinement.

``ProfileProtocol`` is the universal contract: every profile — storage,
messaging, connection — can produce SDK-ready kwargs via
``to_handler_kwargs()``.

``StorageProfileProtocol`` refines the base with ``get_connection_url()``
for diagnostics and logging.
"""

from __future__ import annotations

import typing as t

from typing import Protocol


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

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test tests/settings/test_profile_protocol.py -v`
Expected: ALL PASS (both existing `TestStorageProfile` and new `TestProfileProtocolHierarchy`)

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/settings/profile_protocol.py tests/settings/test_profile_protocol.py
git commit -m "feat: extract ProfileProtocol as base protocol for all profiles

StorageProfileProtocol now inherits from ProfileProtocol, adding
get_connection_url(). Both are runtime-checkable."
```

---

### Task 2: Export ProfileProtocol from Package Root

**Files:**
- Modify: `src/mountainash_transport/__init__.py:21-22,80-107`

- [ ] **Step 1: Add the export**

In `src/mountainash_transport/__init__.py`, add the import after the existing `ConnectionProtocol` import (line 21):

```python
from .settings.profile_protocol import ProfileProtocol, StorageProfileProtocol
```

Add both to `__all__`:

```python
"ProfileProtocol", "StorageProfileProtocol",
```

Place these entries after `"StorageDirectoryProtocol",` in the `__all__` list.

- [ ] **Step 2: Verify the export works**

Run: `hatch run test:test tests/test_public_api.py -v`
Expected: PASS (or skip if public API test doesn't assert on these names — check)

Also verify manually:

```bash
cd /home/nathanielramm/git/mountainash-io/mountainash/mountainash-utils-files
hatch run test:test -x -q --no-header 2>&1 | tail -5
```

Expected: no import errors

- [ ] **Step 3: Commit**

```bash
git add src/mountainash_transport/__init__.py
git commit -m "feat: export ProfileProtocol and StorageProfileProtocol from package root"
```

---

### Task 3: Widen Leaf Connection Type Hints

**Files:**
- Modify: `src/mountainash_transport/connections/ssh.py:9,14,33-36`
- Modify: `src/mountainash_transport/connections/http.py:15,18-21`
- Modify: `src/mountainash_transport/connections/s3.py:9,14-20`

- [ ] **Step 1: Run existing connection tests to establish baseline**

Run: `hatch run test:test tests/connections/test_ssh_connection.py tests/connections/test_http_connection.py tests/connections/test_s3_connection.py -v`
Expected: ALL PASS

- [ ] **Step 2: Update SSHConnection**

In `src/mountainash_transport/connections/ssh.py`, change the import (line 14):

```python
from mountainash_transport.settings.profile_protocol import ProfileProtocol
```

Remove the old import:
```python
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
```

Change the `__init__` type hint (line 36):

```python
    def __init__(
        self,
        profile: ProfileProtocol,
        auth_strategy: AuthStrategy,
    ) -> None:
```

- [ ] **Step 3: Update HTTPConnection**

In `src/mountainash_transport/connections/http.py`, change the import (line 15):

```python
from mountainash_transport.settings.profile_protocol import ProfileProtocol
```

Remove the old import:
```python
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
```

Change the `__init__` type hint (line 22):

```python
    def __init__(
        self,
        profile: ProfileProtocol,
        auth_strategy: AuthStrategy,
    ) -> None:
```

- [ ] **Step 4: Update S3Connection**

In `src/mountainash_transport/connections/s3.py`, change the import:

```python
from mountainash_transport.settings.profile_protocol import ProfileProtocol
```

Remove the old import:
```python
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
```

Change the `__init__` type hint:

```python
    def __init__(
        self,
        profile: ProfileProtocol,
        auth_strategy: AuthStrategy,
    ) -> None:
```

- [ ] **Step 5: Re-run connection tests**

Run: `hatch run test:test tests/connections/test_ssh_connection.py tests/connections/test_http_connection.py tests/connections/test_s3_connection.py -v`
Expected: ALL PASS (existing test mocks implement both `to_handler_kwargs` and `get_connection_url`, so they satisfy `ProfileProtocol`)

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/connections/ssh.py src/mountainash_transport/connections/http.py src/mountainash_transport/connections/s3.py
git commit -m "refactor: widen leaf connection type hints from StorageProfileProtocol to ProfileProtocol"
```

---

### Task 4: Widen Connection Factory and Tunnel

**Files:**
- Modify: `src/mountainash_transport/connections/__init__.py:8,39-46,69-101,103-121`
- Modify: `src/mountainash_transport/connections/tunnel.py:81-105`
- Test: `tests/connections/test_factory_profile_protocol.py` (new)

- [ ] **Step 1: Write a test that a ProfileProtocol-only profile works with the factory**

Create `tests/connections/test_factory_profile_protocol.py`:

```python
"""Tests that create_connection() accepts ProfileProtocol-only profiles."""
from __future__ import annotations

import pytest

from mountainash_transport.connections import create_connection
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.connections.null import NullConnection
from mountainash_transport.settings.profile_protocol import ProfileProtocol


class BareHTTPProfile:
    """ProfileProtocol-only — no get_connection_url()."""

    class __spec__:
        provider_type = "http"

    def to_handler_kwargs(self) -> dict:
        return {"timeout": 30}


class BareLocalProfile:
    """ProfileProtocol-only — no get_connection_url()."""

    class __spec__:
        provider_type = "local"

    def to_handler_kwargs(self) -> dict:
        return {}


@pytest.mark.unit
class TestFactoryAcceptsProfileProtocol:
    def test_bare_profile_satisfies_profile_protocol(self):
        assert isinstance(BareHTTPProfile(), ProfileProtocol)

    def test_bare_http_profile_creates_http_connection(self):
        conn = create_connection(BareHTTPProfile())
        assert isinstance(conn, HTTPConnection)

    def test_bare_local_profile_creates_null_connection(self):
        conn = create_connection(BareLocalProfile())
        assert isinstance(conn, NullConnection)
```

- [ ] **Step 2: Run to verify it fails (or passes — the runtime doesn't enforce type hints)**

Run: `hatch run test:test tests/connections/test_factory_profile_protocol.py -v`
Expected: likely PASS already (Python doesn't enforce type annotations at runtime), but we need the annotation changes for mypy and correctness.

- [ ] **Step 3: Update the factory import and signatures**

In `src/mountainash_transport/connections/__init__.py`:

Change the import (line 8):
```python
from mountainash_transport.settings.profile_protocol import ProfileProtocol
```

Remove:
```python
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
```

Change `_provider_type_from_profile` signature (line 39):
```python
def _provider_type_from_profile(profile: ProfileProtocol) -> CONST_STORAGE_PROVIDER_TYPE | None:
```

Change `_connection_for_provider` signature (line 62):
```python
def _connection_for_provider(profile: ProfileProtocol) -> type:
```

Change `create_connection` signature (line 69):
```python
def create_connection(
    profile: ProfileProtocol,
    auth_profile: AuthProfile | None = None,
    *,
    auto_authorize: bool = False,
) -> ConnectionProtocol:
```

Change `create_tunnelled_connection` signature (line 103):
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

- [ ] **Step 4: Update `_PatchedEndpointProfile` in tunnel.py**

In `src/mountainash_transport/connections/tunnel.py`, change the class (lines 81-105):

```python
class _PatchedEndpointProfile:
    """Wraps a profile, replacing endpoint kwargs with the tunnel's local address."""

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
        if hasattr(self._inner, "get_connection_url"):
            return f"tunnel://{self._host}:{self._port}"
        return f"tunnel://{self._host}:{self._port}"

    def __getattr__(self, name: str) -> t.Any:
        return getattr(self._inner, name)
```

The `get_connection_url` method stays (to satisfy `StorageProfileProtocol` when wrapping storage profiles), but the class no longer imports or depends on `StorageProfileProtocol`.

- [ ] **Step 5: Run all connection tests**

Run: `hatch run test:test tests/connections/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/connections/__init__.py src/mountainash_transport/connections/tunnel.py tests/connections/test_factory_profile_protocol.py
git commit -m "refactor: widen connection factory and tunnel to accept ProfileProtocol"
```

---

### Task 5: Run Full Test Suite and Type Check

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `hatch run test:test -v`
Expected: ALL PASS — no existing tests should break

- [ ] **Step 2: Run mypy**

Run: `hatch run mypy:check`
Expected: PASS (or existing issues only — no new errors from our changes)

- [ ] **Step 3: Run ruff**

Run: `hatch run ruff:check`
Expected: PASS

- [ ] **Step 4: Commit any fixups if needed, then done**

If linting or typing found issues, fix and commit:
```bash
git add -A
git commit -m "fix: resolve lint/type issues from profile hierarchy extraction"
```
