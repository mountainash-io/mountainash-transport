# Auth Separation: Profile and Auth as Independent Settings Instances

## Problem

The Phase 4 settings migration introduced auth as a nested field on storage
Profile subclasses (`S3Settings.auth: IAMAuth | TokenAuth | NoAuth`), with
`auth_modes` declared on `StorageDescriptor`. The adapters then access auth
via `getattr(profile, "auth", None)` typed as `t.Any` with string-based
type discrimination (`type(auth).__name__ == "IAMAuth"`).

Additionally, all 9 Settings classes inherit from `StorageAuthBase`, a legacy
mixin that puts auth fields (`USERNAME`, `PASSWORD`, `ACCESS_KEY_ID`,
`SECRET_KEY`, `TOKEN`) directly on the profile — duplicating what auth-client
Profile subclasses now provide.

This design has four problems:

1. **Nested auth loses settings services.** Pydantic constructs nested models
   via its validator pipeline, bypassing `MountainAshBaseSettings.__init__`.
   Nested auth instances have no config loading, secret resolution, caching,
   or persist — defeating the purpose of migrating auth modes to Profile
   subclasses in mountainash-auth-client.

2. **`t.Any` throughout.** The facade, registry, backends, and all 9 adapters
   use `t.Any` for auth parameters. No type safety, no IDE autocompletion,
   no static analysis protection against field name typos.

3. **String-based type discrimination.** Adapters check
   `type(auth).__name__ == "IAMAuth"` instead of `isinstance(auth, IAMAuth)`.
   Fragile, no exhaustiveness checking, breaks silently on rename.

4. **`StorageAuthBase` duplicates auth-client fields.** The mixin defines
   `USERNAME`, `PASSWORD`, `ACCESS_KEY_ID`, `SECRET_KEY`, `TOKEN` directly
   on each Settings class, overlapping with auth-client's `PasswordAuth`,
   `IAMAuth`, `TokenAuth` etc. With auth separated to its own instance, these
   fields on the profile are redundant and create ambiguity about which is the
   source of truth.

## Upstream Context

This spec depends on upstream changes in mountainash-auth-client and
mountainash-settings (documented in the auth-client repo). These changes have
already landed:

- **Auth modes are Profile subclasses** with ParameterSpec-driven fields and
  UPPERCASE field names (e.g. `auth.ACCESS_KEY_ID`, not `auth.access_key_id`).
- **`auth_modes` removed from ProfileSpec** — already shipped in
  mountainash-settings. Auth is a domain concern, not a generic profile
  concern.
- **`AuthSpec` base class removed** — auth modes inherit from
  `mountainash_settings.Profile` directly.
- **`CONST_AUTH_MODE` StrEnum** exported from mountainash-auth-client with
  members matching AUTH_REGISTRY keys.
- **`AuthMode` type alias** exported from mountainash-auth-client — a union of
  all 13 concrete auth Profile subclasses.

See:
- `mountainash-auth-client/docs/superpowers/specs/2026-06-07-auth-settings-alignment-design.md`
- `mountainash-auth-client/docs/superpowers/specs/2026-06-07-settings-parameters-pattern-discussion.md`
- `mountainash-auth-client/docs/superpowers/specs/2026-06-07-auth-integration-wiring-design.md`

## Core Principle: Separate Profile and Auth

**Profile** (`StorageProfile`) describes *how to connect to storage* — region,
bucket, endpoint URL, timeouts, addressing style. It is a
`mountainash_settings.Profile` subclass with ParameterSpec-driven fields.

**Auth** (an auth mode Profile subclass from mountainash-auth-client) describes
*who you are* — credentials, tokens, keys. It is a separate top-level settings
instance, materialised independently via its own `SettingsParameters`.

Both can load from the same config file (each picks its own fields via
`extra="ignore"`) or from separate files. Neither is nested inside the other.

This follows the **materialise early, flow the instance** pattern documented
in the settings-parameters discussion paper: the consumer's entry point creates
`SettingsParameters` and calls `get_settings()`, then passes materialised
instances to library code. The facade and backends never see
`SettingsParameters`.

## Design

### Remove StorageAuthBase

`StorageAuthBase` (`settings/base.py`) is deleted. Its responsibilities are
replaced by:

