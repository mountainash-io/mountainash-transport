# Unified Emission — Phase 3 (Transport Wiring + `_core/auth` Deletion) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace transport's duplicated `_core/auth` strategy/resolver engine with the unified `profile.emit(target)` primitive landed in Phases 1–2, so credential injection becomes a single declarative call per leaf connection.

**Architecture:** The factory (`connections/__init__.py`) stops calling `resolve_auth_strategy(...).apply(kwargs)` and instead calls `auth_profile.emit(family, base=profile.to_handler_kwargs())`, where `family` is a `TargetFamily` derived from the provider type. Leaf connections (`HTTP`/`S3`/`SSH`) become pure dict consumers. OAuth2/OAuth1 connections (the spec's "flow-owned" path) resolve credentials dynamically, then construct a `TokenAuthProfile`/`OAuth1AuthProfile` and `emit()`. The `resolver.py` + 8 concrete static strategies + their tests are deleted; the `AuthStrategy`/`RefreshableAuthStrategy` *protocols* (live in the HTTP engine's 401-refresh path; no concrete implementer yet — forward-looking scaffolding) relocate to `_core/http/`.

**Tech Stack:** Python 3.12, pydantic v2, `mountainash-settings` (`Profile.emit`), `mountainash-auth-client` (`TargetFamily`, `*Profile` adapters), boto3, httpx, paramiko, pytest, hatch.

**Governing spec:** `mountainash-auth-client/docs/superpowers/specs/2026-06-12-unified-profile-kwargs-emission-design.md` (Phase 3 section + "Connection composition model" + "BOTO credential layering").

---

## Critical environment + naming preconditions (read before starting)

Two facts (verified during planning) shape task ordering:

1. **Transport's hatch `test` env is STALE.** It serves a pre-Phase-2 `mountainash-auth-client` (no `TargetFamily`, no `Profile.emit`) and a pre-Phase-1 `mountainash-settings`, because uv caches path-dep wheels by version and neither version bumped. Phase 3 is **untestable** until both wheels are rebuilt and reinstalled into the transport test-env venv (Task 2). See memory `transport_env_staleness_and_profile_rename`.

2. **Merged auth-client uses `*Profile` class names only** (`TokenAuthProfile`, `IAMAuthProfile`, `OAuth1AuthProfile`, `OAuth2AuthProfile`, `OAuth2AuthCodeAuthProfile`, `NoAuthProfile`, `KerberosAuthProfile`, `JWTAuthProfile`, `PasswordAuthProfile`, …). There are **no short aliases** (`TokenAuth`, `OAuth2Auth`, …). Every code example below uses `*Profile` names. Transport's surviving short-name imports (factory `__init__.py:78,84`; `oauth1/connection.py:18`; `oauth2/connection.py:18-19`) must migrate to `*Profile` as part of this phase. The `schemas/<mode>.py` module *paths* are unchanged — only the class symbol renamed.

**Consequence for golden capture:** the pre-refactor resolver runs only on the *stale* env (it imports short names). Task 1 captures golden values **on the current env, before Task 2's refresh**. The captured literals are env-independent strings/dicts.

**EXECUTION ORDER OVERRIDE (discovered during the Task 2 refresh — supersedes the task numbering below).** After the env refresh, `tests/conftest.py` imports the transport package, which runs `connections/__init__.py`, which imports `_core/auth/resolver.py` at module load — and `resolver.py`'s *module-level* short-name auth imports (`CertificateAuth`, …) now raise `ImportError`, so **the entire test suite fails to collect**. (The factory's own short-name imports at `__init__.py:78,84` are function-local and harmless; only `resolver.py` breaks package import.) Therefore execute in this order:

1. Task 1 — golden capture (stale env). 2. Task 2 — env refresh. **3. Task 4 — leaves dict-only + factory emit (this removes the `resolver` import from `connections/__init__.py` and is what makes the package importable again).** 4. Task 2b — test-name migration (now `tests/settings` can collect). 5. Task 3 — protocol relocation. 6. Task 5 — OAuth. 7. Task 6 — delete `_core/auth`. 8. Task 7 — golden tests. 9. Task 8 — full suite/lint/type.

Note for the implementer of Task 4 Step 2: on the refreshed env the "expected failure" of the new factory test surfaces first as the package-level `ImportError` (resolver short names), not the clean `_family_for_provider` ImportError — red is still red; proceed to implement Steps 3–5, after which the package imports and the test passes.

---

## Design Decisions (resolve the spec's deferred Phase-3 choices)

- **D1 — Deletion boundary.** Delete `_core/auth/{resolver,strategies,__init__}.py` and `tests/_core/auth/` (the resolver/strategy unit tests). The `AuthStrategy`/`RefreshableAuthStrategy` **protocols** survive (HTTP engine 401-refresh seam + HTTP backend type hint; no concrete `RefreshableAuthStrategy` implementer yet — deliberate forward-looking scaffolding, not dead code). They relocate to `_core/http/auth_protocol.py`.

- **D2 — Leaf connections become dict-only.** `HTTPConnection`/`S3Connection`/`SSHConnection` drop the `auth_strategy` parameter and the `.apply()` call; they receive fully-merged `connect_kwargs`.

- **D3 — Provider → family mapping.** `_family_for_provider(provider_type) -> TargetFamily | None`: `HTTP→HTTP`; `S3/S3EXPRESS/R2/MINIO/B2→BOTO`; `SSH/SFTP→PARAMIKO`; `LOCAL`/unmapped→`None` (no emission; kwargs pass through).

- **D4 — None/NoAuth pass-through.** When `auth_profile is None` or is a `NoAuthProfile`, the factory does **not** call `emit()` — it uses `profile.to_handler_kwargs()` verbatim (mirrors the old `NoAuthStrategy` passthrough exactly).

