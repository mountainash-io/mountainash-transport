# Phase 4 — Storage-profile config emission via `emit()`

**Status:** Draft for review (fresh spec; Phase 4 was explicitly out of scope in the governing unified-emission spec — `mountainash-auth-client/.../2026-06-12-unified-profile-kwargs-emission-design.md` line 505 — so this is net-new design). Transport-only.

**Date:** 2026-06-13

**Related:** completes the unified-emission roadmap (`project_unified_emission_roadmap`). Independent of the connections-dedup spec; sequenced **after** it.

---

## Problem

Storage profiles produce SDK client kwargs through hand-written `to_handler_kwargs()` methods that predate the `emit()`/`__adapters__` machinery landed in Phases 1–3. This is the storage analog of the auth-side duplication Phase 2 eliminated: the same "profile fields → SDK kwargs" mapping, but expressed imperatively per profile and dispatched specially by the factory (`connections/__init__.py:103` calls `to_handler_kwargs()` while auth credentials go through `emit()`).

Storage profiles are already `Profile` subclasses and already use `driver_key` for simple fields (e.g. SFTP 11, FTP 8, GitHub/S3 3 each), but the orchestration and computed values — S3 endpoint derivation, addressing-style resolution, the botocore `Config` object, the `ROLE_ARN` nested envelope — live in `to_handler_kwargs()` outside the declarative machinery. The result is two parallel kwargs-production paths (storage config vs auth credentials) that Phase 4 unifies.

## Goal

Storage profiles produce their SDK config through the unified `emit()` primitive, so the factory assembles a connection's kwargs with a single consistent two-stage pipeline — `storage_profile.emit(family)` for config, then `auth_profile.emit(family, base=...)` for credentials — eliminating the special-cased `to_handler_kwargs()` dispatch. No behavioral change to the kwargs any SDK client receives (golden-verified).

## Non-goals

- Changing SDK behavior or the kwargs' content. This is a mechanism migration; output is held constant.
- Re-deriving S3 endpoint/addressing/config logic. That computed logic is preserved verbatim inside an adapter.
- The connections dedup (separate spec, lands first).

---

## Current state (the 9 storage profiles)

- All are `Profile` subclasses with a `__spec__` (ParameterSpec list).
- Simple fields already carry `driver_key`; computed output is assembled in `to_handler_kwargs()`.
- **SDK-family coverage (corrects Codex F1).** `_PROVIDER_FAMILY_MAP` (Phase 3) only maps the profiles with a *wired connection*: `http→HTTP`, `s3/r2/minio/b2/s3express→BOTO`, `sftp/ssh→PARAMIKO`. The other profile classes — Azure, GCS, FTP, SMB, GitHub — have **no wired connection/backend** (describe-only registry entries) and have **no `TargetFamily` member** (their SDKs aren't httpx/boto3/paramiko). **Phase 4 scope is therefore limited to the connected families: HTTP (http), BOTO (s3 + flavors), PARAMIKO (sftp), and Local** (a degenerate case — see below). Migrating the describe-only profiles is **explicitly out of scope** (it would require new `TargetFamily` members and connections that don't exist yet).
- **Local** uses `NullConnection` and its `to_handler_kwargs()` is mount/path config the factory does not feed to an SDK client. It keeps a plain `emit()` (no family) or is left on `to_handler_kwargs()` — settled at plan time (D5).
- `to_handler_kwargs()` callers (blast radius): `connections/__init__.py:103` (factory), `connections/tunnel.py:91-92` (`_PatchedEndpointProfile`, see F2 below), and the two OAuth connection modules (the dedup spec collapses these — sequenced first). ~4 sites.

## Architecture

### Storage profiles emit via a 2-arg adapter that builds on `driver_key` (decision D1)

Each connected storage profile registers a **2-arg `__adapters__[family]` adapter** keyed by its SDK family. `emit(family)` composes `base + _default_kwargs(family)` (the existing **`driver_key` output**) and hands that merged dict to the adapter, which adds the *computed* parts (S3 endpoint/addressing/`Config`, the nested assume-role envelope). The existing `driver_key`s are **preserved and consumed**, not orphaned:

```python
def _s3_boto_kwargs(profile, kw):           # kw already contains the driver_key fields
    # ... compute endpoint_url, addressing Config, etc., layering onto kw ...
    # ... wrap into {base_kwargs, role_arn, session_name} when ROLE_ARN is set ...
    return result

class S3StorageProfile(Profile):
    __spec__ = S3_SPEC                       # keeps its existing bare driver_keys
    __adapters__ = {TargetFamily.BOTO: _s3_boto_kwargs}
```

**Why 2-arg, not the 1-arg `__adapter__` (resolves Codex F4):** `emit()` feeds `_default_kwargs` (driver_key output) into a 2-arg `__adapters__[target]` adapter but **discards** it for a 1-arg `__adapter__` (settings `profiles/profile.py:295-301`). The 1-arg form would silently orphan every storage profile's existing `driver_key`s. The 2-arg form composes on them — which is also the rule-4-correct pattern (bare `driver_key` behind a 1-arg owns-pipeline adapter is the leak rule-4 forbids; behind a 2-arg compose adapter it is consumed). A profile whose config is *purely* field-renames may instead drop the adapter and rely on `driver_key` alone.

> **rule-4 note:** Phase 2's rule-4 invariant ("adapter-bearing profile may not declare bare driver_key") is **auth-client-local** (runs over `AUTH_REGISTRY`), so it does not touch storage profiles. It was authored for the 1-arg owns-pipeline case. Phase 4 must NOT import/extend that invariant onto the storage registry, since the 2-arg-composes-on-driver_key pattern is intentional and safe. The plan confirms transport's storage registry has no equivalent invariant that would false-positive.

### Storage emit is TARGETED by family (resolves Codex F3)

Because storage profiles now carry `__adapters__[family]`, they are **target-scoped**: `storage_profile.emit(family)` is required and `emit()` with no target fails closed (Phase 1 semantics). This removes the goal-vs-architecture contradiction — the earlier draft's untargeted `emit()` was wrong. The factory already has `family` from `_family_for_provider`, and now passes it to *both* stages:

```python
def _emit_kwargs(profile, auth_profile, family):
    if family is None:                          # Local / unmapped → no SDK emission
        return profile.to_handler_kwargs()      # (or profile.emit() if Local gains a family — D5)
    base = profile.emit(family)                 # storage config (targeted, builds on driver_key)
    if auth_profile is None or isinstance(auth_profile, NoAuthProfile):
        return base
    if "base_kwargs" in base:                   # S3 assume-role envelope — unchanged from Phase 3
        return {**base, "base_kwargs": auth_profile.emit(family, base=base["base_kwargs"])}
    return auth_profile.emit(family, base=base)
```

Storage `emit(family)` produces the config; auth `emit(family, base=...)` layers credentials — **both targeted on the same `TargetFamily`**. The S3 nested `base_kwargs` handling from Phase 3 is preserved exactly.

### `_PatchedEndpointProfile` must override `emit()` (resolves Codex F2)

`_PatchedEndpointProfile` (`connections/tunnel.py:81`) wraps a target profile to inject the tunnel's `127.0.0.1:<local_port>`, overriding **only** `to_handler_kwargs()` and delegating everything else via `__getattr__`. If the factory calls `profile.emit(family)`, `__getattr__` would delegate `emit` to the **inner** profile and return its **unpatched** host/port — silently routing the tunnel to the real remote. Phase 4 therefore **adds an `emit()` override** to `_PatchedEndpointProfile` that applies the same host/port patch to the inner profile's emit output:

```python
def emit(self, *args, **kwargs):
    return self._patch_endpoint(self._inner.emit(*args, **kwargs))   # same patch as to_handler_kwargs
```

(The exact patch helper mirrors the existing `to_handler_kwargs` override.) This is a required, not optional, part of the factory migration.

### `to_handler_kwargs()` disposition

`to_handler_kwargs()` is referenced by `StorageProfileProtocol` and a few external callers. Options (decision D2):
- **(a) Thin shim:** keep `def to_handler_kwargs(self): return self.emit()` on the protocol/base for one release, repoint internal callers to `emit()`, deprecate the method.
- **(b) Remove:** delete `to_handler_kwargs()`, update the ~4 callers + `StorageProfileProtocol` + any downstream consumer to `emit()`.

*Proposed: (a) — shim first (zero-risk for downstream consumers), with internal callers moved to `emit()`; schedule removal in a later major.*

## Data flow (after)

