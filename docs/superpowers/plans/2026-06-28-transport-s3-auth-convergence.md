# Transport S3 Auth/Connection Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring transport's S3 path in line with the ecosystem auth/connection layering rule, dedupe `ROLE_ARN` onto auth, make STS assume-role a real working capability, and make the dead `supported_auth` metadata load-bearing.

**Architecture:** Four layers. L1 config (`S3StorageProfile` + `_s3_boto_kwargs`) emits a flat boto client-config dict. L2 auth (`IAMAuthProfile`, auth-client, unchanged) is pure data. L3 applier (`_emit_kwargs`) builds a Session-instruction envelope from the auth profile and performs no I/O. L4 connection (`S3Connection`) executes the boto3/STS calls. A cross-cutting `supported_auth` check is added to `create_connection`.

**Tech Stack:** Python 3.10+, boto3/botocore (optional S3 extra), pydantic-based `mountainash_settings.Profile`, `mountainash_auth_client` schemas, pytest.

## Global Constraints

- **Transport-only. Do NOT edit `mountainash-auth-client`.** `IAMAuthProfile` already carries `ROLE_ARN`/`PROFILE_NAME`/`ACCESS_KEY_ID`/`SECRET_ACCESS_KEY`/`SESSION_TOKEN`; consume them, do not change them.
- **Keep `auth_profile.emit(family, base=…)`** — it is consistent with as-built auth-client. Do NOT remove `emit()` usage from transport.
- **Layering invariant:** the L3 applier (`_emit_kwargs`) renders the kwargs *shape* and performs NO I/O. All boto3/botocore/STS calls live in L4 (`S3Connection`).
- **Exact botocore assume-role construction** (verified against botocore 1.34.x): `AssumeRoleCredentialFetcher(client_creator=<botocore session>.create_client, source_credentials=<botocore session>.get_credentials(), role_arn=…, extra_args={"RoleSessionName": …})` → `DeferredRefreshableCredentials(fetcher.fetch_credentials, "assume-role")` → attach to `botocore.session.get_session()` → `boto3.Session(botocore_session=…)`.
- **`PROFILE_NAME` is NOT flavor-guarded;** only `ROLE_ARN` is (raises for `r2`/`minio`/`b2`).
- **No count-based assertions.** Compare `botocore.config.Config` **field-by-field** (`cfg.s3`, `cfg.connect_timeout`, …), never whole-object — two `Config` instances never compare equal. The existing `_split_config` helper in `tests/settings/storage/profiles/test_s3_settings.py` is the pattern.
- **CalVer** versioning; commit trailer on every commit: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Branch: `feature/s3-auth-convergence` (already created off `develop`; the spec is already committed there).
- Run tests with `hatch run test:test-target <path>` (or `pytest <path> -v` inside the test env).

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `src/.../settings/storage/profiles/s3_storage_profile.py` | L1 config: ParameterSpecs + `_s3_boto_kwargs` adapter | 1, 3 |
| `src/.../settings/storage/profiles/sftp_storage_profile.py` | SFTP `supported_auth` set | 2 |
| `src/.../settings/storage/profiles/github_storage_profile.py` | GitHub `supported_auth` set | 2 |
| `src/.../connections/__init__.py` | L3 applier `_emit_kwargs` + `create_connection` enforcement + `_auth_kind` | 2, 4 |
| `src/.../connections/s3.py` | L4 `S3Connection` Session/STS execution | 5 |
| `tests/settings/storage/profiles/test_s3_settings.py` | S3 config/emit tests | 1, 3 |
| `tests/connections/test_factory.py` | factory + enforcement tests | 2 |
| `tests/connections/test_emission_golden.py` | applier envelope tests | 4 |
| `tests/connections/test_s3_connection.py` (new) | S3Connection STS tests | 5 |

Paths abbreviate `src/mountainash_transport/`.

---

### Task 1: Drop the dead S3 `driver_key`s (double-render cleanup)

`REGION`, `USE_SSL`, `ENDPOINT_URL` declare `driver_key`s that `_s3_boto_kwargs` then overwrites/pops for every flavor. Remove the `driver_key`s; the adapter is the sole source of truth. This is behavior-preserving — the existing `TestS3EmitGolden` suite pins the exact output and must stay green.

**Files:**
- Modify: `src/.../settings/storage/profiles/s3_storage_profile.py` (ParameterSpecs at lines ~76-82, ~104-114, ~115-122)
- Test: `tests/settings/storage/profiles/test_s3_settings.py` (rename/recomment `test_driver_keys_preserved_in_emit` at lines ~318-324)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `_s3_boto_kwargs(profile, kw)` output is byte-equivalent (field-level) to before; no signature change.

- [ ] **Step 1: Add a characterization test proving the adapter (not `driver_key`) owns the three fields**

In `tests/settings/storage/profiles/test_s3_settings.py`, rename `test_driver_keys_preserved_in_emit` (lines ~318-324) and broaden it:

```python
def test_adapter_is_sole_source_of_region_use_ssl_endpoint(self):
    # REGION/USE_SSL/ENDPOINT_URL are computed by the adapter, not by driver_key
    # passthrough. r2 forces region_name='auto'; aws omits endpoint_url; USE_SSL
    # flows through the adapter.
    aws = S3StorageProfile(FLAVOR="aws", REGION="eu-west-1", USE_SSL=False)
    flat, _ = _split_config(aws.emit(TargetFamily.BOTO))
    assert flat["region_name"] == "eu-west-1"
    assert flat["use_ssl"] is False
    assert "endpoint_url" not in flat                      # aws: popped by adapter

    r2 = S3StorageProfile(FLAVOR="r2", ACCOUNT_ID="acct123", REGION="eu-west-1")
    flat_r2, _ = _split_config(r2.emit(TargetFamily.BOTO))
    assert flat_r2["region_name"] == "auto"               # adapter overrides REGION
    assert flat_r2["endpoint_url"] == "https://acct123.r2.cloudflarestorage.com"
```

- [ ] **Step 2: Run the S3 emit suite to establish the green baseline**

Run: `hatch run test:test-target tests/settings/storage/profiles/test_s3_settings.py -v`
Expected: PASS (the new test passes against current code — the adapter already produces these values).

- [ ] **Step 3: Remove the three `driver_key` declarations**

In `s3_storage_profile.py`, delete `driver_key="region_name"` from the `REGION` ParameterSpec, `driver_key="endpoint_url"` from `ENDPOINT_URL`, and `driver_key="use_ssl"` from `USE_SSL`. Leave every other field of those specs (name/type/tier/default/description/validator) intact. Example for `REGION`:

```python
        ParameterSpec(
            name="REGION",
            type=str,
            tier="core",
            default="us-east-1",
            description="AWS-style region name (e.g. us-east-1).",
        ),
```

(Do the same for `ENDPOINT_URL` and `USE_SSL` — drop only the `driver_key=` line.)

- [ ] **Step 4: Run the full S3 settings suite — behavior preserved**

Run: `hatch run test:test-target tests/settings/storage/profiles/test_s3_settings.py -v`
Expected: PASS — `TestS3EmitGolden` (all five flavors), `TestS3HandlerKwargsMatrix`, and the new characterization test all green. No output changed.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/settings/storage/profiles/s3_storage_profile.py \
        tests/settings/storage/profiles/test_s3_settings.py
git commit -m "refactor(s3): drop dead REGION/USE_SSL/ENDPOINT_URL driver_keys

The adapter computes all three flavor-aware and overwrites the driver_key
values; the declarations were dead and misleading. Behavior-preserving —
TestS3EmitGolden unchanged.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: General `supported_auth` enforcement + set corrections

Make `supported_auth` load-bearing in `create_connection`, deriving the auth mode from `auth_profile.__spec__.provider_type`. Correct the three sets the change exposes (S3 `−TOKEN`, SFTP `+NONE`, GitHub `−OAUTH2`). Enforcement skips profiles whose `__spec__` carries no `supported_auth` (bare protocol fakes), preserving the factory's tolerance.

**Files:**
- Modify: `src/.../connections/errors.py` (generalize `UnsupportedAuthProfileError` to accept a `reason=`)
- Modify: `src/.../connections/__init__.py` (add `_auth_kind`; insert enforcement in `create_connection` after the OAuth reject at lines ~129-138, before `provider_type = _provider_type_from_profile(profile)` at line ~140)
- Modify: `src/.../settings/storage/profiles/s3_storage_profile.py` (`supported_auth` at line ~181)
- Modify: `src/.../settings/storage/profiles/sftp_storage_profile.py` (`supported_auth` at line ~160)
- Modify: `src/.../settings/storage/profiles/github_storage_profile.py` (`supported_auth` at line ~92)
- Test: `tests/connections/test_factory.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `_auth_kind(auth_profile: AuthProfile | None) -> CONST_AUTH_PROFILES` in `connections/__init__.py`. `create_connection` now raises `UnsupportedAuthProfileError` when the mode is outside a provider's `supported_auth`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/connections/test_factory.py`:

```python
class _FakeS3SpecProfile:
    """S3-like profile whose __spec__ carries a real supported_auth set."""
    class __spec__:
        from mountainash_auth_client import CONST_AUTH_PROFILES as _C
        provider_type = "s3"
        supported_auth = frozenset({_C.IAM, _C.NONE})

    def emit(self, target=None, *, base=None):
        return {**(base or {}), "service_name": "s3", "region_name": "us-east-1"}

    def to_handler_kwargs(self):
        return {"service_name": "s3", "region_name": "us-east-1"}

    def get_connection_url(self):
        return "s3://b/k"


class TestSupportedAuthEnforcement:
    def test_auth_kind_maps_profiles(self):
        from mountainash_auth_client import (
            CONST_AUTH_PROFILES, IAMAuthProfile, NoAuthProfile, TokenAuthProfile,
        )
        from mountainash_transport.connections import _auth_kind
        assert _auth_kind(None) is CONST_AUTH_PROFILES.NONE
        assert _auth_kind(NoAuthProfile()) is CONST_AUTH_PROFILES.NONE
        assert _auth_kind(IAMAuthProfile(ACCESS_KEY_ID="a", SECRET_ACCESS_KEY="b")) is CONST_AUTH_PROFILES.IAM
        assert _auth_kind(TokenAuthProfile(TOKEN="t")) is CONST_AUTH_PROFILES.TOKEN

    def test_token_on_s3_rejected(self):
        from mountainash_auth_client import TokenAuthProfile
        from mountainash_transport.connections.errors import UnsupportedAuthProfileError
        with pytest.raises(UnsupportedAuthProfileError):
            create_connection(_FakeS3SpecProfile(), TokenAuthProfile(TOKEN="t"))

    def test_iam_on_s3_allowed(self):
        conn = create_connection(_FakeS3SpecProfile(), IAMAuthProfile(ACCESS_KEY_ID="a", SECRET_ACCESS_KEY="b"))
        assert conn._connect_kwargs["aws_access_key_id"] == "a"

    def test_specless_fake_skips_enforcement(self):
        # FakeHTTPProfile.__spec__ has no supported_auth → enforcement skipped,
        # preserving the factory's tolerance for bare ProfileProtocol impls.
        # JWT would be outside http's real set {NONE,TOKEN,PASSWORD}; the specless
        # fake has no set so it passes (and JWTAuthProfile emits a Bearer on HTTP,
        # so dispatch succeeds — unlike TokenAuthProfile on a BOTO fake, whose
        # emit(BOTO) fails closed).
        from mountainash_auth_client import JWTAuthProfile
        conn = create_connection(FakeHTTPProfile(), JWTAuthProfile(TOKEN="jw7"))
        assert conn is not None
```

- [ ] **Step 2: Run to verify they fail**

Run: `hatch run test:test-target tests/connections/test_factory.py::TestSupportedAuthEnforcement -v`
Expected: FAIL — `_auth_kind` does not exist (ImportError); `test_token_on_s3_rejected` does not raise.

- [ ] **Step 3a: Generalize `UnsupportedAuthProfileError`**

The current message hardcodes OAuth guidance ("use OAuth2Connection…"), which would mislead a non-OAuth rejection (e.g. TOKEN-on-S3). In `src/.../connections/errors.py`, replace `UnsupportedAuthProfileError.__init__` (lines ~56-62) so it accepts an optional `reason`; the OAuth call site passes no reason and keeps today's message:

```python
    def __init__(self, profile_name: str, *, reason: str | None = None) -> None:
        self.profile_name = profile_name
        if reason is not None:
            super().__init__(f"{profile_name} is not supported: {reason}")
        else:
            super().__init__(
                f"{profile_name} is not supported by transport's create_connection; "
                "use mountainash-auth-client's OAuth2Connection/OAuth1Connection with "
                "an OAuth2ProviderProfile/OAuth1ProviderProfile instead."
            )
```

(The existing OAuth reject site `raise UnsupportedAuthProfileError(type(auth_profile).__name__)` is unchanged — no `reason`, so it still gets the OAuth message.)

- [ ] **Step 3b: Add `_auth_kind` and enforcement**

In `src/.../connections/__init__.py`, add after the imports (the file already imports `TargetFamily`; add `CONST_AUTH_PROFILES`):

```python
from mountainash_auth_client import CONST_AUTH_PROFILES


def _auth_kind(auth_profile: AuthProfile | None) -> CONST_AUTH_PROFILES:
    """Derive the auth mode from an auth profile's spec provider_type.

    None → NONE. Every *AuthProfile's __spec__.provider_type string is a
    CONST_AUTH_PROFILES member value (e.g. "iam", "token", "none").
    """
    if auth_profile is None:
        return CONST_AUTH_PROFILES.NONE
    provider_type = getattr(getattr(auth_profile, "__spec__", None), "provider_type", None)
    if provider_type is None:
        return CONST_AUTH_PROFILES.NONE
    return CONST_AUTH_PROFILES(str(provider_type))
```

In `create_connection`, immediately after the OAuth `raise UnsupportedAuthProfileError(...)` block (line ~138) and before `provider_type = _provider_type_from_profile(profile)` (line ~140), insert:

```python
    spec = getattr(profile, "__spec__", None)
    supported = getattr(spec, "supported_auth", None)
    if supported is not None:
        mode = _auth_kind(auth_profile)
        if mode not in supported:
            from .errors import UnsupportedAuthProfileError
            name = type(auth_profile).__name__ if auth_profile else "NoAuth"
            raise UnsupportedAuthProfileError(
                name,
                reason=f"mode {mode.value} not in supported_auth "
                       f"{sorted(m.value for m in supported)}",
            )
```

- [ ] **Step 4: Apply the three set corrections**

- `s3_storage_profile.py` line ~181:
  ```python
  supported_auth=frozenset({CONST_AUTH_PROFILES.IAM, CONST_AUTH_PROFILES.NONE}),
  ```