- **D5 — BOTO credential layering (S3 assume-role envelope).** When `to_handler_kwargs()` returns the nested `{"base_kwargs": ..., "role_arn": ..., "session_name": ...}` shape (set when `ROLE_ARN` present), the factory emits credentials onto `kwargs["base_kwargs"]` (copy-on-write) and leaves `role_arn`/`session_name` untouched. **Scope note (re: STS execution):** actually *consuming* this envelope at connect time (calling STS AssumeRole, building the client from temporary creds) is **pre-existing-unimplemented** — `S3Connection.connect()` does not unwrap it today, and Phase 3 does **not** add that. Phase 3 guarantees only the credential *layering* the spec calls for. The unimplemented assume-role execution is recorded as a known gap (Task 7 Step 2 docstring) for a future phase, consistent with the theatrical-wiring principle (don't delete the scaffolding; don't scope-creep its completion into this phase).

- **D6 — Flow-owned OAuth uses construct-and-emit.** `OAuth2Connection`: resolve access token → `TokenAuthProfile(TOKEN=token).emit(TargetFamily.HTTP, base=...)`. `OAuth1Connection`: resolve tokens → `OAuth1AuthProfile(CONSUMER_KEY=..., CONSUMER_SECRET=..., ACCESS_TOKEN=..., ACCESS_TOKEN_SECRET=...).emit(TargetFamily.HTTP, base=...)`. Credentials are flow-resolved; only rendering reuses the Phase-2 adapter.

- **D7 — `provider_type` retained** as identity label; registry keys on it; no longer dispatched on.

- **D8 — Golden parity is split (not a blanket equivalence).** Phase 2 deliberately diverged from the old resolver in places (notably: SFTP `PasswordAuthProfile` now emits **both** `username` and `password` to PARAMIKO; the old `SSHPasswordStrategy` emitted `password` only). Task 7 therefore has two test groups: `TestStrictParity` (emit == old resolver) and `TestIntentionalDivergence` (emit deliberately differs, each case docstring-citing the Phase-2 decision). Task 1's capture is the *old-behaviour* reference for the strict group; the divergent cases are asserted against the documented new behaviour. No count-based assertions — exact key/value shape only.

---

## File Structure

**New:** `src/mountainash_transport/_core/http/auth_protocol.py`; `tests/_core/test_auth_protocol_relocation.py`; `tests/connections/test_emission_golden.py`.
**Modified:** `connections/__init__.py`, `connections/{http,s3,ssh}.py`, `connections/oauth2/connection.py`, `connections/oauth1/connection.py`, `_core/http/engine.py`, `storage/backends/http/__init__.py`, plus leaf/factory/tunnel/engine/protocol-shape test modules.
**Deleted:** `src/mountainash_transport/_core/auth/{resolver,strategies,__init__}.py`; `tests/_core/auth/` (whole dir).

---

## Task 1: Capture golden baseline on the CURRENT (stale) env

**Files:** none committed — this is a measurement step run before the env refresh.

- [ ] **Step 1: Print the old resolver's merged output for every parity case**

Run (single command, current env, old resolver still importable):
```bash
hatch run test:python - <<'PY'
import base64
from mountainash_transport._core.auth.resolver import resolve_auth_strategy
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as P
from mountainash_auth_client import IAMAuth, JWTAuth, KerberosAuth, NoAuth, PasswordAuth, TokenAuth

def m(auth, prov, base): return resolve_auth_strategy(auth, provider_type=prov).apply(dict(base))
print("http_token   ", m(TokenAuth(TOKEN="t0k"), P.HTTP, {"timeout": 30}))
print("http_jwt     ", m(JWTAuth(TOKEN="jw7"), P.HTTP, {"timeout": 30}))
print("http_basic   ", m(PasswordAuth(USERNAME="u", PASSWORD="p"), P.HTTP, {"timeout": 30}))
print("boto_iam     ", m(IAMAuth(ACCESS_KEY_ID="AKIA", SECRET_ACCESS_KEY="sk", SESSION_TOKEN="st"), P.S3, {"service_name":"s3","region_name":"us-east-1"}))
print("boto_iam_nost", m(IAMAuth(ACCESS_KEY_ID="AKIA", SECRET_ACCESS_KEY="sk"), P.S3, {"service_name":"s3"}))
print("ssh_password ", m(PasswordAuth(USERNAME="u", PASSWORD="p"), P.SFTP, {"hostname":"h"}))
print("ssh_kerberos ", m(KerberosAuth(SERVICE_NAME="host.example.com"), P.SFTP, {"hostname":"h"}))
print("noauth       ", m(NoAuth(), P.HTTP, {"timeout": 30}))
print("basic_b64     u:p ->", base64.b64encode(b"u:p").decode())
PY
```

- [ ] **Step 2: Record the printed dicts in your working notes**

These become the expected literals in Task 7. Expected shapes (confirm against actual print):
- `http_token` → `{'timeout': 30, 'headers': {'Authorization': 'Bearer t0k'}}`
- `http_basic` → `{'timeout': 30, 'headers': {'Authorization': 'Basic dTpw'}}`
- `boto_iam` → `{'service_name': 's3', 'region_name': 'us-east-1', 'aws_access_key_id': 'AKIA', 'aws_secret_access_key': 'sk', 'aws_session_token': 'st'}`
- `ssh_password` (OLD) → `{'hostname': 'h', 'password': 'p'}` ← **no `username`** (this is the divergence in D8)
- `ssh_kerberos` → `{'hostname': 'h', 'gss_auth': True, 'gss_host': 'host.example.com'}`

No commit — this task produces notes only.

---

## Task 2: Refresh transport's test env to merged Phase 1 + Phase 2

