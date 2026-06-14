# mountainash-transport — Deferred Scope & Backlog

**Last updated:** 2026-06-13 (after the unified-emission roadmap + connections-dedup landed)

This doc catalogues work that was **deliberately left out of scope** or **deferred**
during the unified-emission roadmap (Phases 1–4) and the connections-dedup, plus
pre-existing gaps surfaced along the way. Each item states **what's required**, the
**pattern to follow**, and **references** to the code/specs that anchor it.

Status legend: 🔴 not started · 🟡 partial · 🧊 deferred-by-design (needs a trigger) · 🧹 hygiene

---

## A. Storage-emission completion

### A1. 🔴 Migrate the describe-only storage profiles (Azure, GCS, FTP, SMB, GitHub)

Phase 4 migrated only the **connected** profiles (S3/BOTO, HTTP, SFTP/PARAMIKO). The
other five profiles are **describe-only**: they have a `__spec__` and a
`to_handler_kwargs()`, but **no wired connection, no backend, and no `TargetFamily`
member** (their SDKs aren't httpx/boto3/paramiko).

- **Current state:** `src/mountainash_transport/settings/storage/profiles/{azure,gcs,ftp,smb,github}_storage_profile.py` exist with `to_handler_kwargs()`. There are **no** `storage/backends/{azure,gcs,ftp,smb,github}/` dirs (only `http`, `local`, `s3`, `sftp` are implemented). `TargetFamily` has only `HTTP/BOTO/PARAMIKO`.
- **What's required (per profile family):**
  1. Add a `TargetFamily` member in **auth-client** (`src/mountainash_auth_client/targets.py`) for the SDK family (e.g. `AZURE`, `GCS`, `FTP`, `SMB`, `GITHUB`) — and the corresponding auth-side `__adapters__`/`driver_key`s on any auth profiles that target it.
  2. Build a **connection class** (`connections/<family>.py`) that constructs the SDK client from `connect_kwargs` + the auth strategy, conforming to `ConnectionProtocol`.
  3. Build a **backend** (`storage/backends/<family>/`) implementing the relevant granular protocols (`prtcl_*`).
  4. Add a **2-arg `__adapters__[family]` adapter** to the profile (the Phase-4 pattern) and convert `to_handler_kwargs()` to the shim.
  5. Register the provider in `connections/__init__.py` `_PROVIDER_FAMILY_MAP` **and** `_PROVIDER_CONNECTION_MAP`.
- **Pattern to follow:** the S3/HTTP/SFTP work — profile adapter `docs/superpowers/plans/2026-06-13-storage-emission-phase4.md`; connection class `connections/s3.py`; backend `storage/backends/s3/`.
- **Why deferred:** out of Phase 4 scope by design (spec §"SDK-family coverage" / "Scope"). Requires net-new `TargetFamily` members + connections + backends that don't exist yet — a much larger effort than the mechanism swap Phase 4 performed.
- **Refs:** `docs/superpowers/specs/2026-06-13-storage-emission-phase4-design.md` (Scope), `CLAUDE.md` (Storage System Support table).

### A2. 🧊 Remove the `to_handler_kwargs()` shim (Phase 4 D2a)

The three migrated profiles keep `to_handler_kwargs()` as a deprecated shim
(`return self.emit(self._sdk_family())`) so downstream consumers (e.g. `mountainash-data`)
keep working unchanged.

- **What's required:** once all downstream callers migrate to `emit(family)`: delete `to_handler_kwargs()` + `_sdk_family()` from the profiles, drop it from `StorageProfileProtocol`, and update the factory `family is None` fallback (Local still needs *a* config method — see A3).
- **Trigger:** a coordinated major version + confirmation no external caller imports `to_handler_kwargs`.
- **Refs:** Phase-4 spec D2/D4; `settings/profile_protocol.py`.

### A3. ⛔ ~~Migrate the OAuth connections off the `to_handler_kwargs` shim~~

> ⛔ **Obsoleted (2026-06-14):** the transport OAuth connections were deleted in PR 2 of the ProviderProfile cycle — there is nothing left to migrate. See `docs/superpowers/plans/2026-06-14-oauth-connection-deletion-transport.md`.

`connections/oauth2/connection.py` and `oauth1/connection.py` build the storage base via
`self._profile.to_handler_kwargs()`. This routes through `emit(HTTP)` underneath (via the
shim) so there's no behavioral difference — but it's the last internal caller still on the
shim.

- **What's required:** replace `self._profile.to_handler_kwargs()` with `self._profile.emit(TargetFamily.HTTP)` in both connections (they always bind onto an HTTP-family endpoint).
- **Why deferred:** trivial, zero-behavior cleanup; intentionally excluded from Phase 4 to keep that PR's blast radius on the storage profiles + factory. Blocks A2 (shim removal) until done.
- **Refs:** Phase-4 spec D2 "Scope note".

---

## B. Connection-layer gaps (pre-existing)

### B1. 🔴 S3 assume-role envelope is produced but never consumed (STS AssumeRole)

`S3StorageProfile` emits a nested `{base_kwargs, role_arn, session_name}` envelope when
`ROLE_ARN` is set, and the factory layers IAM credentials into `base_kwargs`. But
**`S3Connection` does not perform STS AssumeRole** — it ignores `role_arn`/`session_name`
at connect time.

- **Current state:** `connections/s3.py` has no `role_arn`/`AssumeRole`/`sts` handling (verified). The Phase-3 golden test `tests/connections/test_emission_golden.py::TestS3RoleArnLayering` explicitly notes "S3Connection does NOT yet consume this envelope — pre-existing unimplemented gap."
- **What's required:** in `S3Connection.connect()`, when the kwargs carry a `role_arn`, call `boto3.client("sts").assume_role(RoleArn=..., RoleSessionName=session_name)`, extract the temporary `aws_access_key_id`/`aws_secret_access_key`/`aws_session_token`, and build the s3 client from `base_kwargs` + those temp creds. Handle refresh/expiry if long-lived.
- **Pattern to follow:** lazy boto3 import as elsewhere in `connections/s3.py`; the envelope shape is already defined by the S3 adapter.
- **Refs:** `connections/s3.py`, `test_emission_golden.py::TestS3RoleArnLayering`.

### B2. 🧊 Tunnel does not patch the nested S3 `base_kwargs` endpoint

`_PatchedEndpointProfile._patch_endpoint` (`connections/tunnel.py`) patches `hostname`/`port`
and top-level `endpoint_url`/`base_url` only. For the S3 assume-role envelope, `endpoint_url`
lives **inside** `base_kwargs`, so a tunnelled S3-with-role connection would not be redirected
through the tunnel.

- **What's required:** extend `_patch_endpoint` to also patch `endpoint_url` inside a nested `base_kwargs` dict when present.
- **Why deferred:** pre-existing behavior (the old `to_handler_kwargs` patch had the same top-level-only limitation); Phase 4 preserved it deliberately. Only matters once B1 (assume-role at connect) is real.
- **Refs:** Phase-4 spec "Risks"; `connections/tunnel.py`.

### B3. ⛔ ~~Thread a real callback-server factory through transport (dedup D1)~~

> ⛔ **Obsoleted (2026-06-14):** transport no longer owns OAuth connections — callback-server threading is auth-client's concern (`resolve_access_token(..., callback_server=...)`). See the PR-2 deletion plan.

Transport's collapsed OAuth connections call the auth-client resolver with
`callback_server=None`. The resolver accepts a `CallbackServerFactory` and forwards it to
`authorize()`, but transport never threads a real one — so `auto_authorize=True` falls back
to auth-client's default factory.

- **What's required:** add a `callback_server: CallbackServerFactory | None` parameter to `create_connection` (and the OAuth connection `__init__`s), and pass it into `resolve_access_token`/`resolve_token_pair`.
- **Pattern to follow:** auth-client `OAuthFlow.resolve_access_token(..., callback_server=...)` already supports it; `LocalCallbackServer`/`ManualCallbackServer` are the factories.
- **Refs:** connections-dedup spec D1; auth-client `connections/oauth2/flow.py::authorize`.

### B4. 🧹 Harden two preserved-not-hardened OAuth lifecycle quirks (auth-client)

Lifted verbatim into auth-client's resolvers during the dedup (Part A); inherited, not
regressions:
- OAuth2 refresh re-reads `tokens` inside `backend.transaction(key)` then indexes `tokens["refresh_token"]` — a concurrent delete between reads raises `KeyError`.
- OAuth1 cache check is `if tokens and tokens.get("oauth_token")` but the build indexes `tokens["oauth_token_secret"]` — a partially-persisted entry raises `KeyError`.
- **What's required:** defensive guards in `OAuthFlow.resolve_access_token` / `OAuth1Flow.resolve_token_pair` (auth-client repo). Low priority.
- **Refs:** auth-client `docs/superpowers/plans/2026-06-13-connections-dedup-authclient.md` ("Preserved-not-hardened").

---

## C. Architecture wiring ("theatre")

### C1. 🟡 End-to-end wiring of profile → connection → backend → operation

Several layers are designed but not fully wired through production paths.

- **Symptoms:** `get_connection_url()` is implemented by all 9 profiles but called by **zero** production paths; only a minority of read/write paths actually stream; stream-transform facade integration is partial.
- **What's required:** audit each operation path to confirm it routes through the full stack rather than shortcutting; wire streaming through the remaining backends; complete facade transform integration. **Do not delete** the "unused" architecture — wire it in.
- **Refs:** memory `project_theatrical_wiring`; `storage/facade/`.

### C2. 🔴 `load_storage()` config-driven materialisation (loader.py)

`settings/storage/loader.py` is **entirely commented out** — `load_storage()` is unimplemented.
This is the resolver that the auth-separation design and `mountainash-files` depend on (string
`auth_profile` → resolved `(profile, auth)`).

- **What's required:** implement `load_storage(provider, *, config_file=, secrets_provider=, auth_mode=) -> (StorageProfile, AuthProfile)` per the auth-separation spec; resolve a string provider/auth into materialised profile + auth instances via `STORAGE_REGISTRY` + auth-client's `AUTH_REGISTRY`.
- **Downstream blocked:** `mountainash-files` `_make_facade()` (`_operations.py`) has a TODO that calls `load_storage()` to pass `profile=`/`auth=` separately into `StorageFacade.from_path`.
- **Refs:** `docs/superpowers/specs/2026-06-07-auth-separation-design.md`; memory `project_utils_files_auth_profile_resolution`; `settings/storage/loader.py`.

---

## D. Type-checking & hygiene

### D1. 🧹 mypy `import-untyped` noise from auth-client / settings

mypy reports ~66 `import-untyped` errors because `mountainash-auth-client` and
`mountainash-settings` ship **no `py.typed` marker**. These swamp the ~20 genuine
(pre-existing) substantive errors.

- **What's required (pick one):** add a `[[tool.mypy.overrides]] module = ["mountainash_auth_client.*", "mountainash_settings.*"] ignore_missing_imports = true` in `pyproject.toml`, **or** (better, cross-repo) ship a `py.typed` marker from those packages.
- **Refs:** `pyproject.toml` (mypy env).

### D2. 🧹 ~20 pre-existing substantive mypy errors

Independent of the roadmap; worth a dedicated cleanup pass. Examples: `connections/__init__.py:44` `_FindMemberMixin` return-value; `create_connection` passing `ProfileProtocol` where `StorageProfileProtocol` is expected (OAuth connection construction); `connections/tunnel.py` `get_transport` union-attr; `storage/path_helpers/s3.py` union-attrs; `_core/http` test arg-types.
- **What's required:** narrow types / add guards per error. None block CI (the repo runs with these present).

---

## E. Stubs & future families

### E1. 🧊 Messaging profiles (`settings/messaging/`)

Stub package (only `__init__.py`). Reserved for a future messaging profile family that
would reuse the same `Profile` + `emit()` + registry machinery as storage.
- **Pattern to follow:** the storage profile family (`settings/storage/`) is the template — `Registry`, `__adapters__`, per-provider profiles.

### E2. 🧊 Shared httpx client factory (`_core/http.py`)

Stub for a future shared httpx client factory (currently each consumer builds its own
`httpx.Client`). Consolidate when there's a second consumer.

---

## F. Cross-repo & path_helpers follow-ups

These predate the emission roadmap (from the 2026-04 path_helpers refactor); included for
completeness. **Verify current status before acting** — some may have landed.

- **F1. HTTP/HTTPS in the canonical dispatcher** — populate the `http`/`https` `SCHEMES`
  entries with the real provider and delete the urllib bridge in `read_bytes.py`. (Note: an
  HTTP **backend** now exists at `storage/backends/http/` — verify whether the `read_bytes`
  urllib bridge is still present.) Ref: canonical-dispatcher spec §8.
- **F2. Facade-level `read(..., infer=True)` / `read_stream(..., infer=True)`** — today
  `read_bytes(infer=True)` is the only suffix-inference entry point.
- **F3. Additional transform suffixes** (`.bz2`, `.zst`, `.xz`, `.lz4`) — add when their
  `StreamTransform` classes exist. Write-side inference is intentionally **out of scope**
  (footgun). Ref: stream-transforms / suffix-inference specs.
- **F4. (mountainash repo, not here)** dedupe the copy-pasted `_facade_read_bytes` in
  `mountainash/relations/dag/readers/{parquet,csv,json}.py` → `from mountainash_utils_files import read_bytes`.
- **Refs:** memory `project_path_helpers_roadmap`; `docs/path_helpers_full_scope.md`.

---

## Quick triage

| Priority | Items |
|---|---|
| **High value, scoped** | ~~A3 (OAuth→emit cleanup)~~ ⛔ obsolete, ~~B3 (callback threading)~~ ⛔ obsolete, D1 (mypy override) |
| **Larger efforts** | A1 (describe-only families), B1 (S3 assume-role), C1 (wiring), C2 (load_storage) |
| **Deferred-by-design (need a trigger)** | A2 (shim removal), B2 (nested tunnel patch), E1/E2 (stubs) |
| **Hygiene** | B4, D2, F-series |