| StorageAuthBase field | Replacement |
|----------------------|-------------|
| `USERNAME`, `PASSWORD`, `ACCESS_KEY_ID`, `SECRET_KEY`, `TOKEN` | Auth-client Profile subclasses (`PasswordAuth`, `IAMAuth`, `TokenAuth`) — separate instance |
| `AUTH_METHOD` | `CONST_AUTH_MODE` from auth-client + `default_auth` on `StorageDescriptor` |
| `PROVIDER_TYPE` | Already on `StorageDescriptor.provider_type` |
| `ENDPOINT`, `PORT`, `TIMEOUT` | Remain as ParameterSpec fields on each provider's spec (already declared there) |
| `ROOT_PATH`, `CREATE_PATH` | Remain as ParameterSpec fields on relevant provider specs |
| `ACCESS_TYPE`, `REQUIRED_PERMISSIONS` | Not used by any adapter — remove |
| `COMPRESSION_TYPE`, `ENCRYPTION_TYPE` | Not used by any adapter — remove |
| `get_connection_args()` | Replaced by `to_handler_kwargs(auth=)` |
| `get_connection_url()` | Stays as a method on individual Settings classes that override it (e.g. `S3Settings`) |
| `format_connection_url()` | Not used — remove |
| `post_init()` bridge | No longer needed — `StorageProfile` inherits `Profile.post_init()` directly |
| `_init_provider_specific()` | Legacy hook — no provider overrides it. Remove |

All 9 Settings classes change from `class S3Settings(StorageProfile, StorageAuthBase)`
to `class S3Settings(StorageProfile)`.

Connection fields that are genuinely provider-specific (`ENDPOINT`, `PORT`,
`TIMEOUT`, `ROOT_PATH`) are already declared as ParameterSpec entries on
each provider's spec. `StorageAuthBase` was adding duplicate declarations
that the ParameterSpec fields shadow.

### StorageDescriptor Changes

`auth_modes` is already gone from `ProfileSpec` upstream. Add `default_auth`
and `supported_auth` as domain-specific metadata:

```python
from mountainash_auth_client import CONST_AUTH_MODE

@dataclass(frozen=True, kw_only=True)
class StorageDescriptor(ProfileSpec):
    sdk_package: str | None = None
    handler_module: str = ""
    handler_class: str = ""
    supports_streaming: bool = True
    supports_multipart: bool = True
    read_only: bool = False
    default_auth: CONST_AUTH_MODE = CONST_AUTH_MODE.NONE
    supported_auth: frozenset[CONST_AUTH_MODE] = frozenset({CONST_AUTH_MODE.NONE})
```

`default_auth` is what `load_storage()` uses when the caller doesn't specify
an auth mode. `supported_auth` is the full set of valid auth modes for
validation — `load_storage()` raises `ValueError` if the requested auth mode
is not in `supported_auth`.

### Settings Classes Changes

Each provider's spec drops `auth_modes`, adds `default_auth` and
`supported_auth`. Auth type imports move from provider files to adapter files.

Before:
```python
from mountainash_auth_client import IAMAuth, NoAuth, TokenAuth

S3_SPEC = StorageDescriptor(
    name="s3",
    provider_type=CONST_STORAGE_PROVIDER_TYPE.S3,
    auth_modes=[IAMAuth, TokenAuth, NoAuth],
    parameters=[...],
)

class S3Settings(StorageProfile, StorageAuthBase):
    __spec__ = S3_SPEC
```

After:
```python
from mountainash_auth_client import CONST_AUTH_MODE

S3_SPEC = StorageDescriptor(
    name="s3",
    provider_type=CONST_STORAGE_PROVIDER_TYPE.S3,
    default_auth=CONST_AUTH_MODE.IAM,
    supported_auth=frozenset({
        CONST_AUTH_MODE.IAM,
        CONST_AUTH_MODE.TOKEN,
        CONST_AUTH_MODE.NONE,
    }),
    parameters=[...],
)

class S3Settings(StorageProfile):
    __spec__ = S3_SPEC
```

All 9 provider settings files follow this pattern:

| Provider | `default_auth` | `supported_auth` |
|----------|---------------|-----------------|
| S3 | `IAM` | `{IAM, TOKEN, NONE}` |
| GCS | `SERVICE_ACCOUNT` | `{SERVICE_ACCOUNT, IAM, OAUTH2, TOKEN, NONE}` |
| Azure | `AZURE_AD` | `{AZURE_AD, TOKEN, PASSWORD, NONE}` |
| SSH | `PASSWORD` | `{PASSWORD, CERTIFICATE, KERBEROS}` |
| FTP | `PASSWORD` | `{PASSWORD, NONE}` |
| SMB | `PASSWORD` | `{PASSWORD, KERBEROS}` |
| Local | `NONE` | `{NONE}` |
| GitHub | `TOKEN` | `{TOKEN, OAUTH2, JWT, NONE}` |
| HTTP | `NONE` | `{NONE, TOKEN, PASSWORD}` |

### StorageProfile Changes

`to_handler_kwargs()` gains an `auth` parameter and forwards it to the
adapter. This changes the `__adapter__` contract from
`Callable[[Profile], dict]` to `Callable[[Profile, AuthMode | None], dict]`.
This is a storage-domain contract (defined on `StorageProfile`, not the
generic `Profile` base), so no upstream change is needed.

Also fixes pre-existing bug: duplicate `self._default_kwargs()` call on
line 41 of profile.py.

```python
from mountainash_auth_client import AuthMode

class StorageProfile(Profile):
    def to_handler_kwargs(self, auth: AuthMode | None = None) -> dict[str, t.Any]:
        adapter = lookup_class_var(type(self), "__adapter__")
        if adapter is not None:
            return adapter(self, auth)
        return self._default_kwargs()
```

### Adapter Changes

Every adapter's `build_handler_kwargs` changes:

1. **Signature** — add `auth: AuthMode | None = None` parameter.
2. **Type checking** — `isinstance()` replaces `type().__name__` string
   matching.
3. **Field names** — lowercase to UPPERCASE (`auth.access_key_id` →
   `auth.ACCESS_KEY_ID`).

Example (S3 adapter):
```python
from mountainash_auth_client import AuthMode, IAMAuth, TokenAuth

def build_handler_kwargs(
    profile: "StorageProfile",
    auth: AuthMode | None = None,
) -> dict[str, t.Any]:
    # ... profile-driven kwargs unchanged ...

    if isinstance(auth, IAMAuth):
        if auth.ACCESS_KEY_ID:
            base["aws_access_key_id"] = auth.ACCESS_KEY_ID
        if auth.SECRET_ACCESS_KEY:
            base["aws_secret_access_key"] = _unwrap_secret(auth.SECRET_ACCESS_KEY)
        if auth.SESSION_TOKEN:
            base["aws_session_token"] = _unwrap_secret(auth.SESSION_TOKEN)
    elif isinstance(auth, TokenAuth):
        if auth.TOKEN:
            base["aws_session_token"] = _unwrap_secret(auth.TOKEN)

    return base
```

The `__adapter__` callable on each Settings class updates to forward both
params:

```python
def _adapter(profile: "S3Settings", auth: AuthMode | None = None) -> dict[str, t.Any]:
    from ..adapters.s3 import build_handler_kwargs
    return build_handler_kwargs(profile, auth)
```

All 9 adapters follow this pattern.

### Facade Changes

`StorageFacade` renames `auth_params` to `profile` and types both parameters.
This is a breaking change — no deprecation shim.

```python
from mountainash_auth_client import AuthMode

class StorageFacade:
    def __init__(
        self,
        provider_type: CONST_STORAGE_PROVIDER_TYPE,
        profile: StorageProfile | None = None,
        *,
        auth: AuthMode | None = None,
    ) -> None:
        self._backend = get_storage_backend(provider_type, profile, auth=auth)

    @classmethod
    def from_path(
        cls,
        path: str,
        profile: StorageProfile | None = None,
        *,
        auth: AuthMode | None = None,
    ) -> StorageFacade:
        provider = detect_provider_from_path(path)
        return cls(provider_type=provider, profile=profile, auth=auth)
```

The `hasattr(self._backend, "auth")` guard (current lines 79-83) is removed.
All backends accept `auth` uniformly — backends that don't need auth simply
ignore it.

### Registry Changes

`get_storage_backend()` gets typed parameters. The `_accepts_auth()`
introspection is removed — all backends accept `auth` in their `__init__`
signature. Backends that don't use auth simply ignore the parameter.