**Files:** none (env operation). See memory `transport_env_staleness_and_profile_rename` and `auth_client_settings_env_staleness` for the uv-staleness mechanism.

- [ ] **Step 1: Locate the transport test-env venv**

Run: `hatch run test:python -c "import sys; print(sys.prefix)"`
Record the printed venv path (e.g. `~/.local/share/hatch/env/virtual/.../test.py3.12`).

- [ ] **Step 2: Build fresh wheels for settings and auth-client**

```bash
rm -f ../mountainash-settings/dist/*.whl ../mountainash-auth-client/dist/*.whl
python3 -m pip wheel --no-deps --no-cache-dir --wheel-dir /tmp/ph3-wheels ../mountainash-settings
python3 -m pip wheel --no-deps --no-cache-dir --wheel-dir /tmp/ph3-wheels ../mountainash-auth-client
```

- [ ] **Step 3: Reinstall both into the test venv with uv (the env has no pip)**

```bash
~/.local/bin/uv pip install --python <VENV>/bin/python --reinstall --no-cache --no-deps \
  /tmp/ph3-wheels/mountainash_settings-*.whl /tmp/ph3-wheels/mountainash_auth_client-*.whl
```
(Substitute `<VENV>` from Step 1. `uv cache clean` hangs in this environment — do not use it.)

- [ ] **Step 4: Verify the merged API is present**

Run:
```bash
hatch run test:python -c "from mountainash_auth_client.targets import TargetFamily; from mountainash_settings import Profile; from mountainash_auth_client import OAuth1AuthProfile; print('emit', hasattr(Profile,'emit'), 'TF', list(TargetFamily))"
```
Expected: `emit True TF [<TargetFamily.HTTP...>, ...]` and no ImportError.

- [ ] **Step 5: Record the expected baseline breakage**

Run: `hatch run test:test -q 2>&1 | tail -20`
Expected: failures/errors from transport's surviving short-name imports against the renamed auth-client (e.g. `ImportError: cannot import name 'OAuth2Auth'`). **This is expected** — Task 2b + Tasks 4–6 migrate those names. Note the failing modules so Task 8 can confirm they are all resolved. No commit.

---

## Task 2b: Migrate test-side short-name auth imports to `*Profile`

> These test modules import auth-client classes by their old short names and break the moment Task 2 refreshes the env. The migration is a pure mechanical symbol rename — no behavioural change. Doing it here restores suite collectability before the wiring work. (Production short-name sites are migrated inside Tasks 4–5 where those files are already being edited.)

**Files (11):** `tests/settings/test_profile_protocol.py`; `tests/connections/test_factory.py`; `tests/settings/storage/profiles/test_{azure,ftp,gcs,github,http,local,s3,sftp,smb}_settings.py`.

**Name map (apply to every occurrence — module-level AND inline imports):**
`NoAuth → NoAuthProfile`, `TokenAuth → TokenAuthProfile`, `OAuth2AuthCodeAuth → OAuth2AuthCodeAuthProfile`, `PasswordAuth → PasswordAuthProfile` (and, defensively, `IAMAuth → IAMAuthProfile`, `JWTAuth → JWTAuthProfile`, `KerberosAuth → KerberosAuthProfile`, `CertificateAuth → CertificateAuthProfile`, `OAuth2Auth → OAuth2AuthProfile`, `OAuth1Auth → OAuth1AuthProfile` if any surface).

- [ ] **Step 1: Find every short-name import outside `_core/auth`**

```bash
grep -rn "from mountainash_auth_client import \(NoAuth\|TokenAuth\|JWTAuth\|IAMAuth\|PasswordAuth\|KerberosAuth\|CertificateAuth\|OAuth2Auth\|OAuth2AuthCodeAuth\|OAuth1Auth\)\b" tests/ --include='*.py' | grep -v "_core/auth"
```
Confirmed set as of planning: the 9 `test_*_settings.py` + `test_profile_protocol.py` import `NoAuth`; `test_factory.py` inline-imports `TokenAuth` (line 54), `OAuth2AuthCodeAuth` (line 59). (Note: the new factory tests added in Task 4 Step 1 already use `*Profile` names, so they are unaffected.)

- [ ] **Step 2: Apply the rename in each file**

Rename per the map above. Each is a whole-word symbol swap on the import line and any constructor call site in the same file. After editing, re-run the Step-1 grep — expected: **no matches** outside `_core/auth/`.

- [ ] **Step 3: Verify the settings test tree imports cleanly**

Run: `hatch run test:test tests/settings -q`
Expected: PASS (these tests are orthogonal to the auth wiring; only the symbol names changed).

- [ ] **Step 4: Commit**
```bash
git add tests/settings tests/connections/test_factory.py
git commit -m "test(transport): migrate test-side auth imports to *Profile names"
```

---

## Task 3: Relocate auth protocols to `_core/http/`

**Files:** Create `src/mountainash_transport/_core/http/auth_protocol.py`; Modify `_core/http/engine.py:24`, `storage/backends/http/__init__.py:18`; Test `tests/_core/test_auth_protocol_relocation.py`.

- [ ] **Step 1: Write the failing relocation test**

```python
# tests/_core/test_auth_protocol_relocation.py
"""The auth protocols live in _core/http after Phase 3 relocation."""
import pytest


@pytest.mark.unit
def test_protocols_importable_from_new_home():
    from mountainash_transport._core.http.auth_protocol import (  # noqa: F401
        AuthStrategy,
        RefreshableAuthStrategy,
    )


@pytest.mark.unit
def test_apply_only_object_is_authstrategy():
    from mountainash_transport._core.http.auth_protocol import AuthStrategy

    class _Stub:
        def apply(self, kwargs):
            return dict(kwargs)

    assert isinstance(_Stub(), AuthStrategy)
```

