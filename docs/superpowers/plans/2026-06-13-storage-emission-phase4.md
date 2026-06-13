# Phase 4 — Storage-profile config emission via `emit()` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the three *connected* storage profiles (S3/BOTO, HTTP, SFTP/PARAMIKO) to produce their SDK config through the unified `emit(family)` primitive via 2-arg `__adapters__` adapters that build on the existing `driver_key`s — eliminating the special-cased `to_handler_kwargs()` dispatch in the factory. Output is held byte-identical (golden-verified).

**Architecture:** Each connected profile gains `__adapters__ = {TargetFamily.X: _adapter}` (2-arg, composes on `_default_kwargs` = driver_key output) plus a tiny `_sdk_family()` hook; `to_handler_kwargs()` becomes a deprecated shim → `self.emit(self._sdk_family())` (D2a). The factory's `_emit_kwargs` calls `profile.emit(family)` for the storage base, then `auth_profile.emit(family, base=...)` for credentials — both on the same `TargetFamily`. `_PatchedEndpointProfile` gains an `emit()` override mirroring its `to_handler_kwargs` patch (Codex-F2). Local stays on `to_handler_kwargs` (no family — factory's `family is None` branch handles it, D5).

**Tech Stack:** Python 3.12, mountainash-settings `Profile.emit`/`__adapters__`, boto3/botocore `Config`, httpx `Timeout`, paramiko, pytest, ruff.

**Repo / branch:** `mountainash-utils-files`. Branch `feature/storage-emission-phase4` off **`origin/develop`** (the connections-dedup is merged at `3ab7dc2`).

**Spec:** `docs/superpowers/specs/2026-06-13-storage-emission-phase4-design.md` (accepted, Codex ACCEPT).

---

## Settled decisions (baked in — do not re-litigate)

- **D1:** 2-arg `__adapters__[family]` adapters that BUILD ON `driver_key` (`emit` feeds `{**base, **_default_kwargs(family)}` to the 2-arg adapter; the 1-arg `__adapter__` would orphan driver_keys — settings `profile.py:297-302`).
- **D2(a):** `to_handler_kwargs()` becomes a deprecated shim `return self.emit(self._sdk_family())`. The adapters contain the computed logic inline and do NOT call `to_handler_kwargs` (no circularity). Internal factory path goes direct to `emit(family)`.
  - **Scope note (deliberate):** the OAuth2/OAuth1 connections (`connections/oauth{2,1}/connection.py`) still call `self._profile.to_handler_kwargs()` to build the storage base. This is intentionally left on the shim — it routes through `emit(HTTP)` underneath, so there is no behavioral change and no regression. Migrating those two call sites to `emit()` directly is a trivial, separate cleanup, NOT part of Phase 4. Do not flag it as incomplete.
