# Transport S3 Auth / Connection Convergence — Design Spec

**Date:** 2026-06-28
**Repo:** mountainash-transport
**Status:** Design — approved in brainstorming, not yet planned
**Scope:** transport-only (no auth-client change)
**Source findings:** investigation + Codex adversarial pass (this session); convergence-backlog item 2 in `mountainash/docs/guides/auth-connection-layering.md#convergence-backlog`
**Layering rule:** `mountainash/docs/guides/auth-connection-layering.md` (config emits, auth is data, the L3 applier renders credentials, the L4 connection executes I/O)

## Goal

Bring transport's S3 path in line with the ecosystem auth/connection layering rule, remove the duplicated `ROLE_ARN`, and turn the half-built assume-role path into a real, working capability — while making the dead `supported_auth` metadata load-bearing across all storage providers.

## Background — what is wrong today

Five concrete defects, all verified against the code:

1. **S3 double-render (`driver_key`-then-overwrite).** `S3StorageProfile` declares
   `driver_key` on `REGION→region_name`, `USE_SSL→use_ssl`, `ENDPOINT_URL→endpoint_url`
   (`s3_storage_profile.py:76-120`), but `_s3_boto_kwargs` unconditionally recomputes and
   overwrites all three flavor-aware (`:222-235`, `:297-328`) — forcing `region="auto"` for
   r2 and popping `endpoint_url` for aws/express. The `driver_key`s are dead and actively
   misleading: trusting them would emit a wrong region for r2 and a stray endpoint for aws.
   SFTP composes additively (`sftp_storage_profile.py:164-176`) and HTTP renders only
   in-adapter with no `driver_key`s (`http_storage_profile.py:33-104`) — both already clean.

2. **`ROLE_ARN` duplicated.** It exists on **both** `S3StorageProfile` (`s3_storage_profile.py:153`,
   actually read) and `IAMAuthProfile` (auth-client `iam.py:13-15`, documented as
   "consumed by the storage profile's assume-role shape" but in fact dead — nothing reads it).
   Data's Redshift adapter already reads `IAMAuthProfile.ROLE_ARN`
   (`mountainash-data/.../adapters/redshift.py:10-13`), so the auth-side field is the real one.

3. **Assume-role envelope is mislayered.** `_s3_boto_kwargs` (a config-profile adapter, L1)
   builds the `{base_kwargs, role_arn, session_name}` envelope (`s3_storage_profile.py:252-257`).
   Building the credential-application shape is an L3 applier concern, not config emission.

4. **Assume-role is dead and broken.** No STS `AssumeRole` runs anywhere (full-tree grep: zero
   hits). `S3Connection.connect()` just calls `boto3.client("s3", **kwargs)` (`connections/s3.py:27-33`),
   which would pass the envelope keys (`base_kwargs`/`role_arn`/`session_name`) straight to
   boto3 and fail at runtime. The golden test admits it (`tests/connections/test_emission_golden.py:90-98`).
   **Anyone who sets `ROLE_ARN` today gets a broken connect.**