- [ ] **Step 2: Run to verify it fails** — `hatch run test:test tests/_core/test_auth_protocol_relocation.py -v` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Create the relocated module**

```python
# src/mountainash_transport/_core/http/auth_protocol.py
"""Auth strategy protocols for the HTTP engine.

These describe the credential-injection / live-refresh contract the HTTP
request engine consumes. Concrete static strategies were removed in Phase 3
(credential rendering now flows through ``Profile.emit``); the refreshable
protocol remains as the seam for flow-owned token refresh.
"""
from __future__ import annotations

import typing as t
from typing import Protocol, runtime_checkable


@runtime_checkable
class AuthStrategy(Protocol):
    """Inject auth credentials into SDK client kwargs. Returns a NEW dict."""

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]: ...


@runtime_checkable
class RefreshableAuthStrategy(AuthStrategy, Protocol):
    """Auth strategy supporting credential refresh.

    After a successful refresh(), get_headers() must reflect the new
    credentials. Implementations must be internally synchronized.
    """

    def refresh(self) -> bool: ...

    def get_headers(self) -> dict[str, str]: ...
```

- [ ] **Step 4: Repoint the engine import** — `_core/http/engine.py:24`:
```python
from mountainash_transport._core.http.auth_protocol import AuthStrategy, RefreshableAuthStrategy
```

- [ ] **Step 5: Repoint the HTTP backend import** — `storage/backends/http/__init__.py:18` (inside `TYPE_CHECKING`):
```python
    from mountainash_transport._core.http.auth_protocol import AuthStrategy
```

- [ ] **Step 6: Repoint engine/protocol-shape TEST imports**

`tests/_core/http/test_engine.py:11` and `tests/connections/test_protocol_shapes.py:7` import from `_core.auth`. Change both to import the protocols from `mountainash_transport._core.http.auth_protocol`. (If either also references a deleted *concrete* strategy, leave that line for Task 6 — but the protocol imports move now.)

- [ ] **Step 7: Run** — `hatch run test:test tests/_core/test_auth_protocol_relocation.py tests/_core/http tests/connections/test_protocol_shapes.py -v` → PASS.

- [ ] **Step 8: Commit**
```bash
git add src/mountainash_transport/_core/http/auth_protocol.py src/mountainash_transport/_core/http/engine.py src/mountainash_transport/storage/backends/http/__init__.py tests/_core/test_auth_protocol_relocation.py tests/_core/http/test_engine.py tests/connections/test_protocol_shapes.py
git commit -m "refactor(transport): relocate auth protocols to _core/http"
```

---

## Task 4: Leaves become dict-only + factory emits — ONE atomic change

> **Why combined:** changing the leaf constructors and the factory in separate commits leaves an intermediate state where `create_connection()` passes 2 args to a 1-arg constructor → `TypeError`. Do both in one task/commit.

**Files:** Modify `connections/{http,s3,ssh}.py`, `connections/__init__.py`; Test `tests/connections/{test_http_connection,test_s3_connection,test_ssh_connection,test_factory,test_tunnel_connection}.py`.

- [ ] **Step 1: Write failing factory tests (family map + emission + passthrough)**

Add to `tests/connections/test_factory.py`:
```python
from mountainash_auth_client import IAMAuthProfile, NoAuthProfile
from mountainash_auth_client.targets import TargetFamily
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as P
from mountainash_transport.connections import _family_for_provider, create_connection


class FakeS3Profile:
    class __spec__:
        provider_type = "s3"
    def to_handler_kwargs(self):
        return {"service_name": "s3", "region_name": "us-east-1"}
    def get_connection_url(self):
        return "s3://b/k"


class TestFamilyMap:
    def test_http_to_http(self):    assert _family_for_provider(P.HTTP) is TargetFamily.HTTP
    def test_s3_to_boto(self):      assert _family_for_provider(P.S3) is TargetFamily.BOTO
    def test_sftp_to_paramiko(self):assert _family_for_provider(P.SFTP) is TargetFamily.PARAMIKO
    def test_local_to_none(self):   assert _family_for_provider(P.LOCAL) is None


class TestFactoryEmission:
    def test_iam_emitted_onto_s3_kwargs(self):
        conn = create_connection(FakeS3Profile(), IAMAuthProfile(ACCESS_KEY_ID="AKIA", SECRET_ACCESS_KEY="sk"))
        assert conn._connect_kwargs["aws_access_key_id"] == "AKIA"
        assert conn._connect_kwargs["aws_secret_access_key"] == "sk"
        assert conn._connect_kwargs["region_name"] == "us-east-1"

    def test_noauth_passthrough(self):
        conn = create_connection(FakeS3Profile(), NoAuthProfile())
        assert "aws_access_key_id" not in conn._connect_kwargs
        assert conn._connect_kwargs["service_name"] == "s3"

    def test_none_passthrough(self):
        conn = create_connection(FakeS3Profile(), None)
        assert "aws_access_key_id" not in conn._connect_kwargs
```

- [ ] **Step 2: Run to verify failure** — `hatch run test:test tests/connections/test_factory.py -v` → FAIL (`ImportError: _family_for_provider`).

- [ ] **Step 3: Make the three leaves dict-only**

For each of `connections/s3.py`, `connections/http.py`, `connections/ssh.py`:
- Remove the `from mountainash_transport._core.auth.strategies import AuthStrategy` import.
- Change `__init__` to `def __init__(self, connect_kwargs: dict[str, t.Any]) -> None:` (drop `auth_strategy`, drop `self._auth_strategy = ...`).
- In `connect()`, delete the `kwargs = self._auth_strategy.apply(kwargs)` line. Keep `kwargs = dict(self._connect_kwargs)` and any existing pops (`service_name` for S3, `_post_connect` for SSH).