```
create_connection(storage_profile, auth_profile)
  → _emit_kwargs:
       base   = storage_profile.emit(family)              # storage config (targeted; builds on driver_key)
       merged = auth_profile.emit(family, base=base)       # + credentials (same TargetFamily)
  → leaf_cls(merged)
```

One emission machinery, two stages on the same family, no special-cased `to_handler_kwargs()` branch.

## Error handling

- Storage `emit(family)` (via the 2-arg adapter) raises exactly what `to_handler_kwargs()` raises today (e.g. profile-validation `ValueError`s) — same computed body, moved into the adapter.
- `emit()` with no target on a now-target-scoped storage profile raises (Phase 1 fail-closed) — the factory always supplies `family` for connected profiles, so this only bites a mis-call, which is the desired loud failure.
- No new failure modes for valid paths: output-preserving mechanism swap.

## Testing

- **Golden equivalence (central safety net):** for each connected profile (http, s3+flavors, sftp), capture `to_handler_kwargs()` output across representative field combinations **before** the change; assert `emit(family)` produces byte-identical dicts after. Include S3's flavor matrix (aws/r2/minio/b2/express), the `ROLE_ARN` nested envelope, the botocore `Config` object's fields, and HTTP's `httpx.Timeout`. No count-based assertions — exact key/value shape.
- **driver_key preservation:** assert the existing `driver_key` fields still appear in `emit(family)` output (proves the 2-arg adapter composes on them rather than orphaning them).
- **Tunnel:** a test that a tunnelled connection's inner kwargs carry the patched `127.0.0.1:<local_port>` (proves the `_PatchedEndpointProfile.emit()` override works — guards the Codex-F2 regression).
- Factory tests: `_emit_kwargs` still layers auth credentials correctly onto the storage `emit(family)` base (reuse Phase 3's `test_emission_golden.py` patterns).
- Back-compat: if D2(a), a test that the `to_handler_kwargs()` shim equals `emit(family)`.

## Settled decisions

- **D1 — 2-arg `__adapters__[family]` building on `driver_key`** (user decision). Preserves existing driver_keys; computed parts in the adapter. Not the 1-arg `__adapter__` (would orphan driver_keys). See Architecture.
- **D3 — storage emit is targeted by family** (resolves the earlier untargeted/targeted contradiction).
- **Scope — connected families only** (HTTP/BOTO/PARAMIKO + Local); describe-only profiles (Azure/GCS/FTP/SMB/GitHub) deferred (no connection, no TargetFamily).

## Open questions / decisions for review

- **D2 — `to_handler_kwargs()` shim vs removal.** (a) keep `to_handler_kwargs(self): return self.emit(self._family())` as a deprecated shim for downstream consumers, internal callers move to `emit`; (b) remove it and update `StorageProfileProtocol` + all callers + downstream. *Proposed: (a) shim, deprecate.* **Watch the shim's family:** the shim must know its own `family` to call `emit(family)` — add a small `_family` hook per profile (or look it up from the provider map). Confirm the shim is not circular (the adapter no longer calls `to_handler_kwargs`).
- **D4 — `StorageProfileProtocol`.** It requires `to_handler_kwargs()` + `get_connection_url()`. `emit` is already inherited from `ProfileProtocol` via `Profile`. Decide whether the protocol advertises `emit` directly and whether `to_handler_kwargs` stays under D2(a).
- **D5 — Local profile.** `LocalStorageProfile` has no SDK family (NullConnection). Keep it on plain `to_handler_kwargs()` (factory already special-cases `family is None`), or give it a degenerate untargeted `emit()`? *Proposed: leave on `to_handler_kwargs()`; the factory's `family is None` branch already handles it.*

## Risks

- **S3 is the highest-risk profile** (flavor dispatch + computed endpoint/addressing + `Config` object + nested envelope). The golden matrix must cover all flavors and the assume-role shape; the adapter body is the existing computed code moved with minimal change.
- **Downstream consumers of `to_handler_kwargs()`** (outside transport, e.g. `mountainash-data`) — the D2(a) shim protects them; removal would be a coordinated breaking change.
- **Interaction with the Phase-3 `base_kwargs` layering** must be preserved exactly — covered by reusing the Phase-3 S3 envelope test.
- **Tunnel regression (Codex F2)** — the `_PatchedEndpointProfile.emit()` override is mandatory and directly tested.