```python
from mountainash_auth_client import AuthMode

def get_storage_backend(
    provider_type: CONST_STORAGE_PROVIDER_TYPE,
    profile: StorageProfile | None,
    *,
    auth: AuthMode | None = None,
) -> t.Any:
    cls = _backend_registry.get(provider_type)
    if cls is None:
        raise ValueError(f"No backend registered for {provider_type!r}")
    return cls(profile, auth=auth)
```

### Backend Changes

Each backend's `__init__` gets typed parameters. Auth flows through
`profile.to_handler_kwargs(auth=auth)` — the adapter handles auth-to-SDK
mapping.

```python
class S3StorageBackend:
    def __init__(
        self,
        profile: StorageProfile | None,
        *,
        auth: AuthMode | None = None,
    ) -> None:
        kwargs = profile.to_handler_kwargs(auth=auth) if profile else {}
        # ... construct boto3 client from kwargs ...
```

All 3 existing backends (S3, local, HTTP) follow this pattern.

**HTTP backend dual-auth path:** The HTTP backend currently has its own auth
handling in `_get_client()` that reads `self.auth` and does string-based type
checking to build Authorization headers. This is removed — all auth handling
moves to the HTTP adapter's `build_handler_kwargs(profile, auth)`, which
returns httpx kwargs including the Authorization header. The backend's
`_get_client()` just uses the kwargs dict as-is.

### Public API Convenience Functions

`read_bytes()`, `storage()`, and `copy_between()` update their signatures:

```python
# __init__.py
def storage(
    provider_type: CONST_STORAGE_PROVIDER_TYPE = CONST_STORAGE_PROVIDER_TYPE.LOCAL,
    profile: StorageProfile | None = None,
    *,
    auth: AuthMode | None = None,
) -> StorageFacade:
    return StorageFacade(provider_type, profile, auth=auth)
```

```python
# storage_facade/read_bytes.py
def read_bytes(
    path: str,
    profile: StorageProfile | None = None,
    *,
    auth: AuthMode | None = None,
    ...
) -> bytes:
    facade = StorageFacade.from_path(path, profile, auth=auth)
    return facade.read(path, ...)
```

`copy_between()` takes two pre-built facades — no signature change needed.

### load_storage() Convenience

New application-layer function for config-driven usage. The facade stays
ignorant of `SettingsParameters` — it receives materialised instances.

```python
# settings/loader.py
from mountainash_auth_client import AUTH_REGISTRY, AuthMode, CONST_AUTH_MODE
from mountainash_settings import SettingsParameters, get_settings

from .registry import STORAGE_REGISTRY
from .profile import StorageProfile


def load_storage(
    provider: str,
    *,
    config_file: str | None = None,
    secrets_provider: str | None = None,
    auth_mode: CONST_AUTH_MODE | None = None,
) -> tuple[StorageProfile, AuthMode]:
    spec = STORAGE_REGISTRY.get_descriptor(provider)
    profile_cls = STORAGE_REGISTRY.get_settings_class(provider)

    effective_auth = auth_mode or spec.default_auth
    if effective_auth not in spec.supported_auth:
        raise ValueError(
            f"Auth mode {effective_auth!r} is not supported for provider "
            f"{provider!r}. Supported: {sorted(spec.supported_auth)}"
        )
    auth_cls = AUTH_REGISTRY.get_settings_class(effective_auth)

    config_files = [config_file] if config_file else []

    profile = get_settings(settings_parameters=SettingsParameters.create(
        settings_class=profile_cls,
        config_files=config_files,
        secrets_provider=secrets_provider,
    ))
    auth = get_settings(settings_parameters=SettingsParameters.create(
        settings_class=auth_cls,
        config_files=config_files,
        secrets_provider=secrets_provider,
    ))
    return profile, auth
```

Usage:
```python
# Config-driven
profile, auth = load_storage("s3", config_file="s3-prod.yaml")
facade = StorageFacade(CONST_STORAGE_PROVIDER_TYPE.S3, profile=profile, auth=auth)

# Override auth mode
profile, auth = load_storage("s3", auth_mode=CONST_AUTH_MODE.TOKEN,
                             config_file="s3-temp.yaml")

# Programmatic (no config)
from mountainash_auth_client import IAMAuth
facade = StorageFacade(
    CONST_STORAGE_PROVIDER_TYPE.S3,
    profile=S3Settings(FLAVOR="r2", ACCOUNT_ID="abc123"),
    auth=IAMAuth(ACCESS_KEY_ID="AKIA...", SECRET_ACCESS_KEY="..."),
)
```