- [ ] **Step 4: Rewrite the factory to emit per leaf + migrate names**

In `connections/__init__.py`:
- Remove `from mountainash_transport._core.auth.resolver import resolve_auth_strategy`.
- Migrate the OAuth routing imports to `*Profile`:
  - line 78: `from mountainash_auth_client import OAuth2AuthProfile, OAuth2AuthCodeAuthProfile` and update the `isinstance(auth_profile, (OAuth2AuthProfile, OAuth2AuthCodeAuthProfile))` check.
  - line 84: `from mountainash_auth_client.schemas.oauth1 import OAuth1AuthProfile` and update `isinstance(auth_profile, OAuth1AuthProfile)`.
- Add the family map + emit helper near the provider map:
```python
from mountainash_auth_client.targets import TargetFamily

_PROVIDER_FAMILY_MAP: dict[str, TargetFamily] = {
    "http": TargetFamily.HTTP,
    "s3": TargetFamily.BOTO, "s3express": TargetFamily.BOTO, "r2": TargetFamily.BOTO,
    "minio": TargetFamily.BOTO, "b2": TargetFamily.BOTO,
    "sftp": TargetFamily.PARAMIKO, "ssh": TargetFamily.PARAMIKO,
}


def _family_for_provider(provider_type: CONST_STORAGE_PROVIDER_TYPE | None) -> TargetFamily | None:
    """Map a storage provider type to the SDK target family it emits for."""
    if provider_type is None:
        return None
    provider_str = str(provider_type.value) if hasattr(provider_type, "value") else str(provider_type)
    return _PROVIDER_FAMILY_MAP.get(provider_str)


def _emit_kwargs(
    profile: ProfileProtocol,
    auth_profile: AuthProfile | None,
    family: TargetFamily | None,
) -> dict[str, t.Any]:
    """Merge handler kwargs with auth credentials via emit().

    NoAuthProfile / None / no-family → kwargs pass through unchanged. For the
    S3 assume-role envelope (nested ``base_kwargs``), credentials emit onto the
    inner base_kwargs, leaving role_arn/session_name untouched.
    """
    from mountainash_auth_client import NoAuthProfile

    base = profile.to_handler_kwargs()
    if auth_profile is None or isinstance(auth_profile, NoAuthProfile) or family is None:
        return base
    if "base_kwargs" in base:
        inner = auth_profile.emit(family, base=base["base_kwargs"])
        return {**base, "base_kwargs": inner}
    return auth_profile.emit(family, base=base)
```
- Replace the body of `create_connection` after the OAuth routing block:
```python
    provider_type = _provider_type_from_profile(profile)
    family = _family_for_provider(provider_type)

    if provider_type == CONST_STORAGE_PROVIDER_TYPE.SFTP:
        ssh_conn = SSHConnection(_emit_kwargs(profile, auth_profile, family))
        return SFTPConnection(ssh_conn)

    leaf_cls = _connection_for_provider(provider_type)
    if leaf_cls is NullConnection:
        return NullConnection()
    return leaf_cls(_emit_kwargs(profile, auth_profile, family))
```
(Add `from mountainash_auth_client import AuthProfile` under `TYPE_CHECKING` if not already imported, for the `_emit_kwargs` annotation.)

- [ ] **Step 5: Migrate `create_tunnelled_connection`**
```python
    bastion_family = _family_for_provider(CONST_STORAGE_PROVIDER_TYPE.SSH)
    ssh_conn = SSHConnection(_emit_kwargs(bastion_profile, bastion_auth, bastion_family))
```
(Delete the old `bastion_kwargs = ...` + `resolve_auth_strategy(...)` lines; the `inner_factory` closure is unchanged.)

- [ ] **Step 6: Update leaf + tunnel + protocol-shape tests**

In `tests/connections/test_http_connection.py`, `test_s3_connection.py`, `test_ssh_connection.py`, `test_tunnel_connection.py`, **and `tests/connections/test_protocol_shapes.py`**: drop every strategy argument from leaf constructor calls (`S3Connection(kwargs)`, etc.), remove all `from mountainash_transport._core.auth...` imports, and where a test asserted a strategy injected a value, fold that value into the `connect_kwargs` passed in.

Specifically for `tests/connections/test_protocol_shapes.py`: delete the line 7 import `from mountainash_transport._core.auth.strategies import NoAuthStrategy`; change `HTTPConnection(FakeProfile(), NoAuthStrategy())` (line 55) and `S3Connection(FakeProfile(), NoAuthStrategy())` (line 63) to dict-only construction — pass a plain dict (e.g. `HTTPConnection({})` / `S3Connection({})`), since the leaves no longer take a profile or a strategy. (The `OAuth2Connection`/`OAuth1Connection` shape assertions at lines 79/94 are unaffected — they still take a profile + auth.) This removes the last concrete-strategy reference so Task 6 Step 1's grep comes back clean.

Add to `test_s3_connection.py`:
```python
def test_connect_passes_merged_credentials_to_boto3(self):
    kwargs = {**FAKE_S3_KWARGS, "aws_access_key_id": "AKIA", "aws_secret_access_key": "sk"}
    conn = S3Connection(kwargs)
    with patch("boto3.client") as mock_client:
        conn.connect()
    _, called = mock_client.call_args
    assert called["aws_access_key_id"] == "AKIA"
    assert "service_name" not in called
```

- [ ] **Step 7: Run** — `hatch run test:test tests/connections/test_factory.py tests/connections/test_http_connection.py tests/connections/test_s3_connection.py tests/connections/test_ssh_connection.py tests/connections/test_tunnel_connection.py -v` → PASS.

