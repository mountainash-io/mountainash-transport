# Auth-Client Integration Design Spec

**Date**: 2026-06-04
**Status**: Draft (rev 2 — post adversarial review)
**Package**: mountainash-utils-files
**Prerequisite for**: mountainash-file-client P1

## Problem

The auth types used across all 9 provider settings files (`NoAuth`, `TokenAuth`,
`PasswordAuth`, `IAMAuth`, etc.) are imported from `mountainash_settings.auth` —
a module that no longer exists. These types were extracted into the standalone
`mountainash-auth-client` package, but this consumer was never updated. Every
settings-related test fails with `ModuleNotFoundError`.

Separately, the HTTP backend ignores `auth_params` entirely — it always creates
a bare `httpx.Client()` with no authentication, timeouts, or custom headers,
even when a fully-configured `HTTPSettings` profile is provided.

Finally, the upcoming `mountainash-file-client` package needs to pass
`AuthSpec` objects directly to utils-files without constructing a full
`HTTPSettings` profile (P1 prerequisite in the file-client design spec).

## Solution

Three changes shipped as one PR:

1. **Import migration** — replace `mountainash_settings.auth` → `mountainash_auth_client` across all provider settings files, adapters, tests, and re-export surfaces.
2. **Fix HTTP backend** — wire `auth_params` through to `httpx.Client` when a profile is provided.
3. **New `auth=` parameter** — accept `AuthSpec` directly on `StorageFacade`, `HTTPStorageBackend`, and `read_bytes()`.

## Change 1: Import Migration

### Full migration inventory

**Provider settings (9 files):**

| File | Auth types imported |
|------|-------------------|
| `settings/providers/s3_settings.py` | `IAMAuth`, `NoAuth`, `TokenAuth` |
| `settings/providers/gcs_settings.py` | `NoAuth`, `ServiceAccountAuth` + others |
| `settings/providers/azure_settings.py` | `AzureADAuth`, `NoAuth`, `PasswordAuth` + others |
| `settings/providers/ssh_settings.py` | `CertificateAuth`, `KerberosAuth`, `PasswordAuth` |
| `settings/providers/ftp_settings.py` | `NoAuth`, `PasswordAuth` |
| `settings/providers/smb_settings.py` | `KerberosAuth`, `PasswordAuth` |
| `settings/providers/local_settings.py` | `NoAuth` |
| `settings/providers/github_settings.py` | `JWTAuth`, `NoAuth`, `OAuth2Auth`, `TokenAuth` |
| `settings/providers/http_settings.py` | `NoAuth`, `PasswordAuth`, `TokenAuth` |

**Adapters** — `settings/adapters/http.py` uses `type(auth).__name__` string
matching, not direct imports. No import change needed, but verify the class
names match auth-client's classes (they do — same names).

**Package re-exports** — grep `settings/__init__.py` and the top-level
`__init__.py` for any re-exports of auth types. If found, update or remove.

**Tests** — all test files under `tests/test_unit/settings/` that import
auth types need the same migration. Full grep for
`from mountainash_settings.auth` across the entire repo.

**Commented-out imports** — `settings/utils/connection.py` and
`settings/utils/validation.py` have commented-out imports from
`mountainash_settings.auth.storage.exceptions`. Update comments or remove
if the referenced exceptions no longer exist.

### Migration rule

```python
# Before
from mountainash_settings.auth import NoAuth, TokenAuth, PasswordAuth

# After
from mountainash_auth_client import NoAuth, TokenAuth, PasswordAuth
```

The auth types are identical classes — same field names, same discriminators,
same Pydantic BaseModel subclasses. No downstream code changes are required
beyond the import path.

### Dependency change

`mountainash-auth-client` becomes a **core dependency** in `pyproject.toml`
(not optional). The settings providers import auth types unconditionally at
class-definition time — guarding behind `try/except ImportError` is not
feasible without restructuring the entire settings layer.

## Change 2: Fix HTTP Backend

`HTTPStorageBackend._get_client()` currently creates a bare `httpx.Client()`.
When `auth_params` is an `HTTPSettings` profile (or any object with
`to_handler_kwargs()`), the method should use the profile's kwargs:

```python
def _get_client(self) -> httpx.Client:
    if self._client is None:
        kwargs: dict[str, t.Any] = {}
        if hasattr(self.auth_params, "to_handler_kwargs"):
            kwargs = self.auth_params.to_handler_kwargs()
        self._client = httpx.Client(**kwargs)
    return self._client
```

This enables:
- **Authentication**: `Authorization` headers from the profile's `auth` field
  via `_resolve_auth_headers()` in the HTTP adapter.
- **Timeouts**: `httpx.Timeout(connect=..., read=..., write=...)` from profile fields.
- **SSL verification**: `verify=True/False` from `VERIFY_SSL`.
- **Redirects**: `follow_redirects` and `max_redirects` from profile fields.
- **Custom headers**: Merged with auth headers from the `HEADERS` field.