### Removals

| Item | Action |
|------|--------|
| `settings/base.py` (`StorageAuthBase`) | Delete — auth fields now on auth-client Profile subclasses |
| `CONST_STORAGE_AUTH_METHOD` in `constants.py` | Delete — replaced by `CONST_AUTH_MODE` from auth-client |
| `_accepts_auth()` in `storage_registry/registry.py` | Delete — all backends accept `auth` uniformly |
| `hasattr(self._backend, "auth")` guard in facade | Delete — no longer needed |
| HTTP backend `_get_client()` auth handling | Delete — moved to HTTP adapter |

### Breaking Changes

| Change | Migration |
|--------|-----------|
| `auth_params` → `profile` on facade, registry, backends, `read_bytes()`, `storage()` | Rename at call sites |
| `StorageAuthBase` removed | Settings classes inherit `StorageProfile` only; auth fields come from auth-client instances |
| `CONST_STORAGE_AUTH_METHOD` removed | Use `CONST_AUTH_MODE` from `mountainash_auth_client` |

## Change Map

**mountainash-auth-client (upstream, already landed):**
- `CONST_AUTH_MODE` StrEnum in constants
- `AuthMode` type alias in `__init__.py`

**mountainash-utils-files — Removals:**

| File | Change |
|------|--------|
| `settings/base.py` | Delete (`StorageAuthBase`) |
| `settings/__init__.py` | Remove `StorageAuthBase` export |
| `constants.py` | Remove `CONST_STORAGE_AUTH_METHOD` |
| `storage_registry/registry.py` | Remove `_accepts_auth()` |

**mountainash-utils-files — Settings layer:**

| File | Change |
|------|--------|
| `settings/descriptor.py` | Add `default_auth` and `supported_auth` fields |
| `settings/profile.py` | `to_handler_kwargs(auth=None)`, fix duplicate `_default_kwargs()` |
| `settings/providers/*.py` (all 9) | Drop `StorageAuthBase` inheritance, drop `auth_modes`, add `default_auth` + `supported_auth`, remove auth type imports |
| `settings/adapters/*.py` (all 9) | Add `auth: AuthMode \| None` param, `isinstance()` checks, UPPERCASE fields |

**mountainash-utils-files — Runtime layer:**

| File | Change |
|------|--------|
| `storage_registry/registry.py` | `get_storage_backend(provider_type, profile, *, auth)` — typed, no introspection |
| `storage_facade/facade.py` | `__init__(provider_type, profile, *, auth)`, `from_path()`, remove auth guard |
| `storage_facade/read_bytes.py` | `auth_params` → `profile`, typed |
| `__init__.py` | `storage()` — `auth_params` → `profile`, typed |
| `storage_backends/s3/__init__.py` | `__init__(profile, *, auth)` — typed |
| `storage_backends/local/__init__.py` | `__init__(profile, *, auth)` — typed |
| `storage_backends/http/__init__.py` | `__init__(profile, *, auth)` — typed, remove `_get_client()` auth logic |

**mountainash-utils-files — New:**

| File | Purpose |
|------|---------|
| `settings/loader.py` | `load_storage()` — SettingsParameters → materialised profile + auth |

**mountainash-utils-files — Tests:**

| Concern | Change |
|---------|--------|
| All test call sites using `auth_params=` | Rename to `profile=` |
| Tests constructing `StorageAuthBase` directly | Remove or replace with auth-client instances |
| Adapter tests | Update to pass `auth` as second param with UPPERCASE fields |

**Out of scope:**
- mountainash-data adaptation
- mountainash-wearables adaptation
- New storage backends beyond the 3 existing (S3, local, HTTP)

## Migration Order

1. **mountainash-auth-client** — `CONST_AUTH_MODE` StrEnum and `AuthMode`
   type alias (already landed).
2. **mountainash-settings** — `auth_modes` removed from `ProfileSpec`
   (already landed).
3. **mountainash-utils-files** — all changes in this spec.