- [ ] **Step 8: Commit**
```bash
git add src/mountainash_transport/connections/__init__.py src/mountainash_transport/connections/http.py src/mountainash_transport/connections/s3.py src/mountainash_transport/connections/ssh.py tests/connections/test_factory.py tests/connections/test_http_connection.py tests/connections/test_s3_connection.py tests/connections/test_ssh_connection.py tests/connections/test_tunnel_connection.py tests/connections/test_protocol_shapes.py
git commit -m "feat(transport): leaves consume merged kwargs; factory emits per leaf"
```

---

## Task 5: OAuth connections construct-and-emit

**Files:** Modify `connections/oauth2/connection.py`, `connections/oauth1/connection.py`; Test `tests/connections/oauth2/`, `tests/connections/oauth1/`.

- [ ] **Step 1: Write a failing OAuth2 emission test**

In the OAuth2 connection test module, using the existing token-resolution mocks, assert the resolved token becomes a Bearer header on the inner client kwargs:
```python
def test_resolved_token_emitted_as_bearer(self, ...):
    # arrange a valid cached access_token "AT0KEN" via the existing mock backend
    conn = OAuth2Connection(profile, auth_profile).connect()
    assert conn._inner._connect_kwargs["headers"]["Authorization"] == "Bearer AT0KEN"
```

- [ ] **Step 2: Run to verify failure** — `hatch run test:test tests/connections/oauth2 -v` → FAIL.

- [ ] **Step 3: Rewire OAuth2Connection + add empty-token guard (Codex F5)**

In `connections/oauth2/connection.py`:
- Remove `from mountainash_transport._core.auth.strategies import BearerTokenStrategy`.
- Add top-level `from mountainash_auth_client import TokenAuthProfile` and `from mountainash_auth_client.targets import TargetFamily`.
- Migrate the `TYPE_CHECKING` imports (lines 18-19) to `OAuth2AuthProfile`, `OAuth2AuthCodeAuthProfile`.
- Replace `connect()`:
```python
    def connect(self) -> Self:
        access_token = self._resolve_token()
        merged = TokenAuthProfile(TOKEN=access_token).emit(
            TargetFamily.HTTP, base=self._profile.to_handler_kwargs()
        )
        self._inner = HTTPConnection(merged)
        self._inner.connect()
        return self
```
- In `_resolve_token()`, harden against empty (not just `None`) tokens so an empty string can't silently produce a header-less (unauthenticated) client via the Phase-2 falsy-token guard. Change the two `access_token = tokens["access_token"]` / `new_tokens["access_token"]` assignments' downstream check: replace the final `if access_token is None:` guard with `if not access_token:` so empty strings trigger the same `AuthorizationRequired`/re-authorize path.

- [ ] **Step 4: Rewire OAuth1Connection**

In `connections/oauth1/connection.py`:
- Remove `from mountainash_transport._core.auth.strategies import AuthStrategy, OAuth1SignedStrategy`.
- Add top-level `from mountainash_auth_client import OAuth1AuthProfile` and `from mountainash_auth_client.targets import TargetFamily`.
- Migrate the `TYPE_CHECKING` import (line 18) to `OAuth1AuthProfile`.
- Replace `connect()` + `_resolve_strategy()` with:
```python
    def connect(self) -> Self:
        self._inner = HTTPConnection(self._resolve_kwargs())
        self._inner.connect()
        return self

    def _resolve_kwargs(self) -> dict[str, t.Any]:
        provider = self._spec.name
        backend = get_secrets_backend(self._auth.SETTINGS_SOURCE_SECRETS_PROVIDER)
        key = self._auth.persist_key()
        tokens = backend.get(key)

        if not (tokens and tokens.get("oauth_token")):
            if not self._auto_authorize:
                raise AuthorizationRequired(provider=provider, user="default")
            flow = OAuth1Flow(self._spec)
            tokens = flow.authorize(
                consumer_key=self._auth.CONSUMER_KEY,
                consumer_secret=self._auth.CONSUMER_SECRET.get_secret_value(),
            )
            backend.set(key, tokens)

        emitter = OAuth1AuthProfile(
            CONSUMER_KEY=self._auth.CONSUMER_KEY,
            CONSUMER_SECRET=self._auth.CONSUMER_SECRET.get_secret_value(),
            ACCESS_TOKEN=tokens["oauth_token"],
            ACCESS_TOKEN_SECRET=tokens["oauth_token_secret"],
        )
        return emitter.emit(TargetFamily.HTTP, base=self._profile.to_handler_kwargs())
```

- [ ] **Step 5: Update OAuth tests**

In `tests/connections/oauth1/` and `oauth2/`: any assertion on a returned `OAuth1SignedStrategy`/`BearerTokenStrategy` now targets inner kwargs — `assert "auth" in conn._inner._connect_kwargs` (OAuth1) / the Bearer header (OAuth2). The authorize-vs-cached and no-auth-raises branches are behaviourally unchanged; retarget only the strategy-shape assertions. Add a test that an empty cached access token raises `AuthorizationRequired` rather than producing a header-less client.

- [ ] **Step 6: Run** — `hatch run test:test tests/connections/oauth1 tests/connections/oauth2 -v` → PASS.

- [ ] **Step 7: Commit**
```bash
git add src/mountainash_transport/connections/oauth2/connection.py src/mountainash_transport/connections/oauth1/connection.py tests/connections/oauth1 tests/connections/oauth2
git commit -m "feat(transport): OAuth connections construct-and-emit; guard empty token"
```

---

## Task 6: Delete `_core/auth` + its tests

**Files:** Delete `_core/auth/{resolver,strategies,__init__}.py` and `tests/_core/auth/`; prune dangling re-exports.

- [ ] **Step 1: Confirm only deletable importers remain**