- **D3:** storage `emit` is targeted by family (adding `__adapters__` makes the profile `_is_targeted()` → `emit()` with no target fails closed; `emit(family)` required).
- **D5:** `LocalStorageProfile` keeps its real `to_handler_kwargs()` (no SDK family; factory's `family is None` branch already feeds it). NOT migrated.
- **Scope:** connected families only (S3/BOTO, HTTP/HTTP, SFTP/PARAMIKO). Azure/GCS/FTP/SMB/GitHub are describe-only (no connection, no `TargetFamily`) — explicitly NOT migrated.

## Key facts from the code (read before implementing)

- `_default_kwargs(target)` (settings `profile.py:206-229`) **skips params whose value is None** and whose resolved key is None, unwraps `SecretStr`, applies `transform`. So e.g. S3 `aws` (ENDPOINT_URL=None) does NOT emit `endpoint_url`.
- `emit(family)` (settings `profile.py:256-302`): `merged = {**(base or {}), **_default_kwargs(target)}`; if `__adapters__[target]` exists → `adapter(self, merged)`; fail-closed when target-scoped and target missing/unknown.
- **S3 driver_keys:** `REGION→region_name`, `ENDPOINT_URL→endpoint_url`, `USE_SSL→use_ssl`. But `to_handler_kwargs` OVERRIDES `region_name` (→`"auto"` for r2) and `endpoint_url` (computed via `_resolve_endpoint_url`), and adds `service_name`/`verify`/`config`. The adapter must set those explicitly.
- **SFTP driver_keys** already cover every `_DRIVER_KEYS` pair, so `_default_kwargs(PARAMIKO)` == the current loop output; the adapter only adds the `_post_connect` envelope (KNOWN_HOSTS_FILE + HOST_KEY_POLICY).
- **HTTP** has NO driver_keys → `_default_kwargs(HTTP)` == `{}`; the adapter builds the full httpx config.

---

### Task 1: S3 — `__adapters__[BOTO]` adapter + shim (highest risk)

**Files:**
- Modify: `src/mountainash_transport/settings/storage/profiles/s3_storage_profile.py`
- Test: `tests/settings/storage/profiles/test_s3_settings.py`

- [ ] **Step 1: Write the golden-equivalence test FIRST**

Append to `tests/settings/storage/profiles/test_s3_settings.py` (import `TargetFamily` from `mountainash_auth_client.targets`, `botocore.config`). These assert `emit(BOTO)` equals the current `to_handler_kwargs` output across the flavor matrix + role envelope. The `config` value is a `botocore.config.Config`; compare its relevant attributes (Config has no stable `__eq__`), so compare the surrounding dict minus `config`, then assert `config` fields.

```python
import botocore.config
from mountainash_auth_client.targets import TargetFamily
from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile


def _split_config(d: dict):
    d = dict(d)
    cfg = d.pop("config", None)
    return d, cfg


class TestS3EmitGolden:
    def test_aws_default(self):
        p = S3StorageProfile(FLAVOR="aws", REGION="us-east-1")
        out = p.emit(TargetFamily.BOTO)
        flat, cfg = _split_config(out)
        assert flat == {
            "service_name": "s3", "region_name": "us-east-1",
            "use_ssl": True, "verify": True,
        }
        assert cfg.s3 == {"addressing_style": "auto"}

    def test_r2_region_auto_and_endpoint_from_account(self):
        p = S3StorageProfile(FLAVOR="r2", ACCOUNT_ID="acct123")
        out = p.emit(TargetFamily.BOTO)
        flat, cfg = _split_config(out)
        assert flat == {
            "service_name": "s3", "region_name": "auto", "use_ssl": True,
            "verify": True, "endpoint_url": "https://acct123.r2.cloudflarestorage.com",
        }
        assert cfg.s3 == {"addressing_style": "auto"}

    def test_minio_requires_explicit_endpoint(self):
        p = S3StorageProfile(FLAVOR="minio", ENDPOINT_URL="http://localhost:9000", REGION="us-east-1")
        out = p.emit(TargetFamily.BOTO)
        flat, _ = _split_config(out)
        assert flat["endpoint_url"] == "http://localhost:9000"
        assert flat["region_name"] == "us-east-1"

    def test_b2_default_endpoint(self):
        p = S3StorageProfile(FLAVOR="b2", REGION="us-west-004")
        out = p.emit(TargetFamily.BOTO)
        flat, _ = _split_config(out)
        assert flat["endpoint_url"] == "https://s3.us-west-004.backblazeb2.com"

    def test_express_forces_virtual_addressing(self):
        p = S3StorageProfile(FLAVOR="express", REGION="us-east-1")
        out = p.emit(TargetFamily.BOTO)
        _, cfg = _split_config(out)
        assert cfg.s3 == {"addressing_style": "virtual"}

    def test_aws_accelerate_and_dualstack(self):
        p = S3StorageProfile(FLAVOR="aws", REGION="us-east-1",
                             ACCELERATE_ENDPOINT=True, DUALSTACK_ENDPOINT=True)
        _, cfg = _split_config(p.emit(TargetFamily.BOTO))
        assert cfg.s3 == {
            "addressing_style": "auto",
            "use_accelerate_endpoint": True,
            "use_dualstack_endpoint": True,
        }

    def test_timeouts_land_on_config(self):
        p = S3StorageProfile(FLAVOR="aws", REGION="us-east-1",
                             CONNECT_TIMEOUT=3.0, READ_TIMEOUT=7.0)
        _, cfg = _split_config(p.emit(TargetFamily.BOTO))
        assert cfg.connect_timeout == 3.0
        assert cfg.read_timeout == 7.0

    def test_role_arn_nested_envelope(self):
        p = S3StorageProfile(FLAVOR="aws", REGION="us-east-1",
                             ROLE_ARN="arn:aws:iam::123:role/r")
        out = p.emit(TargetFamily.BOTO)
        assert out["role_arn"] == "arn:aws:iam::123:role/r"
        assert out["session_name"] == "mountainash-transport"
        inner_flat, inner_cfg = _split_config(out["base_kwargs"])
        assert inner_flat == {
            "service_name": "s3", "region_name": "us-east-1",
            "use_ssl": True, "verify": True,
        }
        assert inner_cfg.s3 == {"addressing_style": "auto"}

    def test_driver_keys_preserved_in_emit(self):
        # The 2-arg adapter composes on driver_key output (use_ssl/region_name),
        # not orphaning it.
        p = S3StorageProfile(FLAVOR="aws", REGION="eu-west-1", USE_SSL=False)
        flat, _ = _split_config(p.emit(TargetFamily.BOTO))
        assert flat["region_name"] == "eu-west-1"   # REGION driver_key
        assert flat["use_ssl"] is False             # USE_SSL driver_key

    def test_emit_no_target_fails_closed(self):
        import pytest
        with pytest.raises(ValueError):
            S3StorageProfile(FLAVOR="aws").emit()

    def test_shim_equals_emit(self):
        p = S3StorageProfile(FLAVOR="r2", ACCOUNT_ID="acct123")
        shim, semit = _split_config(p.to_handler_kwargs())
        emit, eemit = _split_config(p.emit(TargetFamily.BOTO))
        assert shim == emit
        assert semit.s3 == eemit.s3
```

- [ ] **Step 2: Run to verify it fails**

Run: `hatch run test:test tests/settings/storage/profiles/test_s3_settings.py -k TestS3EmitGolden -v`
Expected: FAIL — `S3StorageProfile is target-scoped`? No — currently NOT targeted (no `__adapters__`), so `emit(BOTO)` returns the bare driver_key merge `{region_name, use_ssl}` with no service_name/config → assertions fail.

- [ ] **Step 3: Add the adapter, `_sdk_family`, and the shim**

In `s3_storage_profile.py`, add the import near the top:

```python
from mountainash_auth_client.targets import TargetFamily
```

Add a module-level adapter function (above the class). It is the existing `to_handler_kwargs` body, seeded from `kw` (the driver_key merge) and setting every computed key explicitly. Reuse the profile's existing `_resolve_endpoint_url` / `_resolve_addressing_style` helpers:

```python
def _s3_boto_kwargs(profile: "S3StorageProfile", kw: dict[str, t.Any]) -> dict[str, t.Any]:
    """Build boto3 client kwargs, composing on the driver_key merge (``kw``).

    ``kw`` already carries the driver_key fields (region_name, use_ssl, and
    endpoint_url when ENDPOINT_URL is set). This recomputes the flavor-dependent
    region/endpoint/addressing and the botocore Config, preserving the exact
    output the legacy ``to_handler_kwargs`` produced.
    """
    try:
        import botocore.config as _botocore_config
    except ImportError:  # pragma: no cover - botocore is a boto3 transitive
        _botocore_config = None  # type: ignore[assignment]

    flavor = getattr(profile, "FLAVOR", "aws")
    region = getattr(profile, "REGION", None)
    endpoint_url = getattr(profile, "ENDPOINT_URL", None)
    account_id = getattr(profile, "ACCOUNT_ID", None)
    use_ssl = getattr(profile, "USE_SSL", True)
    addressing_style = profile._resolve_addressing_style(
        flavor, getattr(profile, "ADDRESSING_STYLE", "auto")
    )
    accelerate = bool(getattr(profile, "ACCELERATE_ENDPOINT", False))
    dualstack = bool(getattr(profile, "DUALSTACK_ENDPOINT", False))
    verify_ssl = getattr(profile, "VERIFY_SSL", True)
    role_arn = getattr(profile, "ROLE_ARN", None)

    effective_region = "auto" if flavor == "r2" else region

    base: dict[str, t.Any] = dict(kw)            # compose on driver_key output
    base["service_name"] = "s3"
    base["region_name"] = effective_region
    base["use_ssl"] = use_ssl
    base["verify"] = verify_ssl

    resolved_endpoint = profile._resolve_endpoint_url(
        flavor, region, endpoint_url, account_id
    )
    if resolved_endpoint is not None:
        base["endpoint_url"] = resolved_endpoint
    else:
        base.pop("endpoint_url", None)           # aws/express: never present

    if _botocore_config is not None:
        s3_config: dict[str, t.Any] = {"addressing_style": addressing_style}
        if flavor == "aws":
            if accelerate:
                s3_config["use_accelerate_endpoint"] = True
            if dualstack:
                s3_config["use_dualstack_endpoint"] = True
        config_kwargs: dict[str, t.Any] = {"s3": s3_config}
        connect_timeout = getattr(profile, "CONNECT_TIMEOUT", None)
        read_timeout = getattr(profile, "READ_TIMEOUT", None)
        if connect_timeout is not None:
            config_kwargs["connect_timeout"] = connect_timeout
        if read_timeout is not None:
            config_kwargs["read_timeout"] = read_timeout
        base["config"] = _botocore_config.Config(**config_kwargs)

    if role_arn:
        return {
            "base_kwargs": base,
            "role_arn": role_arn,
            "session_name": "mountainash-transport",
        }
    return base
```

On the `S3StorageProfile` class, register the adapter and add `_sdk_family`, then REPLACE the body of `to_handler_kwargs` with the shim:

```python
class S3StorageProfile(Profile):
    __spec__ = S3_SPEC
    __adapters__ = {TargetFamily.BOTO: _s3_boto_kwargs}

    def _sdk_family(self) -> TargetFamily:
        return TargetFamily.BOTO

    # ... keep get_connection_url, _resolve_endpoint_url, _resolve_addressing_style ...

    def to_handler_kwargs(self) -> dict[str, t.Any]:
        """Deprecated shim — kept for downstream callers (Phase 4 D2a).

        Delegates to the unified ``emit()`` pipeline. Internal callers should
        use ``emit(TargetFamily.BOTO)`` directly. Slated for removal in a later major.
        """
        return self.emit(self._sdk_family())
```

Delete the old computed body of `to_handler_kwargs` (lines ~285-357) — it now lives in `_s3_boto_kwargs`. Keep `_resolve_endpoint_url`/`_resolve_addressing_style` (the adapter calls them).

> `__adapters__` must reference `_s3_boto_kwargs`, which is defined above the class. Because `_resolve_endpoint_url`/`_resolve_addressing_style` are instance methods, the adapter calls them as `profile._resolve_...(...)`.

- [ ] **Step 4: Run the golden + existing S3 profile tests**

Run: `hatch run test:test tests/settings/storage/profiles/test_s3_settings.py -v`
Expected: PASS — the new `TestS3EmitGolden` group AND every pre-existing test in the file (which asserts `to_handler_kwargs()` output — now proves the shim is byte-identical).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/settings/storage/profiles/s3_storage_profile.py tests/settings/storage/profiles/test_s3_settings.py
git commit -m "feat: S3 profile emits boto3 kwargs via __adapters__[BOTO]"
```

---

### Task 2: HTTP — `__adapters__[HTTP]` adapter + shim

**Files:**
- Modify: `src/mountainash_transport/settings/storage/profiles/http_storage_profile.py`
- Test: `tests/settings/storage/profiles/test_http_settings.py`

- [ ] **Step 1: Write the golden test**

Append (import `TargetFamily`, `httpx`):

```python
import httpx
from mountainash_auth_client.targets import TargetFamily
from mountainash_transport.settings.storage.profiles.http_storage_profile import HTTPStorageProfile


class TestHTTPEmitGolden:
    def test_default_config(self):
        out = HTTPStorageProfile().emit(TargetFamily.HTTP)
        assert out["follow_redirects"] is True
        assert out["max_redirects"] == 10
        assert out["verify"] is True
        assert out["timeout"] == httpx.Timeout(connect=10.0, read=30.0, write=60.0, pool=5.0)
        assert "headers" not in out

    def test_custom_timeouts_and_headers(self):
        out = HTTPStorageProfile(
            TIMEOUT_CONNECT=1.0, TIMEOUT_READ=2.0, TIMEOUT_WRITE=3.0,
            VERIFY_SSL=False, HEADERS={"X-A": "1"},
        ).emit(TargetFamily.HTTP)
        assert out["timeout"] == httpx.Timeout(connect=1.0, read=2.0, write=3.0, pool=5.0)
        assert out["verify"] is False
        assert out["headers"] == {"X-A": "1"}

    def test_emit_no_target_fails_closed(self):
        import pytest
        with pytest.raises(ValueError):
            HTTPStorageProfile().emit()

    def test_shim_equals_emit(self):
        p = HTTPStorageProfile(HEADERS={"X-A": "1"})
        assert p.to_handler_kwargs() == p.emit(TargetFamily.HTTP)
```

> `httpx.Timeout` implements `__eq__`, so the equality assertions hold.

- [ ] **Step 2: Run to verify fail**

Run: `hatch run test:test tests/settings/storage/profiles/test_http_settings.py -k TestHTTPEmitGolden -v`
Expected: FAIL (emit returns `{}` — no adapter yet).

- [ ] **Step 3: Add adapter, `_sdk_family`, shim**

Add import `from mountainash_auth_client.targets import TargetFamily`. Add the module-level adapter (the existing `to_handler_kwargs` body, seeded from `kw`):

```python
def _http_httpx_kwargs(profile: "HTTPStorageProfile", kw: dict[str, t.Any]) -> dict[str, t.Any]:
    """Build httpx.Client kwargs (composing on kw, which is empty for HTTP)."""
    result: dict[str, t.Any] = dict(kw)
    result["timeout"] = httpx.Timeout(
        connect=getattr(profile, "TIMEOUT_CONNECT", 10.0),
        read=getattr(profile, "TIMEOUT_READ", 30.0),
        write=getattr(profile, "TIMEOUT_WRITE", 60.0),
        pool=5.0,
    )
    result["follow_redirects"] = getattr(profile, "FOLLOW_REDIRECTS", True)
    result["max_redirects"] = getattr(profile, "MAX_REDIRECTS", 10)
    result["verify"] = getattr(profile, "VERIFY_SSL", True)
    custom_headers = getattr(profile, "HEADERS", None) or {}
    if custom_headers:
        result["headers"] = dict(custom_headers)
    return result
```

On the class:

```python
class HTTPStorageProfile(Profile):
    __spec__ = HTTP_SPEC
    __adapters__ = {TargetFamily.HTTP: _http_httpx_kwargs}

    def _sdk_family(self) -> TargetFamily:
        return TargetFamily.HTTP

    def get_connection_url(self) -> str:
        return "http(s)://<dynamic>"

    def to_handler_kwargs(self) -> dict[str, t.Any]:
        """Deprecated shim (Phase 4 D2a) → emit(TargetFamily.HTTP)."""
        return self.emit(self._sdk_family())
```

Delete the old computed `to_handler_kwargs` body.

- [ ] **Step 4: Run tests**

Run: `hatch run test:test tests/settings/storage/profiles/test_http_settings.py -v`
Expected: PASS (new group + existing tests via the shim).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/settings/storage/profiles/http_storage_profile.py tests/settings/storage/profiles/test_http_settings.py
git commit -m "feat: HTTP profile emits httpx kwargs via __adapters__[HTTP]"
```

---

### Task 3: SFTP — `__adapters__[PARAMIKO]` adapter + shim

**Files:**
- Modify: `src/mountainash_transport/settings/storage/profiles/sftp_storage_profile.py`
- Test: `tests/settings/storage/profiles/test_sftp_settings.py`

- [ ] **Step 1: Write the golden test**

Append (import `TargetFamily`):

```python
from mountainash_auth_client.targets import TargetFamily
from mountainash_transport.settings.storage.profiles.sftp_storage_profile import SFTPStorageProfile


class TestSFTPEmitGolden:
    def test_driver_keys_plus_post_connect(self):
        p = SFTPStorageProfile(HOST="h", USERNAME="u", PORT=2222, TIMEOUT=15.0)
        out = p.emit(TargetFamily.PARAMIKO)
        assert out["hostname"] == "h"
        assert out["username"] == "u"
        assert out["port"] == 2222
        assert out["timeout"] == 15.0
        # default HOST_KEY_POLICY="reject" always lands in the _post_connect envelope
        assert out["_post_connect"] == {"host_key_policy": "reject"}

    def test_known_hosts_in_post_connect(self):
        p = SFTPStorageProfile(HOST="h", USERNAME="u",
                               KNOWN_HOSTS_FILE="/etc/known_hosts", HOST_KEY_POLICY="auto_add")
        out = p.emit(TargetFamily.PARAMIKO)
        assert out["_post_connect"] == {
            "known_hosts_file": "/etc/known_hosts",
            "host_key_policy": "auto_add",
        }

    def test_none_timeouts_skipped(self):
        p = SFTPStorageProfile(HOST="h", USERNAME="u")  # BANNER/AUTH_TIMEOUT default None
        out = p.emit(TargetFamily.PARAMIKO)
        assert "banner_timeout" not in out
        assert "auth_timeout" not in out

    def test_emit_no_target_fails_closed(self):
        import pytest
        with pytest.raises(ValueError):
            SFTPStorageProfile(HOST="h", USERNAME="u").emit()

    def test_shim_equals_emit(self):
        p = SFTPStorageProfile(HOST="h", USERNAME="u", KNOWN_HOSTS_FILE="/k")
        assert p.to_handler_kwargs() == p.emit(TargetFamily.PARAMIKO)
```

- [ ] **Step 2: Run to verify fail**

Run: `hatch run test:test tests/settings/storage/profiles/test_sftp_settings.py -k TestSFTPEmitGolden -v`
Expected: FAIL (emit returns just the driver_key merge — no `_post_connect`).

- [ ] **Step 3: Add adapter, `_sdk_family`, shim**

Add import `from mountainash_auth_client.targets import TargetFamily`. Add the module-level adapter — `kw` is already the driver_key output (identical to the old `_DRIVER_KEYS` loop), so the adapter only appends the post-connect envelope:

```python
def _sftp_paramiko_kwargs(profile: "SFTPStorageProfile", kw: dict[str, t.Any]) -> dict[str, t.Any]:
    """Compose on the driver_key merge (kw) and append the post-connect envelope."""
    result: dict[str, t.Any] = dict(kw)
    post_connect: dict[str, t.Any] = {}
    known_hosts = getattr(profile, "KNOWN_HOSTS_FILE", None)
    host_key_policy = getattr(profile, "HOST_KEY_POLICY", None)
    if known_hosts:
        post_connect["known_hosts_file"] = str(known_hosts)
    if host_key_policy:
        post_connect["host_key_policy"] = host_key_policy
    if post_connect:
        result["_post_connect"] = post_connect
    return result
```

On the class:

```python
class SFTPStorageProfile(Profile):
    __spec__ = SFTP_SPEC
    __adapters__ = {TargetFamily.PARAMIKO: _sftp_paramiko_kwargs}

    def _sdk_family(self) -> TargetFamily:
        return TargetFamily.PARAMIKO

    # ... keep get_connection_url ...

    def to_handler_kwargs(self) -> dict[str, t.Any]:
        """Deprecated shim (Phase 4 D2a) → emit(TargetFamily.PARAMIKO)."""
        return self.emit(self._sdk_family())
```

Delete the old computed `to_handler_kwargs` body. The module-level `_DRIVER_KEYS` tuple is now unused by the profile — remove it ONLY if nothing else imports it (grep `_DRIVER_KEYS` first; if unused, delete it to avoid dead code).

- [ ] **Step 4: Run tests**

Run: `hatch run test:test tests/settings/storage/profiles/test_sftp_settings.py -v`
Expected: PASS (new group + existing tests via the shim).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/settings/storage/profiles/sftp_storage_profile.py tests/settings/storage/profiles/test_sftp_settings.py
git commit -m "feat: SFTP profile emits paramiko kwargs via __adapters__[PARAMIKO]"
```

---

### Task 4: `_PatchedEndpointProfile.emit()` override (Codex-F2)

**Files:**
- Modify: `src/mountainash_transport/connections/tunnel.py`
- Test: `tests/connections/test_tunnel_connection.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/connections/test_tunnel_connection.py` a test that the patched profile's `emit()` injects the tunnel's local host/port (so the migrated factory routes through the tunnel, not the real remote):

```python
from mountainash_auth_client.targets import TargetFamily
from mountainash_transport.connections.tunnel import _PatchedEndpointProfile


class TestPatchedEndpointEmit:
    def test_emit_patches_hostname_and_port(self):
        from mountainash_transport.settings.storage.profiles.sftp_storage_profile import SFTPStorageProfile
        inner = SFTPStorageProfile(HOST="real-remote", USERNAME="u", PORT=22)
        patched = _PatchedEndpointProfile(inner, "127.0.0.1", 54321)
        out = patched.emit(TargetFamily.PARAMIKO)
        assert out["hostname"] == "127.0.0.1"
        assert out["port"] == 54321

    def test_emit_patches_endpoint_url(self):
        from mountainash_transport.settings.storage.profiles.http_storage_profile import HTTPStorageProfile
        # HTTP profile emits no endpoint_url, so use S3 (emits endpoint_url for minio).
        from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile
        inner = S3StorageProfile(FLAVOR="minio", ENDPOINT_URL="http://real:9000", REGION="us-east-1")
        patched = _PatchedEndpointProfile(inner, "127.0.0.1", 7777)
        out = patched.emit(TargetFamily.BOTO)
        assert out["endpoint_url"] == "http://127.0.0.1:7777"
```

- [ ] **Step 2: Run to verify fail**

Run: `hatch run test:test tests/connections/test_tunnel_connection.py -k TestPatchedEndpointEmit -v`
Expected: FAIL — `emit` is delegated via `__getattr__` to the inner profile and returns the UNPATCHED host/port.

- [ ] **Step 3: Refactor the patch into a helper + add `emit()`**

In `tunnel.py`, factor the patch logic out of `to_handler_kwargs` into a private helper and call it from both `to_handler_kwargs` and the new `emit`:

```python
    def _patch_endpoint(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        if "hostname" in kwargs:
            kwargs["hostname"] = self._host
            kwargs["port"] = self._port
        for key in self._URL_KEYS:
            if key in kwargs:
                kwargs[key] = f"http://{self._host}:{self._port}"
        return kwargs

    def to_handler_kwargs(self) -> dict[str, t.Any]:
        return self._patch_endpoint(self._inner.to_handler_kwargs())

    def emit(self, *args: t.Any, **kwargs: t.Any) -> dict[str, t.Any]:
        # MUST override (not delegate via __getattr__) so the tunnel's local
        # endpoint is injected — otherwise the inner profile's emit returns the
        # real remote host/port and the tunnel is silently bypassed.
        return self._patch_endpoint(self._inner.emit(*args, **kwargs))
```

> Behavior-preserving: the patch is top-level only, exactly as today (the S3 assume-role nested `endpoint_url` is not patched — unchanged pre-existing behavior; out of scope).

- [ ] **Step 4: Run the tunnel tests**

Run: `hatch run test:test tests/connections/test_tunnel_connection.py -v`
Expected: PASS (new group + existing tunnel tests, including the existing `to_handler_kwargs` patch test which now routes through `_patch_endpoint`).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/connections/tunnel.py tests/connections/test_tunnel_connection.py
git commit -m "feat: _PatchedEndpointProfile.emit() override for tunnel endpoint patching"
```

---

### Task 5: Factory `_emit_kwargs` migration to `emit(family)`

**Files:**
- Modify: `src/mountainash_transport/connections/__init__.py`
- Test: `tests/connections/test_factory.py` (add `emit()` to the connected fakes), `tests/connections/test_emission_golden.py`

- [ ] **Step 1: Migrate `_emit_kwargs`**

Replace the body of `_emit_kwargs` (currently builds `base = profile.to_handler_kwargs()`) so the storage config also flows through `emit(family)`, preserving the S3 nested-`base_kwargs` layering exactly:

```python
def _emit_kwargs(
    profile: ProfileProtocol,
    auth_profile: AuthProfile | None,
    family: TargetFamily | None,
) -> dict[str, t.Any]:
    """Assemble connection kwargs: storage config via emit(family), then auth
    credentials layered on the same family.

    family is None (Local / unmapped) → no SDK emission; fall back to
    to_handler_kwargs (Local keeps its real method). For the S3 assume-role
    envelope (nested base_kwargs), credentials emit onto the inner base_kwargs.
    """
    from mountainash_auth_client import NoAuthProfile

    if family is None:
        return profile.to_handler_kwargs()

    base = profile.emit(family)
    if auth_profile is None or isinstance(auth_profile, NoAuthProfile):
        return base
    if "base_kwargs" in base:
        return {**base, "base_kwargs": auth_profile.emit(family, base=base["base_kwargs"])}
    return auth_profile.emit(family, base=base)
```

(Other functions in `connections/__init__.py` are unchanged. `_family_for_provider` already returns the right `TargetFamily` for connected providers and `None` for Local/unmapped.)

- [ ] **Step 2: Verify the Phase-3 golden + factory tests still pass**

Run: `hatch run test:test tests/connections/test_emission_golden.py tests/connections/test_factory.py -v`
Expected: PASS unchanged. `test_emission_golden.py`'s `TestS3RoleArnLayering` exercises `_emit_kwargs` with a nested `base_kwargs` envelope — the migrated version must keep credentials landing inside `base_kwargs` with the outer `role_arn`/`session_name` untouched. Note: that test uses a fake profile with `to_handler_kwargs()`; see Step 3.

- [ ] **Step 3: Teach the factory-test fakes to `emit()`**

Since `_emit_kwargs` now calls `profile.emit(family)` for non-None families, every hand-rolled fake profile a factory test passes through `create_connection`/`_emit_kwargs` must expose an `emit()` returning the SAME dict its `to_handler_kwargs()` did (so the layering assertions are unchanged). Two test files have such fakes:

**(i) `tests/connections/test_factory.py`** — add `emit()` to the three CONNECTED fakes (leave `FakeLocalProfile` alone — provider `local` → `family is None` → the factory still calls `to_handler_kwargs()`):

```python
class FakeS3Profile:
    class __spec__:
        provider_type = "s3"

    def to_handler_kwargs(self):
        return {"service_name": "s3", "region_name": "us-east-1"}

    def emit(self, target=None, *, base=None):
        return {**(base or {}), "service_name": "s3", "region_name": "us-east-1"}

    def get_connection_url(self):
        return "s3://b/k"
```

```python
class FakeHTTPProfile:
    class __spec__:
        provider_type = "http"

    def to_handler_kwargs(self) -> dict:
        return {"timeout": 30}

    def emit(self, target=None, *, base=None) -> dict:
        return {**(base or {}), "timeout": 30}

    def get_connection_url(self) -> str:
        return "https://example.com"
```

```python
class FakeSFTPProfile:
    class __spec__:
        provider_type = "sftp"

    def to_handler_kwargs(self) -> dict:
        return {
            "hostname": "example.com", "port": 22, "username": "user",
            "_post_connect": {"host_key_policy": "auto_add"},
        }

    def emit(self, target=None, *, base=None) -> dict:
        return {
            **(base or {}),
            "hostname": "example.com", "port": 22, "username": "user",
            "_post_connect": {"host_key_policy": "auto_add"},
        }

    def get_connection_url(self) -> str:
        return "sftp://user@example.com:22"
```

**(ii) `tests/connections/test_emission_golden.py`** — `TestS3RoleArnLayering` and `TestPerLeafEmission` use fakes exposing only `to_handler_kwargs()`. Add an `emit(self, target=None, *, base=None)` returning the same dict each `to_handler_kwargs()` returns (the S3 fake returns the nested `{"base_kwargs": ..., "role_arn": ..., "session_name": ...}`; the SFTP fake returns `{"hostname": "h"}`). Keep all assertions identical.

> Keeps the golden tests meaningful: they assert the factory's auth-credential layering onto the storage `emit(family)` base — the exact contract Phase 4 changes. Do not weaken assertions; only teach the fakes to `emit`. The `{**(base or {}), ...}` form mirrors the real `emit` so a future caller passing `base=` still composes.

- [ ] **Step 4: Run the connections suite**

Run: `hatch run test:test tests/connections/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/connections/__init__.py tests/connections/test_emission_golden.py
git commit -m "refactor: factory _emit_kwargs builds storage base via emit(family)"
```

---

### Task 6: Full suite + lint + types + cross-backend check

**Files:** none (verification + fixups).

- [ ] **Step 1: Full suite**

Run: `hatch run test:test -q`
Expected: all pass. Watch `tests/storage/backends/test_s3.py`, `tests/storage/backends/test_http.py`, `tests/storage/backends/test_sftp.py`, `tests/cross_backend/`, `tests/storage_facade/` — any test that builds a connection through a real profile now flows through `emit(family)`.

- [ ] **Step 2: Lint**

Run: `hatch run ruff:check`
Expected: clean. Remove dead imports/code the migration left (e.g. SFTP `_DRIVER_KEYS` if unused, any now-unused imports in the profile modules).

- [ ] **Step 3: Type check**

Run: `hatch run mypy:check`
Expected: no NEW errors vs the develop baseline (the repo carries a known set of `import-untyped` + pre-existing arg-type errors; compare counts if unsure).

- [ ] **Step 4: Confirm describe-only profiles untouched**

Run:

```bash
grep -rn "__adapters__\|_sdk_family" src/mountainash_transport/settings/storage/profiles/
```

Expected: only `s3_storage_profile.py`, `http_storage_profile.py`, `sftp_storage_profile.py` (the connected three). Azure/GCS/FTP/SMB/GitHub/Local must NOT have been given adapters.

- [ ] **Step 5: Commit any fixups**

```bash
git add -A
git commit -m "chore: lint/type fixups for storage emission (Phase 4)"
```

---

## Self-Review Checklist (controller runs before dispatch)

1. **Spec coverage:** 2-arg `__adapters__` building on driver_key for the 3 connected profiles (Tasks 1-3); targeted emit / fail-closed (each task's `test_emit_no_target_fails_closed`); `_PatchedEndpointProfile.emit()` override (Task 4); factory two-stage `emit(family)` pipeline preserving S3 `base_kwargs` (Task 5); D2a shim + `_sdk_family` (Tasks 1-3); D5 Local untouched (Task 6 Step 4). ✅
2. **Golden equivalence (the safety net):** S3 flavor matrix + role envelope + Config fields + timeouts (Task 1); HTTP Timeout/headers (Task 2); SFTP driver_keys + post-connect (Task 3); each has a `shim == emit` test. Existing profile tests (which assert `to_handler_kwargs`) double as back-compat verification. ✅
3. **Out of scope (correctly excluded):** describe-only profiles, Local, SDK-behavior changes. ✅
4. **Type/name consistency:** `_sdk_family() -> TargetFamily`; adapters are 2-arg `(profile, kw) -> dict`; `emit(family)` everywhere. ✅
5. **Sequencing:** profiles first (1-3), then tunnel (4), then factory (5) — the factory migration depends on the profiles being emit-capable; each task is independently green. ✅

---

## Risks

- **S3 golden-identity is the highest risk** (flavor dispatch + computed endpoint/addressing + Config object + nested envelope). Mitigated by the flavor-matrix golden tests + the `shim == emit` test + the pre-existing S3 profile tests. The adapter body is the existing computed code moved with minimal change (seeded from `kw`, every computed key set explicitly).
- **`botocore.config.Config` has no stable `__eq__`** — golden tests compare the dict minus `config`, then assert `config.s3` / `config.connect_timeout` / `config.read_timeout` explicitly.
- **`httpx.Timeout` equality** — it implements `__eq__`; the HTTP golden test relies on that.
- **Phase-3 `base_kwargs` layering must be preserved** — covered by reusing `test_emission_golden.py::TestS3RoleArnLayering` (with the fake updated to `emit`).
- **Downstream consumers of `to_handler_kwargs()`** (e.g. `mountainash-data`) — the D2a shim keeps them working unchanged; removal is a later coordinated major.