When `auth_params` is `None` or lacks `to_handler_kwargs`, behavior is
unchanged — bare `httpx.Client()`.

## Change 3: New `auth=` Parameter

### Public API additions

**StorageFacade**:
```python
class StorageFacade:
    def __init__(
        self,
        provider_type: CONST_STORAGE_PROVIDER_TYPE,
        auth_params: typing.Any = None,
        *,
        auth: "AuthSpec | None" = None,  # NEW
    ) -> None: ...

    @classmethod
    def from_path(
        cls,
        path: str,
        auth_params: typing.Any = None,
        *,
        auth: "AuthSpec | None" = None,  # NEW
    ) -> StorageFacade: ...
```

**read_bytes()**:
```python
def read_bytes(
    path: str,
    *,
    auth_params: typing.Any = None,
    auth: "AuthSpec | None" = None,  # NEW
    infer: bool = False,
    gpg: GPG | None = None,
    gzip: Gzip | None = None,
) -> bytes: ...
```

### Precedence (auth-header level, not client level)

When both `auth` and `auth_params` are provided, precedence applies **only at
the auth-header level**. The profile's non-auth configuration (timeouts, SSL,
redirects, custom non-auth headers) is always preserved.

Resolution in `_get_client()`:

1. Start with base kwargs from `auth_params.to_handler_kwargs()` if available
   (timeouts, SSL, redirects, custom headers including any profile-derived
   Authorization header).
2. If `auth` (AuthSpec) is also provided, compute auth headers from it via
   `_resolve_auth_headers(auth)` and **merge them into the kwargs headers**,
   overriding any `Authorization` header from the profile.
3. If only `auth` is provided (no profile), create `httpx.Client(headers=...)`
   with just the auth headers (default httpx timeouts apply).
4. If neither is provided, bare `httpx.Client()`.

**Header merge semantics**: Auth headers from `auth=` override headers with
matching keys (case-insensitive) from the profile. Non-auth headers from the
profile are preserved. This is a shallow dict merge:
`{**profile_headers, **auth_headers}`.

**`auth=NoAuth()` explicitly strips** any `Authorization` header that would
have come from the profile. This is intentional — it lets callers override
profile auth for anonymous access.

### Backend plumbing

`get_storage_backend()` in the storage registry gains an `auth` keyword
argument. The registry uses `inspect.signature` on the backend class's
`__init__` to check whether it accepts an `auth` parameter. If it does,
`auth` is forwarded. If not, `auth` is not passed — no `TypeError` catch,
no silent retry.

`HTTPStorageBackend.__init__` accepts `auth: AuthSpec | None = None`.
Other backends' signatures are unchanged and do not receive `auth`.

**Non-HTTP providers with `auth=`**: If `auth` is provided and the resolved
backend does not accept `auth` in its `__init__` signature, `StorageFacade`
raises `ValueError("auth= is not supported for provider {provider_type}; "
"use auth_params with a profile instead")`. This prevents silent no-ops
where auth is provided but never applied.

### Auth types supported for direct `auth=` usage

| AuthSpec subclass | HTTP mapping |
|-------------------|-------------|
| `NoAuth` | No `Authorization` header (strips profile auth if present) |
| `TokenAuth` | `Authorization: Bearer {token}` |
| `PasswordAuth` | `Authorization: Basic {base64(user:pass)}` |
| `OAuth2Auth` | `Authorization: Bearer {token}` (when `token` is set; no header when only client credentials) |
| `OAuth2AuthCodeAuth` | `Authorization: Bearer {access_token}` (when `access_token` is set) |

`OAuth2AuthCodeAuth` is a valid `AuthSpec` subclass in mountainash-auth-client
but is not currently listed in any provider's `auth_modes`. It is supported
here for direct `auth=` usage only, enabling file-client consumers who
authenticate via OAuth2 authorization code flow.

The existing `_resolve_auth_headers()` in `settings/adapters/http.py` handles
`TokenAuth` and `PasswordAuth`. Three additions are needed:
- `NoAuth`: return empty dict (existing behavior, made explicit).
- `OAuth2Auth`: extract `token` field → Bearer header. Return empty dict if
  only `client_id`/`client_secret` are set (no bearer token available).
- `OAuth2AuthCodeAuth`: extract `access_token` field → Bearer header. Return
  empty dict if `access_token` is `None`.

### Error behaviour for expired/invalid tokens

The HTTP backend does not refresh tokens or manage token lifecycle. When a
request returns HTTP 401 or 403, the backend raises `AuthenticationError`
with the status code and URL, same as today. Callers (e.g. file-client)
are responsible for catching `AuthenticationError`, refreshing tokens via
auth-client's `RefreshableAuth` protocol, and retrying.