Run:
```bash
grep -rn "_core\.auth\|_core/auth\|resolve_auth_strategy" src/ tests/ --include='*.py'
```
Expected matches: only inside `_core/auth/` itself and `tests/_core/auth/` (both about to be deleted). `tests/connections/test_protocol_shapes.py` was already cleaned in Task 4 Step 6, so it must NOT appear here — if it does, that step was missed. If any other file appears (a re-export in a package `__init__.py`, `src/mountainash_transport/__init__.py`, or `tests/test_public_api.py`), note it for Step 3.

- [ ] **Step 2: Delete the package and its tests**
```bash
git rm src/mountainash_transport/_core/auth/resolver.py \
       src/mountainash_transport/_core/auth/strategies.py \
       src/mountainash_transport/_core/auth/__init__.py
git rm -r tests/_core/auth
rm -rf src/mountainash_transport/_core/auth/__pycache__
```

- [ ] **Step 3: Prune dangling re-exports**

```bash
grep -rn "AuthStrategy\|NoAuthStrategy\|BearerTokenStrategy\|IAMCredentialStrategy\|OAuth1SignedStrategy\|SSHKeyStrategy\|SSHPasswordStrategy\|SSHKerberosStrategy\|BasicAuthStrategy\|resolve_auth_strategy" src/mountainash_transport/__init__.py tests/test_public_api.py
```
Remove any **deleted** concrete-strategy / `resolve_auth_strategy` name from `__init__.py` exports and from public-API test expectations. Do **not** remove `AuthStrategy`/`RefreshableAuthStrategy` references that now resolve via `_core/http/auth_protocol` (repoint their import instead, if present).

- [ ] **Step 4: Import-smoke**

Run: `hatch run test:python -c "import mountainash_transport; from mountainash_transport.connections import create_connection; print('ok')"` → `ok`.

- [ ] **Step 5: Commit**
```bash
git add -A
git commit -m "refactor(transport): delete _core/auth resolver + static strategies + tests"
```

---

## Task 7: Golden (parity + divergence) + per-leaf emission tests

**Files:** Create `tests/connections/test_emission_golden.py`.

- [ ] **Step 1: Strict-parity golden tests (emit == old resolver, from Task 1 notes)**

```python
# tests/connections/test_emission_golden.py
"""Phase 3 golden tests. TestStrictParity: emit() reproduces the pre-refactor
resolver output captured in Task 1. TestIntentionalDivergence: cases where
Phase 2 deliberately changed behaviour. Exact key/value shape — no count asserts."""
from __future__ import annotations

import base64
import pytest

from mountainash_auth_client import (
    IAMAuthProfile, JWTAuthProfile, KerberosAuthProfile, PasswordAuthProfile, TokenAuthProfile,
)
from mountainash_auth_client.targets import TargetFamily


@pytest.mark.unit
class TestStrictParity:
    def test_http_bearer(self):
        out = TokenAuthProfile(TOKEN="t0k").emit(TargetFamily.HTTP, base={"timeout": 30})
        assert out == {"timeout": 30, "headers": {"Authorization": "Bearer t0k"}}

    def test_http_jwt_bearer(self):
        out = JWTAuthProfile(TOKEN="jw7").emit(TargetFamily.HTTP, base={"timeout": 30})
        assert out == {"timeout": 30, "headers": {"Authorization": "Bearer jw7"}}

    def test_http_basic(self):
        out = PasswordAuthProfile(USERNAME="u", PASSWORD="p").emit(TargetFamily.HTTP, base={"timeout": 30})
        token = base64.b64encode(b"u:p").decode()
        assert out == {"timeout": 30, "headers": {"Authorization": f"Basic {token}"}}

    def test_boto_iam_full(self):
        out = IAMAuthProfile(ACCESS_KEY_ID="AKIA", SECRET_ACCESS_KEY="sk", SESSION_TOKEN="st").emit(
            TargetFamily.BOTO, base={"service_name": "s3", "region_name": "us-east-1"})
        assert out == {"service_name": "s3", "region_name": "us-east-1",
                       "aws_access_key_id": "AKIA", "aws_secret_access_key": "sk", "aws_session_token": "st"}

    def test_boto_iam_no_session(self):
        out = IAMAuthProfile(ACCESS_KEY_ID="AKIA", SECRET_ACCESS_KEY="sk").emit(
            TargetFamily.BOTO, base={"service_name": "s3"})
        assert out == {"service_name": "s3", "aws_access_key_id": "AKIA", "aws_secret_access_key": "sk"}

    def test_paramiko_kerberos(self):
        out = KerberosAuthProfile(SERVICE_NAME="host.example.com").emit(
            TargetFamily.PARAMIKO, base={"hostname": "h"})
        assert out == {"hostname": "h", "gss_auth": True, "gss_host": "host.example.com"}


@pytest.mark.unit
class TestIntentionalDivergence:
    def test_sftp_password_now_emits_username(self):
        # OLD SSHPasswordStrategy emitted {"password": "p"} only. Phase 2's
        # PasswordAuthProfile deliberately scopes BOTH username + password to
        # PARAMIKO so paramiko.connect receives a username. Documented divergence.
        out = PasswordAuthProfile(USERNAME="u", PASSWORD="p").emit(
            TargetFamily.PARAMIKO, base={"hostname": "h"})
        assert out == {"hostname": "h", "username": "u", "password": "p"}
```

> **Implementer note:** reconcile every `TestStrictParity` literal against the Task-1 capture print. If a captured value differs (e.g. Kerberos also emitted `gss_kex`), the capture is truth for parity — update the assertion and flag it. If a difference is an *intentional* Phase-2 change, move that case into `TestIntentionalDivergence` with a docstring citing the decision instead of forcing parity.