- `sftp_storage_profile.py` line ~160 — add `NONE` (SSH-agent / default-key path uses `auth_profile=None`):
  ```python
  supported_auth=frozenset({CONST_AUTH_PROFILES.PASSWORD, CONST_AUTH_PROFILES.CERTIFICATE, CONST_AUTH_PROFILES.KERBEROS, CONST_AUTH_PROFILES.NONE}),
  ```
- `github_storage_profile.py` line ~92 — drop `OAUTH2` (OAuth is rejected before enforcement; transport's OAuth connections were deleted):
  ```python
  supported_auth=frozenset({CONST_AUTH_PROFILES.TOKEN, CONST_AUTH_PROFILES.JWT, CONST_AUTH_PROFILES.NONE}),
  ```

- [ ] **Step 5: Add the SFTP-None regression test**

Add to `tests/connections/test_factory.py`:

```python
class TestSftpNoneAllowed:
    def test_real_sftp_profile_accepts_no_auth(self):
        # SFTP's set now includes NONE; SSH-agent / default-key path must survive
        # enforcement. Uses the real profile so __spec__.supported_auth is live.
        from mountainash_transport.settings.storage.profiles import SFTPStorageProfile
        from mountainash_transport.connections.sftp import SFTPConnection
        prof = SFTPStorageProfile(HOST="h.example.com", USERNAME="u")
        conn = create_connection(prof, auth_profile=None)
        assert isinstance(conn, SFTPConnection)
```

(`HOST` and `USERNAME` are the two `MISSING`-default required fields on `SFTPStorageProfile`; `PORT` defaults to 22.)

- [ ] **Step 6: Run the factory suite**

Run: `hatch run test:test-target tests/connections/test_factory.py -v`
Expected: PASS — new enforcement tests pass; the existing `test_bearer_auth` (TOKEN on HTTP, allowed) and `test_oauth2_auth_raises_unsupported` (still rejected by the OAuth isinstance check) stay green.

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_transport/connections/errors.py \
        src/mountainash_transport/connections/__init__.py \
        src/mountainash_transport/settings/storage/profiles/s3_storage_profile.py \
        src/mountainash_transport/settings/storage/profiles/sftp_storage_profile.py \
        src/mountainash_transport/settings/storage/profiles/github_storage_profile.py \
        tests/connections/test_factory.py
git commit -m "feat(connections): enforce supported_auth in create_connection

Derive auth mode from __spec__.provider_type; reject modes outside a
provider's supported_auth. Corrections shipped together: S3 -TOKEN,
SFTP +NONE (agent/default-key path), GitHub -OAUTH2 (rejected upstream).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `ROLE_ARN` auth-only — flat config emit

Remove `ROLE_ARN` from `S3StorageProfile` and the assume-role envelope from `_s3_boto_kwargs`. After this task the adapter always returns a flat boto config dict; the role lives only on `IAMAuthProfile` (consumed by the applier in Task 4).

**Files:**
- Modify: `src/.../settings/storage/profiles/s3_storage_profile.py` (delete `ROLE_ARN` ParameterSpec at lines ~152-158; delete the `if role_arn:` branch in `_s3_boto_kwargs` at lines ~218, ~252-257)
- Test: `tests/settings/storage/profiles/test_s3_settings.py` (delete `TestS3RoleArnEnvelope` lines ~163-184 and `test_role_arn_nested_envelope` lines ~305-316)

**Interfaces:**
- Consumes: nothing.
- Produces: `_s3_boto_kwargs` always returns a flat dict `{service_name, region_name, use_ssl, verify, config, endpoint_url?}` — never `{base_kwargs, role_arn, session_name}`. `S3StorageProfile` no longer has a `ROLE_ARN` field.

**Ordering note:** This task does NOT touch `connections/__init__.py` (`_emit_kwargs`) or `tests/connections/test_emission_golden.py` — those are Task 4. The existing `test_emission_golden.py::TestS3RoleArnLayering` still passes after this task because `_emit_kwargs` is unchanged (its `if "base_kwargs" in base` branch survives until Task 4 rewrites both the applier and that test together). Run only the S3-settings suite in this task's gate.

- [ ] **Step 1: Write the failing test**

Add to `tests/settings/storage/profiles/test_s3_settings.py`:

```python
class TestS3RoleArnRemoved:
    def test_role_arn_not_a_field(self):
        assert "ROLE_ARN" not in S3StorageProfile.model_fields

    def test_emit_is_always_flat(self):
        # Even constructed without any role concept, emit never nests base_kwargs.
        p = S3StorageProfile(FLAVOR="aws", REGION="us-east-1")
        out = p.emit(TargetFamily.BOTO)
        assert "base_kwargs" not in out
        assert "role_arn" not in out
```

- [ ] **Step 2: Run to verify it fails**

Run: `hatch run test:test-target tests/settings/storage/profiles/test_s3_settings.py::TestS3RoleArnRemoved -v`
Expected: FAIL — `ROLE_ARN` is still in `model_fields`.

- [ ] **Step 3: Remove `ROLE_ARN` and the envelope branch**

In `s3_storage_profile.py`:
- Delete the entire `ROLE_ARN` ParameterSpec (lines ~152-158).
- In `_s3_boto_kwargs`, delete `role_arn = getattr(profile, "ROLE_ARN", None)` (line ~218) and replace the tail (lines ~252-258):
  ```python
      if role_arn:
          return {
              "base_kwargs": base,
              "role_arn": role_arn,
              "session_name": "mountainash-transport",
          }
      return base
  ```
  with simply:
  ```python
      return base
  ```

- [ ] **Step 4: Delete the now-invalid config envelope tests**

Delete `TestS3RoleArnEnvelope` (lines ~163-184) and `test_role_arn_nested_envelope` (lines ~305-316) from `test_s3_settings.py` — the config layer no longer owns the assume-role envelope (it moves to the applier in Task 4).

- [ ] **Step 5: Run the S3 settings suite**

Run: `hatch run test:test-target tests/settings/storage/profiles/test_s3_settings.py -v`
Expected: PASS — `TestS3RoleArnRemoved` passes; `TestS3EmitGolden` (flat-output goldens) green; deleted envelope tests gone.

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/settings/storage/profiles/s3_storage_profile.py \
        tests/settings/storage/profiles/test_s3_settings.py
git commit -m "refactor(s3): ROLE_ARN is auth-only; adapter emits flat config

Remove ROLE_ARN from S3StorageProfile and the assume-role envelope from
_s3_boto_kwargs. Role now lives solely on IAMAuthProfile; the applier owns
the envelope (next task).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: L3 applier builds the assume-role / profile envelope

Teach `_emit_kwargs` to build the Session-instruction envelope for the BOTO family when the auth profile carries `ROLE_ARN` or `PROFILE_NAME`, applying the `ROLE_ARN`-only flavor guard. No I/O.

**Files:**
- Modify: `src/.../connections/__init__.py` (`_emit_kwargs` at lines ~86-113)
- Test: `tests/connections/test_emission_golden.py` (rewrite `TestS3RoleArnLayering` lines ~90-166)

**Interfaces:**
- Consumes: `_s3_boto_kwargs` flat output (Task 3); `IAMAuthProfile.ROLE_ARN`/`PROFILE_NAME` (auth-client).
- Produces: for BOTO + (`ROLE_ARN` or `PROFILE_NAME`), `_emit_kwargs` returns an envelope:
  ```python
  {"client_config": {...}, "session": {...}, "role_arn": str | None, "session_name": "mountainash-transport"}
  ```
  where `session` holds `aws_*` creds (if explicit) plus `profile_name` (if set) plus `region_name`. Otherwise unchanged flat behavior. Raises `ValueError` for `ROLE_ARN` + flavor ∈ {r2,minio,b2}.

- [ ] **Step 1: Write the failing tests**

Replace `TestS3RoleArnLayering` (lines ~90-166) in `tests/connections/test_emission_golden.py` with:

```python
@pytest.mark.unit
class TestS3AssumeRoleEnvelope:
    """The L3 applier builds the Session-instruction envelope from the auth
    profile (ROLE_ARN/PROFILE_NAME). S3Connection consumes it (see
    tests/connections/test_s3_connection.py)."""

    def _profile(self, flavor="aws"):
        from mountainash_transport.settings.storage.profiles import S3StorageProfile
        return S3StorageProfile(FLAVOR=flavor, REGION="us-east-1",
                                **({"ACCOUNT_ID": "a"} if flavor == "r2" else {}),
                                **({"ENDPOINT_URL": "http://m:9000"} if flavor == "minio" else {}))

    def _emit(self, profile, auth):
        from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as P
        from mountainash_transport.connections import _emit_kwargs, _family_for_provider
        return _emit_kwargs(profile, auth, _family_for_provider(P.S3))

    def test_role_arn_builds_envelope(self):
        out = self._emit(self._profile(), IAMAuthProfile(
            ACCESS_KEY_ID="AKIA", SECRET_ACCESS_KEY="sk",
            ROLE_ARN="arn:aws:iam::123:role/r"))
        assert out["role_arn"] == "arn:aws:iam::123:role/r"
        assert out["session_name"] == "mountainash-transport"
        assert out["client_config"]["service_name"] == "s3"
        assert out["session"]["aws_access_key_id"] == "AKIA"
        assert out["session"]["region_name"] == "us-east-1"

    def test_keyless_role_arn_is_ambient(self):
        out = self._emit(self._profile(), IAMAuthProfile(ROLE_ARN="arn:aws:iam::123:role/r"))
        assert out["role_arn"] == "arn:aws:iam::123:role/r"
        assert "aws_access_key_id" not in out["session"]   # ambient bootstrap

    def test_profile_name_builds_envelope_without_role(self):
        out = self._emit(self._profile(), IAMAuthProfile(PROFILE_NAME="dev"))
        assert out["role_arn"] is None
        assert out["session"]["profile_name"] == "dev"

    def test_profile_name_allowed_on_r2(self):
        out = self._emit(self._profile("r2"), IAMAuthProfile(PROFILE_NAME="dev"))
        assert out["session"]["profile_name"] == "dev"   # NOT guarded

    def test_role_arn_on_r2_raises(self):
        with pytest.raises(ValueError, match="assume-role"):
            self._emit(self._profile("r2"), IAMAuthProfile(ROLE_ARN="arn:aws:iam::123:role/r"))

    def test_plain_iam_stays_flat(self):
        out = self._emit(self._profile(), IAMAuthProfile(ACCESS_KEY_ID="AKIA", SECRET_ACCESS_KEY="sk"))
        assert "client_config" not in out          # flat path
        assert out["aws_access_key_id"] == "AKIA"
```

- [ ] **Step 2: Run to verify they fail**

Run: `hatch run test:test-target tests/connections/test_emission_golden.py::TestS3AssumeRoleEnvelope -v`
Expected: FAIL — `_emit_kwargs` returns the flat creds dict, no `client_config` key; r2+role does not raise.

- [ ] **Step 3: Rewrite `_emit_kwargs`**

Replace the body of `_emit_kwargs` (lines ~86-113) in `connections/__init__.py` with:

```python
_NON_STS_FLAVORS = frozenset({"r2", "minio", "b2"})


def _emit_kwargs(
    profile: ProfileProtocol,
    auth_profile: AuthProfile | None,
    family: TargetFamily | None,
) -> dict[str, t.Any]:
    """Assemble connection kwargs. For BOTO with ROLE_ARN/PROFILE_NAME, build a
    Session-instruction envelope (consumed by S3Connection); otherwise layer
    credentials flat. Performs NO I/O."""
    from mountainash_auth_client import NoAuthProfile

    if family is None:
        return profile.to_handler_kwargs()

    emit = getattr(profile, "emit", None)
    base = emit(family) if callable(emit) else profile.to_handler_kwargs()

    if auth_profile is None or isinstance(auth_profile, NoAuthProfile):
        return base

    if family is TargetFamily.BOTO:
        role_arn = getattr(auth_profile, "ROLE_ARN", None)
        profile_name = getattr(auth_profile, "PROFILE_NAME", None)
        if role_arn or profile_name:
            flavor = getattr(profile, "FLAVOR", "aws")
            if role_arn and flavor in _NON_STS_FLAVORS:
                raise ValueError(
                    f"assume-role (ROLE_ARN) is not supported for S3 flavor {flavor!r}; "
                    "only aws/express reach AWS STS."
                )
            session: dict[str, t.Any] = dict(auth_profile.emit(family))  # aws_* creds or {}
            if profile_name:
                session["profile_name"] = profile_name
            if "region_name" in base:
                session["region_name"] = base["region_name"]
            return {
                "client_config": base,
                "session": session,
                "role_arn": role_arn,
                "session_name": "mountainash-transport",
            }

    return auth_profile.emit(family, base=base)
```

(Note: the old `if "base_kwargs" in base:` branch is removed — Task 3 stopped the config emitting that envelope.)

- [ ] **Step 4: Run the emission suite**

Run: `hatch run test:test-target tests/connections/test_emission_golden.py -v`
Expected: PASS — `TestS3AssumeRoleEnvelope` green; `TestStrictParity` / `TestIntentionalDivergence` / `TestPerLeafEmission` unchanged (HTTP/PARAMIKO paths untouched).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/connections/__init__.py \
        tests/connections/test_emission_golden.py
git commit -m "feat(connections): applier builds S3 assume-role/profile envelope

_emit_kwargs renders the Session-instruction envelope from IAMAuthProfile
ROLE_ARN/PROFILE_NAME with the ROLE_ARN-only flavor guard. No I/O — that
stays in S3Connection (next task).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: L4 `S3Connection` — Session build + STS assume-role execution

Consume the envelope: build a boto3 source `Session` (explicit keys / named profile / ambient), optionally assume a role via botocore refreshable credentials, then create the S3 client. Flat dicts use the existing plain path unchanged.

**Files:**
- Modify: `src/.../connections/s3.py` (`connect` at lines ~19-39)
- Test: `tests/connections/test_s3_connection.py` (**already exists** with `TestS3ConnectionProtocol` / `TestS3ConnectionLifecycle` — APPEND the new classes below; do NOT overwrite the file or remove existing classes)

**Interfaces:**
- Consumes: the envelope from `_emit_kwargs` (Task 4): `{"client_config", "session", "role_arn", "session_name"}`.
- Produces: a connected `S3Connection` whose `.client` is a boto3 S3 client. Raises `ValueError` for `PROFILE_NAME` + explicit keys; `TransportConnectionError` when assume-role has no resolvable source creds.

**Edge note (accepted minor):** `has_keys` checks `aws_access_key_id` only. A malformed `IAMAuthProfile` with a lone secret / session token and no access key is treated as ambient — credential *completeness* is `IAMAuthProfile`'s concern (auth-client), not transport's. Do not add a guard here.

- [ ] **Step 1: Write the failing tests**

APPEND to the existing `tests/connections/test_s3_connection.py` (keep `TestS3ConnectionProtocol` / `TestS3ConnectionLifecycle`). If `patch`, `MagicMock`, `pytest`, `S3Connection`, `TransportConnectionError` are not already imported at the top of that file, add the missing imports. Then add:

```python
def _envelope(*, session=None, role_arn=None):
    return {
        "client_config": {"service_name": "s3", "region_name": "us-east-1",
                          "use_ssl": True, "verify": True},
        "session": session if session is not None else {"region_name": "us-east-1"},
        "role_arn": role_arn,
        "session_name": "mountainash-transport",
    }


@pytest.mark.unit
class TestS3ConnectionFlatPath:
    def test_flat_dict_builds_plain_client(self):
        with patch("boto3.client") as mk:
            S3Connection({"service_name": "s3", "region_name": "us-east-1",
                          "aws_access_key_id": "AKIA"}).connect()
            # service_name is popped; passed positionally as "s3".
            args, kwargs = mk.call_args
            assert args[0] == "s3"
            assert "service_name" not in kwargs
            assert kwargs["aws_access_key_id"] == "AKIA"


@pytest.mark.unit
class TestS3ConnectionProfileName:
    def test_profile_name_routes_to_session(self):
        with patch("boto3.Session") as MkSession:
            sess = MkSession.return_value
            S3Connection(_envelope(session={"profile_name": "dev", "region_name": "us-east-1"})).connect()
            MkSession.assert_called_once_with(profile_name="dev", region_name="us-east-1")
            sess.client.assert_called_once()
            assert sess.client.call_args[0][0] == "s3"

    def test_profile_name_and_keys_is_ambiguous(self):
        env = _envelope(session={"profile_name": "dev", "aws_access_key_id": "AKIA",
                                 "aws_secret_access_key": "sk", "region_name": "us-east-1"})
        with pytest.raises(ValueError, match="[Aa]mbiguous"):
            S3Connection(env).connect()


@pytest.mark.unit
class TestS3ConnectionAssumeRole:
    def test_assume_role_builds_refreshable_client(self):
        with patch("boto3.Session") as MkSession, \
             patch("botocore.session.get_session") as mk_get, \
             patch("mountainash_transport.connections.s3.AssumeRoleCredentialFetcher") as MkFetcher, \
             patch("mountainash_transport.connections.s3.DeferredRefreshableCredentials") as MkCreds:
            source = MkSession.return_value
            source._session.get_credentials.return_value = MagicMock()  # ambient present
            target = mk_get.return_value
            S3Connection(_envelope(role_arn="arn:aws:iam::123:role/r")).connect()
            # fetcher built with the role + session name
            _, fkwargs = MkFetcher.call_args
            assert fkwargs["role_arn"] == "arn:aws:iam::123:role/r"
            assert fkwargs["extra_args"] == {"RoleSessionName": "mountainash-transport"}
            # refreshable creds attached to the target botocore session
            assert target._credentials is MkCreds.return_value

    def test_assume_role_without_source_creds_raises(self):
        with patch("boto3.Session") as MkSession, \
             patch("botocore.session.get_session"):
            MkSession.return_value._session.get_credentials.return_value = None
            with pytest.raises(TransportConnectionError, match="credentials"):
                S3Connection(_envelope(role_arn="arn:aws:iam::123:role/r")).connect()
```

- [ ] **Step 2: Run to verify they fail**

Run: `hatch run test:test-target tests/connections/test_s3_connection.py -v`
Expected: FAIL — `S3Connection` does not branch on `client_config`; the assume-role symbols are not importable from `s3.py`.

- [ ] **Step 3: Rewrite `S3Connection.connect`**

Replace `connect` (lines ~19-39) in `connections/s3.py` and add the imports/helpers. Top of file, add the guarded botocore imports:

```python
try:
    import botocore.session
    from botocore.credentials import (
        AssumeRoleCredentialFetcher,
        DeferredRefreshableCredentials,
    )
except ImportError:  # pragma: no cover - botocore ships with boto3
    botocore = None  # type: ignore[assignment]
    AssumeRoleCredentialFetcher = None  # type: ignore[assignment]
    DeferredRefreshableCredentials = None  # type: ignore[assignment]
```

Replace `connect`:

```python
    def connect(self) -> Self:
        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError as exc:
            raise TransportConnectionError("boto3 is required for S3 connections") from exc

        try:
            if "client_config" in self._connect_kwargs:
                self._client = self._build_via_session(boto3)
            else:
                kwargs = dict(self._connect_kwargs)
                kwargs.pop("service_name", None)
                self._client = boto3.client("s3", **kwargs)
        except (ValueError, TransportConnectionError):
            raise
        except Exception as exc:
            raise TransportConnectionError(f"Failed to create S3 client: {exc}") from exc

        return self

    def _build_via_session(self, boto3: t.Any) -> t.Any:
        env = self._connect_kwargs
        session_inputs = dict(env["session"])
        client_config = dict(env["client_config"])
        client_config.pop("service_name", None)
        role_arn = env.get("role_arn")
        session_name = env.get("session_name", "mountainash-transport")

        profile_name = session_inputs.pop("profile_name", None)
        has_keys = "aws_access_key_id" in session_inputs
        if profile_name and has_keys:
            raise ValueError(
                "Ambiguous S3 credentials: set either PROFILE_NAME or explicit "
                "keys on the IAMAuthProfile, not both."
            )
        region = session_inputs.get("region_name")

        if profile_name:
            source = boto3.Session(profile_name=profile_name, region_name=region)
        elif has_keys:
            source = boto3.Session(**session_inputs)
        else:
            source = boto3.Session(region_name=region)

        if not role_arn:
            return source.client("s3", **client_config)

        bc = source._session
        verify = client_config.get("verify", True)

        def _sts_creator(*a: t.Any, **k: t.Any) -> t.Any:
            k.setdefault("verify", verify)
            return bc.create_client(*a, **k)

        src_creds = bc.get_credentials()
        if src_creds is None:
            raise TransportConnectionError(
                "assume-role requested but no source AWS credentials could be "
                "resolved (no explicit keys, named profile, or ambient credentials)."
            )

        fetcher = AssumeRoleCredentialFetcher(
            client_creator=_sts_creator,
            source_credentials=src_creds,
            role_arn=role_arn,
            extra_args={"RoleSessionName": session_name},
        )
        target = botocore.session.get_session()
        target._credentials = DeferredRefreshableCredentials(
            fetcher.fetch_credentials, "assume-role"
        )
        if region:
            target.set_config_variable("region", region)
        return boto3.Session(botocore_session=target).client("s3", **client_config)
```

- [ ] **Step 4: Run the S3Connection suite**

Run: `hatch run test:test-target tests/connections/test_s3_connection.py -v`
Expected: PASS — flat path, profile-name routing, ambiguity guard, refreshable assume-role wiring, and ambient-missing all green.

- [ ] **Step 5: Run the full connections + S3 settings suites**

Run: `hatch run test:test-target tests/connections/ tests/settings/storage/profiles/test_s3_settings.py -v`
Expected: PASS — no regressions across factory, emission goldens, S3 settings.

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/connections/s3.py tests/connections/test_s3_connection.py
git commit -m "feat(s3): real STS assume-role via botocore refreshable credentials

S3Connection consumes the applier envelope: builds a boto3 Session (keys /
named profile / ambient), assumes a role through AssumeRoleCredentialFetcher
+ DeferredRefreshableCredentials (auto-refresh), then creates the client.
Mutual-exclusion + ambient-missing guards included.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage:**
- Double-render (B) → Task 1. ✅
- `ROLE_ARN` auth-only (locked #1) → Task 3 (remove from config) + Task 4 (applier reads `IAMAuthProfile.ROLE_ARN`). ✅
- STS for real (locked #2) → Task 5 (botocore refreshable, exact verified signature). ✅
- Applier builds envelope / connection does I/O (locked #3) → Task 4 (no I/O) + Task 5 (I/O). ✅
- General `supported_auth` enforcement + SFTP/GitHub/S3 corrections (locked #4) → Task 2. ✅
- Flavor guard (`ROLE_ARN`-only, Codex #5) → Task 4. ✅
- `PROFILE_NAME` wiring (Codex #1) → Task 4 (envelope) + Task 5 (`Session(profile_name=…)`). ✅
- `TokenAuthProfile` removed from S3 (Codex #2) → Task 2. ✅
- Mutual-exclusion + ambient-missing (Codex #2) → Task 5. ✅
- STS leg `verify` (Codex #4) → Task 5 `_sts_creator`. ✅
- `Config` field-level comparison (Codex #6) → Global Constraints + Task 1 uses `_split_config`. ✅

**2. Placeholder scan:** No TBD/TODO. Every code step shows complete code. The one conditional ("if `SFTPStorageProfile` required fields differ…") points to the concrete source to read, not a vague instruction. ✅

**3. Type consistency:** Envelope keys `client_config`/`session`/`role_arn`/`session_name` are identical across Task 4 (producer) and Task 5 (consumer). `_auth_kind` signature matches between definition (Task 2 Step 3) and tests (Task 2 Step 1). `_emit_kwargs` signature unchanged from the existing code. ✅

**Note for executor:** Tasks 3→4 briefly leave assume-role non-functional end-to-end (config flat, applier not yet envelope-building) — this is acceptable because the path is already broken on `develop`; the per-task tests are layer-scoped and pass. The capability is whole only after Task 5.

**Plan-review corrections (Codex, this session):** points 1–4 confirmed sound (botocore signature + mock paths verified against botocore 1.34.x; `auth_profile.emit(BOTO)` returns clean `aws_*`-only dicts; every `__spec__.provider_type` maps to a `CONST_AUTH_PROFILES` member). Fixed: (5a) `test_specless_fake_skips_enforcement` rewritten to JWT-on-HTTP — `TokenAuthProfile.emit(BOTO)` fails closed, so the original premise was invalid; (6a) SFTP field is `HOST` not `HOSTNAME`; (6b) `tests/connections/test_s3_connection.py` already exists → Task 5 appends; (6c) `UnsupportedAuthProfileError` generalized with `reason=` so non-OAuth rejections don't emit OAuth guidance (Task 2 Step 3a). Task 3 ordering confirmed safe (old `TestS3RoleArnLayering` survives because `_emit_kwargs` is unchanged until Task 4).