The `httpx.Client` is created once per backend instance. If a caller refreshes
a token and needs it applied, they must create a new `StorageFacade` /
`HTTPStorageBackend` instance with the new `AuthSpec`. The backend does not
re-read the `AuthSpec` after client creation.

### What is NOT in scope

- **OAuth token refresh**: Stays in the consuming layer (e.g. file-client's
  retry loop). The HTTP backend does not refresh tokens.
- **OAuth1**: Rare for HTTP file sources. Not supported for direct `auth=`.
- **mTLS / client certificates**: Not supported via direct `auth=`.
  Client certificate configuration is available through `HTTPSettings` profile
  (via httpx's `cert` parameter in `to_handler_kwargs()`) if needed in future.
  Currently no provider uses it.
- **Non-HTTP backends**: Only the HTTP backend accepts `auth=` initially.
  Other backends continue to use `auth_params` with their existing profile-based
  auth resolution. Passing `auth=` to a non-HTTP provider raises `ValueError`.

## Auth-Client Capability Gaps

**None identified.** The auth-client package provides all auth types needed by
utils-files. The `auth_to_driver_kwargs()` dispatch function produces generic
driver kwargs (e.g. `{"token": "..."}`) which are useful for database drivers
but not HTTP-specific. The HTTP adapter's `_resolve_auth_headers()` handles the
HTTP-specific mapping (auth type → `Authorization` header), which is the correct
separation of concerns. No changes to `mountainash-auth-client` are required.

## Testing Strategy

- **Import smoke test**: Verify all 9 provider settings classes can be imported
  without `ModuleNotFoundError`. Full grep for residual `mountainash_settings.auth`
  imports across the repo to catch any missed files.
- **HTTPSettings profile test**: Create an `HTTPSettings` with `TokenAuth`,
  verify `to_handler_kwargs()` produces correct `Authorization: Bearer ...`
  header alongside timeouts and other config.
- **HTTP backend profile test**: Instantiate `HTTPStorageBackend` with an
  `HTTPSettings` profile, verify the `httpx.Client` is created with correct
  kwargs (mock `httpx.Client` constructor).
- **HTTP backend direct auth test**: Instantiate with `auth=TokenAuth(...)`,
  verify `Authorization: Bearer ...` header on the client.
- **Auth + profile precedence test**: Provide both `auth=TokenAuth("new")`
  and `auth_params=HTTPSettings(auth=TokenAuth("old"), TIMEOUT_READ=60)`.
  Verify: auth header uses "new" token, timeout uses 60s from profile.
- **NoAuth override test**: Provide `auth=NoAuth()` alongside profile with
  `TokenAuth`. Verify no `Authorization` header on the client.
- **Non-HTTP auth= rejection test**: Pass `auth=TokenAuth(...)` to an S3
  `StorageFacade`. Verify `ValueError` is raised.
- **read_bytes auth forwarding**: Verify `auth=` is forwarded through
  `StorageFacade.from_path()` to the backend.
- **OAuth2Auth mapping**: Verify Bearer header when `token` is set. Verify
  no header when only `client_id`/`client_secret` are set.
- **OAuth2AuthCodeAuth mapping**: Verify Bearer header from `access_token`.
  Verify no header when `access_token` is `None`.
- **401/403 error propagation**: Verify `AuthenticationError` is raised with
  status code and URL (existing behavior, confirm not broken by changes).
- **Existing tests**: All currently-broken settings tests should pass after
  the import migration.

## Adversarial Review Findings Addressed

| # | Finding | Resolution |
|---|---------|-----------|
| 1 | Import inventory incomplete | Expanded to cover adapters, re-exports, tests, commented imports |
| 2 | Precedence discards non-auth profile config | Precedence now auth-header-level only; profile timeouts/SSL/redirects preserved |
| 3 | Header merging unspecified | Specified as shallow dict merge; auth headers override matching keys |
| 4 | TypeError catch masks constructor bugs | Replaced with `inspect.signature` check |
| 5 | Silent no-op for non-HTTP auth= | `ValueError` raised when auth= used with unsupported provider |
| 6 | Direct auth path omits timeout/streaming | Clarified: direct auth without profile gets default httpx timeouts; errors handled by existing per-request exception mapping |
| 7 | Expired token failure behavior undefined | Specified: 401/403 → `AuthenticationError`; no refresh; new instance required for new token |
| 8 | OAuth2AuthCodeAuth ambiguous | Clarified: valid AuthSpec subclass, supported for direct auth= only, not in any provider's auth_modes |
| 9 | NoAuth + profile auth interaction | Specified: `auth=NoAuth()` explicitly strips profile Authorization header |
| 10 | mTLS not covered | Explicitly out of scope for direct auth=; profile-only if needed |