- [ ] **Step 2: S3 ROLE_ARN base_kwargs layering test (+ known-gap docstring)**

```python
@pytest.mark.unit
class TestS3RoleArnLayering:
    """Credentials layer into the nested base_kwargs; the assume-role envelope
    is preserved. NOTE: S3Connection does NOT yet consume this envelope (no STS
    AssumeRole at connect time) — that is a pre-existing unimplemented gap, out
    of Phase 3 scope. This test asserts only the layering the spec requires."""
    def test_credentials_land_in_base_kwargs(self):
        from mountainash_transport.connections import _emit_kwargs, _family_for_provider
        from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as P
        from mountainash_auth_client import IAMAuthProfile

        class _Nested:
            class __spec__:
                provider_type = "s3"
            def to_handler_kwargs(self):
                return {"base_kwargs": {"service_name": "s3", "region_name": "us-east-1"},
                        "role_arn": "arn:aws:iam::123:role/r", "session_name": "mountainash-transport"}
            def get_connection_url(self):
                return "s3://b/k"

        out = _emit_kwargs(_Nested(), IAMAuthProfile(ACCESS_KEY_ID="AKIA", SECRET_ACCESS_KEY="sk"),
                           _family_for_provider(P.S3))
        assert out["role_arn"] == "arn:aws:iam::123:role/r"
        assert out["session_name"] == "mountainash-transport"
        assert out["base_kwargs"]["aws_access_key_id"] == "AKIA"
        assert "aws_access_key_id" not in out  # not at the top level
```

- [ ] **Step 3: Per-leaf emission for the SFTP chain**

```python
@pytest.mark.unit
class TestPerLeafEmission:
    def test_sftp_chain_emits_paramiko_on_inner_ssh(self):
        from mountainash_transport.connections import create_connection
        from mountainash_transport.connections.sftp import SFTPConnection
        from mountainash_auth_client import PasswordAuthProfile

        class _SFTP:
            class __spec__:
                provider_type = "sftp"
            def to_handler_kwargs(self):
                return {"hostname": "h"}
            def get_connection_url(self):
                return "sftp://h/p"

        conn = create_connection(_SFTP(), PasswordAuthProfile(USERNAME="u", PASSWORD="p"))
        assert isinstance(conn, SFTPConnection)
        # SFTPConnection stores its inner SSH leaf as `_ssh` (see connections/sftp.py:19).
        assert conn._ssh._connect_kwargs["username"] == "u"
        assert conn._ssh._connect_kwargs["password"] == "p"
```

- [ ] **Step 4: Run** — `hatch run test:test tests/connections/test_emission_golden.py -v` → PASS.

- [ ] **Step 5: Commit**
```bash
git add tests/connections/test_emission_golden.py
git commit -m "test(transport): golden parity/divergence + S3 layering + per-leaf emission"
```

---

## Task 8: Full suite, lint, type-check

- [ ] **Step 1: Full suite** — `hatch run test:test -q`. Expected: all pass, including the modules Task 2 Step 5 noted as failing on the rename — confirm each is now green. Root-cause any failure; do **not** silence. Likely residue: a stray short-name import or a public-API surface test still listing a deleted strategy export.

- [ ] **Step 2: Lint** — `hatch run ruff:check` (then `hatch run ruff:fix` for import-order/unused-import nits from the deletions). Expected: clean.

- [ ] **Step 3: Type-check** — `hatch run mypy:check`. Fix annotations (leaf `connect()` no longer references `AuthStrategy`; `_emit_kwargs` return type) rather than suppressing. Expected: clean.

- [ ] **Step 4: Commit (if Steps 2–3 changed anything)**
```bash
git add -A
git commit -m "chore(transport): lint + type-check clean post-emission-refactor"
```

---

## Self-Review

**Spec coverage:** merged-kwargs equivalence → Tasks 1+7; HTTP/BOTO/PARAMIKO parametrization → Task 7; S3 ROLE_ARN nested layering → Task 7 `TestS3RoleArnLayering` + Task 4 `_emit_kwargs` (D5, with assume-role-execution gap documented); SFTP/tunnel per-leaf → Task 7 `TestPerLeafEmission` + Task 4 tunnel rewire; composition model / flow-owned OAuth → Tasks 4+5 (D6); `provider_type` retention → D7; require_paramiko/[sftp] → landed in Phase 2, no transport change.

**Codex findings addressed (round 1):** F1 (S3 envelope) → D5 scope note + Task 7 Step 2 docstring (layering only; STS execution out of scope, gap recorded). F2 (ordering) → leaf/factory merged into one atomic Task 4. F3 (names) → `*Profile` everywhere + Task 2b migrates the 11 short-name test modules + production sites migrated in Tasks 4–5. F4 (golden) → Task 7 split into `TestStrictParity` / `TestIntentionalDivergence`. F5 (empty OAuth2 token) → Task 5 Step 3 `if not access_token` guard. F6 (test importers) → Task 3 Step 6 (engine import) + Task 4 Step 6 (`test_protocol_shapes.py` dict-only + `NoAuthStrategy` removal) + Task 6 Step 2 (delete `tests/_core/auth/`).

**Planning-discovered additions:** Task 1 capture runs pre-refresh (old resolver needs short names); Task 2 refreshes transport's stale env to merged Phase 1+2 before any emit-based code is exercised.

**Placeholder scan:** none — code complete in every step; the two implementer notes flag verification points (capture reconciliation, real `_ssh` attr — already confirmed), not gaps.

**Type consistency:** `_family_for_provider`, `_emit_kwargs`, `TargetFamily`, `*Profile` names, single-arg leaf `__init__(connect_kwargs)`, OAuth1 `_resolve_strategy`→`_resolve_kwargs` (return `dict`) used consistently across Tasks 3–7.