5. **`supported_auth` is dead metadata.** It is declared on all storage profiles
   (`profile_spec.py:57`) but **never enforced** — the validation is commented out
   (`settings/storage/loader.py:42-51`) and `create_connection` only rejects OAuth via an
   explicit `isinstance` check (`connections/__init__.py:129-138`). As a result:
   - `S3StorageProfile.supported_auth` lists `TOKEN` (`s3_storage_profile.py:181`), but
     `TokenAuthProfile` has no BOTO adapter — it would flow through and produce a broken/empty
     boto auth rather than being rejected (Codex missed-issue #2).
   - `IAMAuthProfile.PROFILE_NAME` (auth-client `iam.py:22`) has no BOTO `driver_key` and is
     not applied anywhere — AWS named-profile selection silently falls back to ambient
     (Codex missed-issue #1).

What is **not** wrong (explicitly validated, do not "fix"):

- Transport calling `auth_profile.emit(family, base=...)` is **consistent with the as-built
  auth-client**: `*AuthProfile` classes are `mountainash_settings.Profile` subclasses with
  `__adapters__`/`driver_key` that self-render to the three SDK families. The "auth never
  emits" doc-rule is aspirational, not implemented. Do **not** remove `emit()` from transport.
- The auth-client `CLAUDE.md` "connections belong here / transport's copy is deprecated" note
  is **OAuth-connection-scoped** (target: `connections/oauth2/connection.py`), not the general
  boto/paramiko/http connection layer. This work stays in transport; it does not move upstream.
  (The OAuth un-weave is separately backlogged:
  `mountainash-central/04.planning/mountainash-auth-client/a.backlog/2026-06-28-oauth-settings-ops-submodule-split.md`.)

## Locked decisions (from brainstorming)

1. **`ROLE_ARN` is auth-only.** Delete `S3StorageProfile.ROLE_ARN`; the role lives solely on
   `IAMAuthProfile.ROLE_ARN`. Ambient assume-role is a **keyless** `IAMAuthProfile(ROLE_ARN=…)`;
   explicit-key assume-role is `IAMAuthProfile(keys + ROLE_ARN)`; `NoAuthProfile` means no role.
2. **STS is implemented for real** via botocore's refreshable assume-role credential provider
   (auto-renews temp creds). Not fail-closed, not removed.
3. **The L3 applier builds the envelope; the L4 connection does the I/O.** `_s3_boto_kwargs`
   returns a flat boto config base; `_emit_kwargs` owns the assume-role envelope.
4. **General `supported_auth` enforcement** is wired into `create_connection` for all providers
   (makes the metadata load-bearing). Requires a one-time audit of every provider's set.
5. **Double-render cleanup**, **flavor guard**, **`PROFILE_NAME` wiring**, and **`TokenAuthProfile`
   removal from S3** all land in this change.

## The design, by layer

### L1 — Config: `S3StorageProfile` + `_s3_boto_kwargs`

- Delete the `ROLE_ARN` ParameterSpec (`s3_storage_profile.py:152-158`).
- Remove `driver_key=` from `REGION`, `USE_SSL`, `ENDPOINT_URL` ParameterSpecs. The adapter is
  the sole source of truth for those three.
- `_s3_boto_kwargs` returns a **flat boto client-config base** only:
  `{service_name, region_name, use_ssl, verify, config, endpoint_url?}`. Remove the
  `if role_arn: return {base_kwargs, role_arn, session_name}` branch entirely (`:252-257`).
- `supported_auth` → `frozenset({IAM, NONE})` (drop `TOKEN`).

### L2 — Auth: `IAMAuthProfile` (auth-client — NO change)

Already carries `ROLE_ARN`, `ACCESS_KEY_ID`, `SECRET_ACCESS_KEY`, `SESSION_TOKEN`,
`PROFILE_NAME`. `emit(BOTO)` renders the three credential keys via existing `driver_key`s.
`ROLE_ARN` and `PROFILE_NAME` correctly have **no** BOTO `driver_key` — they are
Session-construction inputs, not `boto3.client()` kwargs. The applier reads them directly off
the profile. No auth-client edit is required.

### L3 — Applier: `_emit_kwargs` (`connections/__init__.py`)

For the BOTO family (S3):

1. `base = profile.emit(BOTO)` → flat config (no creds).
2. **Flavor guard (`ROLE_ARN` only):** read `profile.FLAVOR`; if `IAMAuthProfile.ROLE_ARN` is set
   and `FLAVOR ∈ {r2, minio, b2}`, raise `ValueError` with a clear message — those flavors are
   not AWS STS, so assume-role is meaningless. **`PROFILE_NAME` is NOT guarded** (Codex #5): a
   boto named profile can legitimately carry static credentials for a custom endpoint
   (r2/minio/b2), so named-profile selection is allowed on every flavor. The applier is the
   correct home for the role guard: it sees both the storage profile (flavor) and the auth
   profile (role).
3. **Branch on whether a Session is required** (i.e. `ROLE_ARN` or `PROFILE_NAME` is present):
   - **Session path (envelope):** render the IAM credential keys via `auth_profile.emit(BOTO)`
     and route them into the envelope's `session` bucket (NOT merged into `client_config`);
     keyless IAM contributes no keys (ambient). Produce the **Session-instruction envelope**:
     ```
     {
       "client_config": {...},     # endpoint_url, use_ssl, verify, config, region_name
       "session": {...},           # aws_access_key_id/secret/session_token (if explicit),
                                    # profile_name (if set), region_name
       "role_arn": str | None,
       "session_name": "mountainash-transport",
     }
     ```
   - **Flat path (no role/profile):** apply IAM creds onto the config base via the existing
     `auth_profile.emit(BOTO, base=…)` merge and return the flat dict — preserving today's
     plain-client behavior exactly.

   Credential keys land in exactly one place per path (the `session` bucket on the Session path,
   the flat base on the flat path) — never merged then split. The exact key names are an
   implementation detail for the plan; the invariant is: **the applier renders the shape and
   performs no I/O.**

### L4 — Connection: `S3Connection`

`connect()` gains a Session-build path (all imports guarded behind the existing
boto3/botocore optional check):

1. **Mutually-exclusive credential sources.** If `profile_name` AND explicit keys are both
   present in the `session` bucket, raise `ValueError` (ambiguous credential source — do not
   silently drop one, per Codex #2). At most one of {profile_name, explicit keys} may be set.
2. **Source session** from the envelope's `session` inputs:
   - `profile_name` set → `boto3.Session(profile_name=…, region_name=…)`
   - explicit keys → `boto3.Session(aws_access_key_id=…, aws_secret_access_key=…,
     aws_session_token=…, region_name=…)`
   - neither → `boto3.Session(region_name=…)` (ambient / instance profile)
3. **Assume-role (if `role_arn`)** — exact botocore wiring (signature verified against
   botocore 1.34.x; the L4 invariant is this is the ONLY correct construction):
   ```python
   import botocore.session
   from botocore.credentials import (
       AssumeRoleCredentialFetcher, DeferredRefreshableCredentials,
   )
   bc = source._session                       # boto3.Session wraps a botocore Session
   # client_creator must honor the same TLS/endpoint settings on the STS leg (Codex #4):
   def _sts_creator(*a, **kw):
       kw.setdefault("verify", client_config.get("verify", True))
       return bc.create_client(*a, **kw)
   fetcher = AssumeRoleCredentialFetcher(
       client_creator=_sts_creator,
       source_credentials=bc.get_credentials(),   # ambient/explicit/profile creds
       role_arn=role_arn,
       extra_args={"RoleSessionName": session_name},
   )
   target = botocore.session.get_session()
   target._credentials = DeferredRefreshableCredentials(
       fetcher.fetch_credentials, "assume-role")
   target.set_config_variable("region", client_config.get("region_name"))
   session = boto3.Session(botocore_session=target)   # auto-refresh on expiry
   ```
   `source_credentials` is REQUIRED and positional-by-keyword here — passing `role_arn` in its
   slot (the original spec error) is wrong. Note STS does NOT take a custom S3 `endpoint_url`;
   only `verify` is propagated to the STS leg.
4. **Build the client:** `session.client("s3", **client_config)` (after popping `service_name`,
   as today). The S3 `endpoint_url`/`config` apply here, never to the STS client.
5. **Ambient-missing is explicit:** if `bc.get_credentials()` returns `None` (no ambient creds
   resolvable for an assume-role request), raise `TransportConnectionError` with a clear message
   rather than letting `fetch_credentials()` fail opaquely later (Codex #2).
6. **No envelope** (flat dict, plain keys / ambient, no role/profile) → existing
   `boto3.client("s3", **kwargs)` path, unchanged.

### Cross-cutting: general `supported_auth` enforcement

- Add `auth_kind(auth_profile) -> CONST_AUTH_PROFILES` deriving the mode from
  `auth_profile.__spec__.provider_type` (e.g. `"iam"`, `"password"`, `"none"`) via
  `CONST_AUTH_PROFILES(value)`. `None` → `CONST_AUTH_PROFILES.NONE`.
- In `create_connection`, **after** the existing OAuth `isinstance` reject (which keeps its
  specific "OAuth is not a transport concern" message) and **before** dispatch: if
  `auth_kind(auth_profile) not in spec.supported_auth`, raise `UnsupportedAuthProfileError`
  naming the provider, the mode, and the supported set.
- This makes the `TokenAuthProfile`-on-S3 rejection fall out of the general mechanism rather
  than an S3 special-case.

**Required audit (plan step) — and the `supported_auth` corrections are IN scope for this
change.** Turning on enforcement makes every provider's set live behavior, so the audit and any
resulting set corrections ship together with the enforcement code (they are not deferred — see
the Out-of-scope note, which excludes only *behavioral* changes beyond these set corrections).
Audit all current sets so nothing that works today starts being rejected. Known sets to review:
azure `{AZURE_AD, TOKEN, PASSWORD, NONE}`, github `{TOKEN, OAUTH2, JWT, NONE}`,
http `{NONE, TOKEN, PASSWORD}`, local `{NONE}`, s3 `{IAM, NONE}` (post-change),
smb `{PASSWORD, KERBEROS}`, ftp `{PASSWORD, NONE}`,
gcs `{SERVICE_ACCOUNT, IAM, OAUTH2, TOKEN, NONE}`, sftp `{PASSWORD, CERTIFICATE, KERBEROS}`.

Two corrections are already identified (Codex #3) and MUST land with the enforcement:

- **SFTP `+= NONE`.** SFTP omits `NONE` but currently accepts `auth_profile=None`
  (SSH-agent / default-key path). Enforcement without this fix breaks a working path. Add
  `NONE` to `sftp_storage_profile.py` `supported_auth` and cover the agent/default-key case
  with a test.
- **GitHub `-= OAUTH2`.** GitHub lists `OAUTH2`, but `create_connection` rejects OAuth profiles
  before enforcement runs (and transport's OAuth connections were deleted) — the entry is a lie.
  Remove `OAUTH2` from `github_storage_profile.py` `supported_auth`.

For any other set that omits `NONE` but is exercised today with `auth_profile=None`, correct the
set (not the enforcement) and record the rationale. **Ordering:** apply all set corrections in the
same commit that flips enforcement on, so the suite never sees a transiently-broken provider.

## Data flow — ambient assume-role (worked example)

`create_connection(S3StorageProfile(FLAVOR="aws", REGION="us-east-1"), IAMAuthProfile(ROLE_ARN="arn:aws:iam::123:role/r"))`

1. family = BOTO.
2. enforcement: `auth_kind` = `IAM` ∈ `{IAM, NONE}` → OK.
3. applier: `base` = flat config; flavor guard (aws + role) → OK; keyless IAM adds no creds;
   `ROLE_ARN` present → envelope with empty `session` creds, `role_arn`, `session_name`.
4. `S3Connection.connect()`: ambient source `boto3.Session(region_name="us-east-1")` →
   `AssumeRoleCredentialFetcher` → `DeferredRefreshableCredentials` → botocore session →
   `boto3.Session(botocore_session=…)` → `.client("s3", **client_config)`.
5. Temp creds auto-refresh on expiry.

## Error handling

| Condition | Behavior |
|---|---|
| `ROLE_ARN` + flavor ∈ {r2,minio,b2} | `ValueError` in applier, clear message (`PROFILE_NAME` is NOT guarded) |
| `PROFILE_NAME` + explicit keys both set | `ValueError` in `S3Connection` (ambiguous credential source) |
| assume-role requested, no ambient creds resolvable | `TransportConnectionError` (clear message), not opaque late failure |
| auth mode ∉ provider `supported_auth` | `UnsupportedAuthProfileError` in `create_connection` |
| OAuth auth profile (any provider) | existing `UnsupportedAuthProfileError` (unchanged) |
| `boto3`/`botocore` not installed | `TransportConnectionError` (existing import-guard pattern) |
| `assume_role` STS failure at connect | wrapped `TransportConnectionError` |

## Testing

- **Rewrite** `TestS3RoleArnLayering` (`test_emission_golden.py:90-166`): assert the new envelope
  shape from the applier; **delete** the "S3Connection does NOT yet consume this envelope" NOTE —
  it is now implemented.
- **New — assume-role execution:** with a mocked/stubbed STS (botocore `Stubber` or `moto`),
  assert `assume_role` is invoked with the right `RoleArn`/`RoleSessionName`, the client is built
  from the refreshable provider, and the credential type is refreshable (not static).
- **New — ambient assume-role:** keyless `IAMAuthProfile(ROLE_ARN=…)` builds a source session
  with no explicit keys.
- **New — `PROFILE_NAME`:** `IAMAuthProfile(PROFILE_NAME=…)` routes to
  `boto3.Session(profile_name=…)`; and `PROFILE_NAME` is allowed on `r2`/`minio`/`b2`
  (NOT flavor-guarded — Codex #5).
- **New — mutual-exclusion:** `PROFILE_NAME` + explicit keys raises `ValueError` (Codex #2).
- **New — ambient-missing:** assume-role with no resolvable ambient creds raises
  `TransportConnectionError` (clear message), not an opaque late failure (Codex #2).
- **New — flavor guard:** `ROLE_ARN` + `FLAVOR ∈ {r2,minio,b2}` raises `ValueError`;
  `ROLE_ARN` + `aws`/`express` proceeds.
- **New — `supported_auth` enforcement:** `TokenAuthProfile` on S3 raises
  `UnsupportedAuthProfileError`; a representative allowed mode passes. Include the two audit
  corrections: SFTP with `auth_profile=None` (agent/default-key) now passes; GitHub no longer
  advertises `OAUTH2`.
- **Behavior-preserving — double-render:** assert `_s3_boto_kwargs` flat-config output is unchanged
  after dropping the three `driver_key`s, across all five flavors. **Compare field-by-field, not
  whole-dict** — two `botocore.config.Config(...)` objects never compare equal by value (Codex #6),
  so assert non-`config` keys by dict equality and assert the `config` object's relevant
  attributes (`s3`, `connect_timeout`, `read_timeout`) individually. No count-based assertions.
- **Unchanged:** HTTP/Local existing tests stay green. SFTP gains the `NONE`-allowed case above;
  its credentialed paths are otherwise unchanged.

## Out of scope (record as follow-ups, do not build here)

- The auth-client OAuth settings/ops submodule split (separately backlogged; independent).
- Any non-S3 provider behavior change beyond the `supported_auth` audit corrections.
- Re-introducing a `TOKEN`/bearer path for S3 (S3 session tokens are `IAMAuthProfile.SESSION_TOKEN`).

## Dependencies

`botocore` (a `boto3` transitive — already present wherever the S3 extra is installed) supplies
`AssumeRoleCredentialFetcher`, `DeferredRefreshableCredentials`, and `botocore.session.get_session`
— all stable public-ish botocore APIs. All new code paths stay behind the existing boto3/botocore
import guard so the core install (no S3 extra) is unaffected.
