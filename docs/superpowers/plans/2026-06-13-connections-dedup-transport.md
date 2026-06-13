# Connections Dedup — transport consumer (Part B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete transport's stale OAuth-flow / callback-server / protocol fork and collapse transport's OAuth connections onto auth-client's resolvers (`OAuthFlow.resolve_access_token`, `OAuth1Flow.resolve_token_pair`), keeping only the genuinely storage-specific binding (resolved token → `emit(HTTP, base=to_handler_kwargs())` → transport `HTTPConnection`).

**Architecture:** auth-client (PR #6, merged to develop, v26.6.0) is the single source of truth for the OAuth lifecycle + callback servers. Transport's `connect()` becomes: resolve via the auth-client flow → bind onto the storage endpoint's httpx config → connect inner HTTPConnection. The duplicated lifecycle (`_resolve_token`/`_resolve_kwargs`) and the stale `flow.py`/`server/`/`protocols/` modules are removed; the public re-exports repoint to auth-client.

**Tech Stack:** Python 3.12, httpx, mountainash-auth-client 26.6.0 (provides the resolvers), pydantic SecretStr, pytest, ruff.

**Repo / branch:** `mountainash-utils-files`. Branch `feature/connections-dedup-transport` off **`origin/develop`** (Phase 3 PR #70 is merged there at `b22a619`; `_core/auth` is already gone). The transport `.venv` has already been refreshed to auth-client **26.6.0** (both resolvers importable).

**Spec:** `docs/superpowers/specs/2026-06-13-connections-dedup-design.md` (Part B). **Prerequisite (done):** auth-client Part A, merged.

---

## Settled decisions (baked into this plan — do not re-litigate)

1. **AuthorizationRequired translation.** The auth-client resolver raises `mountainash_auth_client.errors.AuthorizationRequired`. Transport's public contract (`test_errors.py:120` asserts `issubclass(AuthorizationRequired, TransportConnectionError)`; it is re-exported from `connections`) must be preserved. So each collapsed `connect()` **catches auth-client's `AuthorizationRequired` and re-raises transport's** (`connections.errors.AuthorizationRequired`). Transport's `errors.py` is **unchanged** (AuthorizationRequired / TokenExchangeError / TokenRefreshError all remain — public + tested by `test_errors.py`, even though only AuthorizationRequired now has an internal raiser).

2. **OAuth1 CONSUMER_SECRET passed through as SecretStr** (spec D-note / Codex F5): `OAuth1AuthProfile(CONSUMER_SECRET=self._auth.CONSUMER_SECRET, ...)` — do NOT `.get_secret_value()`. The plaintext is unwrapped only inside the adapter. This requires the OAuth1 connection test's fake auth to expose a real `pydantic.SecretStr` (the current fake object would fail the SecretStr field).

3. **Drop all three transport protocol defs** (`OAuth2FlowProtocol`, `OAuth1FlowProtocol`, `CallbackServerProtocol`) and their conformance test groups. Auth-client has no flow protocols, and its `CallbackServerProtocol` diverged (`obtain_callback` vs transport's `wait_for_callback`). Post-dedup the implementations live in auth-client, which owns/tests its own protocols. Remove the three names from `connections.__all__`. (Not pinned by `tests/test_public_api.py`.)

4. **Repoint, don't re-implement.** `OAuthFlow`, `OAuth1Flow`, `LocalCallbackServer`, `extract_code_from_input`, `prompt_for_code` re-export directly from `mountainash_auth_client.connections...` (every name has a direct auth-client source). Note: auth-client's **top-level** `connections/__init__` does NOT export `OAuth1Flow` — import it from `mountainash_auth_client.connections.oauth1.flow`.

---

## File Structure

**Collapse (edit):**
- `src/mountainash_transport/connections/oauth2/connection.py` — `connect()` delegates to `OAuthFlow.resolve_access_token`; delete `_resolve_token`; repoint `OAuthFlow` import to auth-client; add aliased auth-client `AuthorizationRequired`; drop `get_secrets_backend` import.
- `src/mountainash_transport/connections/oauth1/connection.py` — `connect()` delegates to `OAuth1Flow.resolve_token_pair`; delete `_resolve_kwargs`; SecretStr pass-through; repoint import; translate; drop `get_secrets_backend`.

**Repoint (edit):**
- `src/mountainash_transport/connections/__init__.py` — repoint OAuthFlow/OAuth1Flow/LocalCallbackServer/manual fns to auth-client; remove the `from .protocols import (...)` block; remove the three protocol names from imports + `__all__`.
- `src/mountainash_transport/connections/oauth2/__init__.py` — repoint `OAuthFlow` to auth-client.
- `src/mountainash_transport/connections/oauth1/__init__.py` — repoint `OAuth1Flow` to auth-client.

**Delete (src):**
- `src/mountainash_transport/connections/oauth2/flow.py`
- `src/mountainash_transport/connections/oauth1/flow.py`
- `src/mountainash_transport/connections/server/` (whole package: `__init__.py`, `callback.py`, `manual.py`)
- `src/mountainash_transport/connections/protocols/` (whole package: `__init__.py`, `prtcl_oauth2_flow.py`, `prtcl_oauth1_flow.py`, `prtcl_callback.py`)

**Tests (edit):**
- `tests/connections/oauth2/test_connection.py` — repoint the `OAuthFlow` import to auth-client (line 13).
- `tests/connections/oauth1/test_connection.py` — make `FakeOAuth1Auth.CONSUMER_SECRET` a real `SecretStr`.
- `tests/connections/test_protocol_shapes.py` — remove the `connections.protocols` import + the three flow/callback conformance groups (+ their Good/Bad/Fake helper classes); keep the `ConnectionProtocol` group.

**Tests (delete):**
- `tests/connections/oauth2/test_flow.py`
- `tests/connections/oauth1/test_flow.py`
- `tests/connections/server/` (whole package: `__init__.py`, `test_server.py`)

**Add (test):**
- `tests/connections/oauth2/test_connection.py` + `oauth1/test_connection.py` — golden-parity tests proving the resolved token binds onto the storage profile's `to_handler_kwargs()` (granular config like `verify`/timeout survives).

---

### Task 1: Collapse `OAuth2Connection` onto the resolver

**Files:**
- Modify: `src/mountainash_transport/connections/oauth2/connection.py`
- Test: `tests/connections/oauth2/test_connection.py`

- [ ] **Step 1: Refactor the connection module**

Replace the import block (current lines 10-20) so it imports `OAuthFlow` from auth-client, adds an aliased auth-client `AuthorizationRequired`, and drops `get_secrets_backend`:

```python
from mountainash_auth_client import TokenAuthProfile
from mountainash_auth_client.targets import TargetFamily
from mountainash_auth_client.errors import AuthorizationRequired as AuthClientAuthorizationRequired
from mountainash_auth_client.connections.oauth2.flow import OAuthFlow
from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol

if t.TYPE_CHECKING:
    from mountainash_auth_client.schemas.oauth2 import OAuth2AuthProfile
    from mountainash_auth_client.schemas.oauth2_authcode import OAuth2AuthCodeAuthProfile
```

Replace `connect()` and DELETE `_resolve_token()` entirely:

```python
    def connect(self) -> Self:
        try:
            access_token = OAuthFlow(self._spec).resolve_access_token(
                self._auth, auto_authorize=self._auto_authorize
            )
        except AuthClientAuthorizationRequired:
            # Preserve transport's public error contract (TransportConnectionError
            # subclass); the resolver raises auth-client's distinct class.
            raise AuthorizationRequired(provider=self._spec.name, user="default")
        merged = TokenAuthProfile(TOKEN=access_token).emit(
            TargetFamily.HTTP, base=self._profile.to_handler_kwargs()
        )
        self._inner = HTTPConnection(merged)
        self._inner.connect()
        return self
```

Leave `__init__`, `disconnect`, `client`, `is_connected`, `__enter__`, `__exit__` unchanged.

- [ ] **Step 2: Repoint the test's OAuthFlow import**

In `tests/connections/oauth2/test_connection.py`, change line 13:

```python
from mountainash_auth_client.connections.oauth2.flow import OAuthFlow
```

(The `patch.object(OAuthFlow, "is_expired"/"refresh")` calls now patch auth-client's flow, which `connect()` instantiates. The `pytest.raises(AuthorizationRequired)` assertions use transport's class — preserved by the translation. No other change needed.)

- [ ] **Step 3: Add a golden-parity test**

Append to `tests/connections/oauth2/test_connection.py` a test proving the resolved token binds onto richer storage config (not just `timeout`). Add this class:

```python
class TestOAuth2StorageConfigParity:
    """The resolved token must bind onto the storage profile's full httpx
    config — granular settings (verify/timeout) survive into the inner client."""

    def test_storage_config_survives_token_binding(self, memory_backend):
        memory_backend.set("test.oauth2", {
            "access_token": "PARITYTOK",
            "token_expires_at": 9999999999,
        })

        class RichProfile:
            __spec__ = FakeOAuth2Spec()

            def to_handler_kwargs(self, auth_profile=None) -> dict:
                return {"timeout": 30, "verify": False, "follow_redirects": True}

            def get_connection_url(self) -> str:
                return "https://api.example.com"

        conn = OAuth2Connection(RichProfile(), FakeOAuth2Auth())
        with patch("mountainash_transport.connections.http.httpx.Client"):
            conn.connect()
        kw = conn._inner._connect_kwargs
        assert kw["headers"]["Authorization"] == "Bearer PARITYTOK"
        assert kw["verify"] is False
        assert kw["follow_redirects"] is True
        assert kw["timeout"] == 30
```

- [ ] **Step 4: Run the OAuth2 connection tests**

Run: `hatch run test:test tests/connections/oauth2/test_connection.py -v`
Expected: all pass (8 lifecycle + protocol + new parity test). In particular `test_connect_raises_when_no_token_and_not_auto`, `test_empty_cached_token_raises` (transport `AuthorizationRequired` via translation), `test_missing_access_token_key_raises_token_exchange_error` (KeyError propagates through the translation — only `AuthClientAuthorizationRequired` is caught).

> NOTE: do not delete `tests/connections/oauth2/test_flow.py` yet — Task 4 owns deletions. `connections/__init__.py` still imports the old transport `flow.py` at this point, so the package still imports cleanly.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/connections/oauth2/connection.py tests/connections/oauth2/test_connection.py
git commit -m "refactor: collapse OAuth2Connection onto auth-client resolver"
```

---

### Task 2: Collapse `OAuth1Connection` onto the resolver

**Files:**
- Modify: `src/mountainash_transport/connections/oauth1/connection.py`
- Test: `tests/connections/oauth1/test_connection.py`

- [ ] **Step 1: Refactor the connection module**

Replace the import block (current lines 10-16) so it imports `OAuth1Flow` from auth-client, adds the aliased auth-client `AuthorizationRequired`, and drops `get_secrets_backend`:

```python
from mountainash_auth_client import OAuth1AuthProfile
from mountainash_auth_client.targets import TargetFamily
from mountainash_auth_client.errors import AuthorizationRequired as AuthClientAuthorizationRequired
from mountainash_auth_client.connections.oauth1.flow import OAuth1Flow
from mountainash_transport.connections.errors import AuthorizationRequired
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
```

Replace `connect()` and DELETE `_resolve_kwargs()` entirely:

```python
    def connect(self) -> Self:
        try:
            oauth_token, oauth_token_secret = OAuth1Flow(self._spec).resolve_token_pair(
                self._auth, auto_authorize=self._auto_authorize
            )
        except AuthClientAuthorizationRequired:
            raise AuthorizationRequired(provider=self._spec.name, user="default")
        emitter = OAuth1AuthProfile(
            CONSUMER_KEY=self._auth.CONSUMER_KEY,
            CONSUMER_SECRET=self._auth.CONSUMER_SECRET,  # SecretStr through; do NOT unwrap
            ACCESS_TOKEN=oauth_token,
            ACCESS_TOKEN_SECRET=oauth_token_secret,
        )
        merged = emitter.emit(TargetFamily.HTTP, base=self._profile.to_handler_kwargs())
        self._inner = HTTPConnection(merged)
        self._inner.connect()
        return self
```

Leave the rest unchanged.

- [ ] **Step 2: Make the test fake's CONSUMER_SECRET a real SecretStr**

In `tests/connections/oauth1/test_connection.py`, the connection now passes `CONSUMER_SECRET` straight into `OAuth1AuthProfile` (a `SecretStr` field), so the fake must expose a real `SecretStr`. Add the import and change `FakeOAuth1Auth`:

```python
from pydantic import SecretStr
```

```python
class FakeOAuth1Auth:
    CONSUMER_KEY = "consumer_key"
    CONSUMER_SECRET = SecretStr("consumer_secret")
    SETTINGS_SOURCE_SECRETS_PROVIDER = "test_mem"

    def persist_key(self):
        return "test.oauth1"
```

(Replaces the previous `property(lambda self: type("S", ...)())` form. The real `OAuth1AuthProfile.CONSUMER_SECRET` is a `SecretStr`, so this fake is now more faithful, not less.)

- [ ] **Step 3: Add a golden-parity test**

Append to `tests/connections/oauth1/test_connection.py`:

```python
class TestOAuth1StorageConfigParity:
    def test_storage_config_survives_oauth1_binding(self, memory_backend):
        import sys
        mock_authlib_module = MagicMock()
        mock_authlib_module.OAuth1Auth = MagicMock()
        sys.modules["authlib.integrations.httpx_client"] = mock_authlib_module
        try:
            memory_backend.set("test.oauth1", {
                "oauth_token": "OT", "oauth_token_secret": "OTS",
            })

            class RichProfile:
                __spec__ = FakeOAuth1Spec()

                def to_handler_kwargs(self, auth_profile=None) -> dict:
                    return {"timeout": 30, "verify": False}

                def get_connection_url(self) -> str:
                    return "https://api.example.com"

            conn = OAuth1Connection(RichProfile(), FakeOAuth1Auth())
            with patch("mountainash_transport.connections.http.httpx.Client"):
                conn.connect()
            kw = conn._inner._connect_kwargs
            assert kw["verify"] is False
            assert kw["timeout"] == 30
            assert "auth" in kw  # OAuth1 signer attached
        finally:
            sys.modules.pop("authlib.integrations.httpx_client", None)
```

- [ ] **Step 4: Run the OAuth1 connection tests**

Run: `hatch run test:test tests/connections/oauth1/test_connection.py -v`
Expected: all pass (`test_connect_raises_when_no_token_and_not_auto` via translation; `test_connect_with_stored_tokens` with the SecretStr fake; new parity test).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/connections/oauth1/connection.py tests/connections/oauth1/test_connection.py
git commit -m "refactor: collapse OAuth1Connection onto auth-client resolver"
```

---

### Task 3: Repoint the re-exports to auth-client

**Files:**
- Modify: `src/mountainash_transport/connections/__init__.py`
- Modify: `src/mountainash_transport/connections/oauth2/__init__.py`
- Modify: `src/mountainash_transport/connections/oauth1/__init__.py`

- [ ] **Step 1: Repoint `connections/__init__.py`**

Replace the legacy-import block (current lines 12-23) with auth-client sources and DROP the protocols import:

```python
# --- Legacy/existing public API (kept for backward compat) -------------------
from .errors import (
    ConnectionError, TokenExchangeError, TokenRefreshError, AuthorizationRequired,
    TransportConnectionError, ConnectionTimeoutError,
)
from mountainash_auth_client.connections.oauth2.flow import OAuthFlow
from mountainash_auth_client.connections.oauth1.flow import OAuth1Flow
from mountainash_auth_client.connections.server.callback import LocalCallbackServer
from mountainash_auth_client.connections.server.manual import (
    extract_code_from_input, prompt_for_code,
)
```

In `__all__`, REMOVE the lines `"OAuth2FlowProtocol", "OAuth1FlowProtocol",` and `"CallbackServerProtocol",` (current lines 165-166). Keep `OAuthFlow`, `OAuth1Flow`, `LocalCallbackServer`, `extract_code_from_input`, `prompt_for_code`, and all the error names. Everything below (the connection-class imports, factory functions, maps) is unchanged.

- [ ] **Step 2: Repoint `oauth2/__init__.py`**

```python
from __future__ import annotations

from mountainash_auth_client.connections.oauth2.flow import OAuthFlow
from mountainash_transport.connections.oauth2.connection import OAuth2Connection

__all__ = ["OAuthFlow", "OAuth2Connection"]
```

- [ ] **Step 3: Repoint `oauth1/__init__.py`**

```python
from __future__ import annotations

from mountainash_auth_client.connections.oauth1.flow import OAuth1Flow
from mountainash_transport.connections.oauth1.connection import OAuth1Connection

__all__ = ["OAuth1Flow", "OAuth1Connection"]
```

- [ ] **Step 4: Verify the package still imports + public surface**

Run: `hatch run test:test tests/test_public_api.py tests/connections/test_factory.py -v`
Expected: pass. The public surface still exposes `OAuthFlow`/`OAuth1Flow`/`LocalCallbackServer`/`extract_code_from_input`/`prompt_for_code` (now auth-client's). The transport `flow.py`/`server/`/`protocols/` modules are now unreferenced by `connections/__init__.py` (Task 4 deletes them).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/connections/__init__.py src/mountainash_transport/connections/oauth2/__init__.py src/mountainash_transport/connections/oauth1/__init__.py
git commit -m "refactor: repoint connection re-exports to auth-client"
```

---

### Task 4: Delete the stale forks + drop the protocol layer

**Files:**
- Delete (src): `connections/oauth2/flow.py`, `connections/oauth1/flow.py`, `connections/server/` (dir), `connections/protocols/` (dir)
- Delete (test): `tests/connections/oauth2/test_flow.py`, `tests/connections/oauth1/test_flow.py`, `tests/connections/server/` (dir)
- Modify (test): `tests/connections/test_protocol_shapes.py`

- [ ] **Step 1: Confirm nothing still imports the doomed modules**

Run (must return ONLY the files being deleted, no live importers):

```bash
grep -rn "connections.oauth2.flow\|connections.oauth1.flow\|connections.server\|connections.protocols\|from .flow import\|from .protocols import\|from .server" src/ tests/ | grep -v "mountainash_auth_client"
```

If any live src/test file OTHER than the ones slated for deletion/edit still references these, STOP and report — the repoint (Task 3) or test edits are incomplete.

- [ ] **Step 2: Delete the stale src modules**

```bash
git rm src/mountainash_transport/connections/oauth2/flow.py \
       src/mountainash_transport/connections/oauth1/flow.py
git rm -r src/mountainash_transport/connections/server \
          src/mountainash_transport/connections/protocols
```

- [ ] **Step 3: Delete the mirrored tests**

```bash
git rm tests/connections/oauth2/test_flow.py \
       tests/connections/oauth1/test_flow.py
git rm -r tests/connections/server
```

- [ ] **Step 4: Trim `test_protocol_shapes.py`**

Remove the now-broken `connections.protocols` import (current lines 9-12) and DELETE the three protocol conformance sections in their entirety: `OAuth2FlowProtocol` (helper classes `GoodOAuth2Flow`/`BadOAuth2Flow` + `class TestOAuth2FlowProtocol`), `OAuth1FlowProtocol` (`GoodOAuth1Flow`/`BadOAuth1Flow` + `TestOAuth1FlowProtocol`), and `CallbackServerProtocol` (`GoodCallbackServer`/`BadCallbackServer` + `TestCallbackServerProtocol`). Also remove any now-unused `FakeOAuth2Spec`/`FakeOAuth1Spec` helper classes that were defined in this file solely for those groups (check usage before removing). **Keep** the `ConnectionProtocol` import (line 6) and the entire `TestConnectionProtocolConformance` group (and its imports of `HTTPConnection`/`NullConnection`).

Rationale: these protocols described transport's now-deleted flow/callback implementations. With the implementations moved to auth-client (which owns and tests its own protocols), transport re-asserting their shapes is redundant — and auth-client's `CallbackServerProtocol` genuinely diverged (`obtain_callback`).

- [ ] **Step 5: Remove orphaned conftest fixtures (if any)**

Check whether `tests/connections/conftest.py`'s OAuth fixtures (`fake_oauth2_spec`, `fake_oauth1_spec`, `fake_oauth2_auth`, `fake_oauth1_auth`, the shared `memory_backend`) are still referenced by any remaining test:

```bash
grep -rn "fake_oauth2_spec\|fake_oauth1_spec\|fake_oauth2_auth\|fake_oauth1_auth" tests/
```

The retained connection tests define their OWN inline fixtures, so these conftest fixtures are likely orphaned by the flow/server test deletions. If `grep` shows no remaining users, remove the orphaned fixtures (and their helper classes) from `conftest.py`. If anything still uses them, leave them. Do NOT remove fixtures that other (non-OAuth) tests in `tests/connections/` rely on — verify first.

- [ ] **Step 6: Run the connections suite**

Run: `hatch run test:test tests/connections/ -v`
Expected: all pass; no import errors from the deleted modules; `test_protocol_shapes.py` runs only the `ConnectionProtocol` group.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: delete stale OAuth flow/callback/protocol fork (now auth-client's)"
```

---

### Task 5: Full suite + lint + types + parity confirmation

**Files:** none (verification + any fixups).

- [ ] **Step 1: Full test suite**

Run: `hatch run test:test -q`
Expected: all pass. Pay attention to `tests/connections/test_emission_golden.py` (Phase 3 golden tests — must still pass) and `tests/storage_facade/` (facade builds connections via `create_connection`).

- [ ] **Step 2: Lint**

Run: `hatch run ruff:check`
Expected: clean. Remove any now-unused imports the deletions left behind (e.g. in `connections/__init__.py`, the OAuth connection modules).

- [ ] **Step 3: Type check**

Run: `hatch run mypy:check`
Expected: no NEW errors versus the develop baseline. The collapsed `connect()` methods and repointed imports must type-check; the aliased `AuthClientAuthorizationRequired` is a concrete exception class.

- [ ] **Step 4: Grep for dangling references**

Run:

```bash
grep -rn "OAuth2FlowProtocol\|OAuth1FlowProtocol\|_resolve_token\|_resolve_kwargs" src/ tests/
```

Expected: NO matches in src (the protocols are gone; the private resolve methods are deleted). If a test still references them, it was missed.

- [ ] **Step 5: Commit any fixups**

```bash
git add -A
git commit -m "chore: lint/type fixups for connections dedup (transport)"
```

---

## Self-Review Checklist (controller runs before dispatch)

1. **Spec coverage (Part B):** delete flow.py×2 + server/ + protocols/ (Task 4); collapse OAuth2/OAuth1 connections onto resolvers (Tasks 1-2); repoint re-exports (Task 3); golden parity (Tasks 1-2 parity tests); error handling preserved via translation (Tasks 1-2). ✅
2. **Settled decisions honored:** translation (Tasks 1-2), SecretStr pass-through + fake update (Task 2), drop-all-three protocols (Tasks 3-4). ✅
3. **Sequencing:** collapse + repoint BEFORE deletion (Tasks 1-3 then 4) so the package never has a dangling import mid-plan — same lesson as Phase 3. ✅
4. **Test integrity:** deleted flow/server tests are auth-client's responsibility now (covered there); deleted protocol conformance groups described deleted implementations; nothing silenced to force a pass. ✅
5. **Type/name consistency:** `AuthClientAuthorizationRequired` alias used in both connections; `resolve_access_token -> str`, `resolve_token_pair -> tuple[str,str]` match Part A. ✅

---

## Risks

- **Public-surface reduction:** removes `OAuth2FlowProtocol`/`OAuth1FlowProtocol`/`CallbackServerProtocol` from `connections.__all__`. Verified: no transport src type-hints use them; `test_public_api.py` does not pin them. Deliberate (decision 3).
- **Env staleness:** requires transport `.venv` on auth-client 26.6.0 (already refreshed; both resolvers importable). If a clean CI env reinstalls auth-client, ensure it resolves ≥26.6.0.
- **OAuth1 SecretStr:** the real `OAuth1AuthProfile.CONSUMER_SECRET` is a `SecretStr`, so the pass-through is correct in production; the fake is updated to match. If any other caller constructed `OAuth1Connection` with a non-SecretStr consumer secret, it would now fail the field — none found in repo.
