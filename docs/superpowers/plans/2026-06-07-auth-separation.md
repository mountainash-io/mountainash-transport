# Auth Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate auth from storage profiles so both are independent top-level settings instances, replacing `t.Any` with proper types throughout, and removing the legacy `StorageAuthBase` mixin.

**Architecture:** Auth modes (from mountainash-auth-client) are now Profile subclasses with UPPERCASE fields. Storage profiles describe connection parameters only. The facade, registry, and backends accept both as separate typed parameters. A new `load_storage()` convenience handles config-driven materialisation.

**Tech Stack:** Python 3.12, mountainash-settings (Profile/ProfileSpec/Registry), mountainash-auth-client (AuthMode/CONST_AUTH_MODE/AUTH_REGISTRY), pydantic v2

---

### Task 1: Remove StorageAuthBase and CONST_STORAGE_AUTH_METHOD

**Files:**
- Delete: `src/mountainash_utils_files/settings/base.py`
- Modify: `src/mountainash_utils_files/settings/__init__.py`
- Modify: `src/mountainash_utils_files/constants.py`

- [ ] **Step 1: Remove StorageAuthBase from settings/__init__.py**

Replace the full contents of `src/mountainash_utils_files/settings/__init__.py` — remove `StorageAuthBase` import and export, keep everything else:

```python
from .exceptions import (
    StorageConfigError,
    StorageConnectionError,
    StorageValidationError,
    StorageSecurityError,
    StorageQuotaError,
    StoragePermissionError,
    StorageProviderError,
    StorageRetryableError,
    StorageTimeoutError,
    StorageNotFoundError,
)
from .templates import StorageAuthTemplates

__all__ = [
    "StorageConfigError",
    "StorageConnectionError",
    "StorageValidationError",
    "StorageSecurityError",
    "StorageQuotaError",
    "StoragePermissionError",
    "StorageProviderError",
    "StorageRetryableError",
    "StorageTimeoutError",
    "StorageNotFoundError",
    "StorageAuthTemplates",
]
```

- [ ] **Step 2: Delete settings/base.py**

```bash
rm src/mountainash_utils_files/settings/base.py
```

- [ ] **Step 3: Remove CONST_STORAGE_AUTH_METHOD from constants.py**

In `src/mountainash_utils_files/constants.py`, delete the `CONST_STORAGE_AUTH_METHOD` class (lines 53-63):

```python
class CONST_STORAGE_AUTH_METHOD(_FindMemberMixin):
    """Authentication methods"""
    NONE = "none"
    KEY = "key"
    PASSWORD = "password"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    IAM = "iam"
    MANAGED_IDENTITY = "managed_identity"
    KERBEROS = "kerberos"
    SERVICE_ACCOUNT = "service_account"
```

- [ ] **Step 4: Run lint to check for remaining references**

```bash
hatch run ruff:check 2>&1 | head -30
```

Expected: Import errors from providers that still reference `StorageAuthBase` and `CONST_STORAGE_AUTH_METHOD`. These will be fixed in subsequent tasks.

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "refactor: remove StorageAuthBase and CONST_STORAGE_AUTH_METHOD

Auth fields now live on auth-client Profile subclasses (separate
instances). The legacy mixin and enum are replaced by
mountainash_auth_client.AuthMode and CONST_AUTH_MODE."
```

---

### Task 2: Update StorageDescriptor with auth metadata fields

**Files:**
- Modify: `src/mountainash_utils_files/settings/descriptor.py`

- [ ] **Step 1: Add default_auth and supported_auth to StorageDescriptor**

In `src/mountainash_utils_files/settings/descriptor.py`, add the import and two new fields:

```python
"""Storage-flavored ProfileSpec with typed metadata fields.

Retained in mountainash-utils-files (rather than lifted to mountainash-settings)
because these fields are domain-specific: handler_module, supports_streaming,
and read_only are meaningful only for storage providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mountainash_auth_client import CONST_AUTH_MODE
from mountainash_settings.profiles import (
    MISSING,
    ParameterSpec,
    ProfileSpec,
)

__all__ = ["MISSING", "ParameterSpec", "StorageDescriptor"]


@dataclass(frozen=True, kw_only=True)
class StorageDescriptor(ProfileSpec):
    """ProfileSpec with storage-provider-specific typed metadata.

    Extra fields:
        sdk_package: Canonical PyPI name of the SDK this provider uses
            (``"boto3"``, ``"google-cloud-storage"``, ``"paramiko"``, etc.).
            ``None`` for stdlib-only providers (``LocalSettings``, ``FTPSettings``).
        handler_module: Dotted module path where the storage backend lives
            (e.g. ``"mountainash_utils_files.storage_backends.s3"``).
        handler_class: Class name of the backend within handler_module
            (e.g. ``"S3StorageBackend"``).
        supports_streaming: Whether the backend supports streaming reads/writes.
        supports_multipart: Whether the backend supports multipart upload.
        read_only: Whether the backend is read-only (``GitHubRepoSettings`` = True).
        default_auth: Auth mode used by ``load_storage()`` when caller doesn't specify.
        supported_auth: Full set of valid auth modes for this provider.
    """

    sdk_package: str | None = None
    handler_module: str = ""
    handler_class: str = ""
    supports_streaming: bool = True
    supports_multipart: bool = True
    read_only: bool = False
    default_auth: CONST_AUTH_MODE = CONST_AUTH_MODE.NONE
    supported_auth: frozenset[CONST_AUTH_MODE] = field(
        default_factory=lambda: frozenset({CONST_AUTH_MODE.NONE})
    )
```

- [ ] **Step 2: Commit**

```bash
git add src/mountainash_utils_files/settings/descriptor.py
git commit -m "feat: add default_auth and supported_auth to StorageDescriptor"
```

---

### Task 3: Update StorageProfile.to_handler_kwargs()

**Files:**
- Modify: `src/mountainash_utils_files/settings/profile.py`

- [ ] **Step 1: Add auth parameter and fix duplicate _default_kwargs() bug**

Replace the full contents of `src/mountainash_utils_files/settings/profile.py`:

```python
"""StorageProfile — storage-flavored subclass of Profile.

Adds ``to_handler_kwargs()`` on top of the generic mechanism provided by
:class:`mountainash_settings.profiles.Profile`.
"""

from __future__ import annotations

import typing as t

from mountainash_settings.profiles import Profile, lookup_class_var

if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthMode

__all__ = ["StorageProfile"]


class StorageProfile(Profile):
    """Storage provider settings.

    Public API:
        - :meth:`to_handler_kwargs` — dict ready for the provider SDK client
          constructor (``boto3.client``, ``google.cloud.storage.Client``,
          ``BlobServiceClient``, ``paramiko.SSHClient.connect``, etc.).

    Subclasses set ``__spec__`` (a :class:`StorageDescriptor`) and
    optionally ``__adapter__``. Field installation, template wiring,
    and validation are inherited from :class:`Profile`.
    """

    def to_handler_kwargs(
        self, auth: AuthMode | None = None,
    ) -> dict[str, t.Any]:
        """Build the final SDK-client kwargs dict.

        If ``__adapter__`` is set, adapter owns the full pipeline — it
        receives the profile and auth, and layers provider-specific
        construction on top. Otherwise defaults to spec ``driver_key``
        mappings via ``_default_kwargs()``.
        """
        adapter = lookup_class_var(type(self), "__adapter__")
        if adapter is not None:
            return adapter(self, auth)
        return self._default_kwargs()
```

- [ ] **Step 2: Commit**

```bash
git add src/mountainash_utils_files/settings/profile.py
git commit -m "feat: add auth parameter to StorageProfile.to_handler_kwargs()

Also fixes pre-existing bug where _default_kwargs() was called twice."
```

---

### Task 4: Update all 9 provider settings files

Each provider drops `StorageAuthBase` inheritance, removes `auth_modes`, replaces auth type imports with `CONST_AUTH_MODE`, and adds `default_auth` + `supported_auth`. The `_adapter()` callable gains an `auth` parameter.

**Files:**
- Modify: `src/mountainash_utils_files/settings/providers/s3_settings.py`
- Modify: `src/mountainash_utils_files/settings/providers/gcs_settings.py`
- Modify: `src/mountainash_utils_files/settings/providers/azure_settings.py`
- Modify: `src/mountainash_utils_files/settings/providers/ssh_settings.py`
- Modify: `src/mountainash_utils_files/settings/providers/ftp_settings.py`
- Modify: `src/mountainash_utils_files/settings/providers/smb_settings.py`
- Modify: `src/mountainash_utils_files/settings/providers/http_settings.py`
- Modify: `src/mountainash_utils_files/settings/providers/github_settings.py`
- Modify: `src/mountainash_utils_files/settings/providers/local_settings.py`

- [ ] **Step 1: Update s3_settings.py**

Apply these changes to `src/mountainash_utils_files/settings/providers/s3_settings.py`:

1. Replace the auth import (line 19):
   ```python
   # Before:
   from mountainash_auth_client import IAMAuth, NoAuth, TokenAuth
   # After:
   from mountainash_auth_client import CONST_AUTH_MODE
   ```

2. Remove the `StorageAuthBase` import (line 24):
   ```python
   # Delete this line:
   from ..base import StorageAuthBase
   ```

3. Replace `auth_modes` on S3_SPEC (line 179):
   ```python
   # Before:
       auth_modes=[IAMAuth, TokenAuth, NoAuth],
   # After:
       default_auth=CONST_AUTH_MODE.IAM,
       supported_auth=frozenset({
           CONST_AUTH_MODE.IAM,
           CONST_AUTH_MODE.TOKEN,
           CONST_AUTH_MODE.NONE,
       }),
   ```

4. Update `_adapter()` signature (lines 194-197):
   ```python
   def _adapter(profile: "S3Settings", auth=None):
       from ..adapters.s3 import build_handler_kwargs
       return build_handler_kwargs(profile, auth)
   ```

5. Remove `StorageAuthBase` from class bases (line 201):
   ```python
   # Before:
   class S3Settings(StorageProfile, StorageAuthBase):
   # After:
   class S3Settings(StorageProfile):
   ```

- [ ] **Step 2: Update gcs_settings.py**

Apply the same pattern to `src/mountainash_utils_files/settings/providers/gcs_settings.py`:

1. Replace auth imports (lines 16-22):
   ```python
   # Before:
   from mountainash_auth_client import (
       IAMAuth, NoAuth, OAuth2Auth, ServiceAccountAuth, TokenAuth,
   )
   # After:
   from mountainash_auth_client import CONST_AUTH_MODE
   ```

2. Remove `StorageAuthBase` import and update class bases.

3. Replace `auth_modes` on GCS_SPEC (line 133):
   ```python
       default_auth=CONST_AUTH_MODE.SERVICE_ACCOUNT,
       supported_auth=frozenset({
           CONST_AUTH_MODE.SERVICE_ACCOUNT,
           CONST_AUTH_MODE.IAM,
           CONST_AUTH_MODE.OAUTH2,
           CONST_AUTH_MODE.TOKEN,
           CONST_AUTH_MODE.NONE,
       }),
   ```

4. Update `_adapter()` to accept `auth` and forward it.

- [ ] **Step 3: Update azure_settings.py**

Apply the same pattern to `src/mountainash_utils_files/settings/providers/azure_settings.py`:

1. Replace auth imports (lines 23-28):
   ```python
   # Before:
   from mountainash_auth_client import (
       AzureADAuth, NoAuth, PasswordAuth, TokenAuth,
   )
   # After:
   from mountainash_auth_client import CONST_AUTH_MODE
   ```

2. Remove `StorageAuthBase` import and update class bases.

3. Replace `auth_modes` on AZURE_STORAGE_SPEC (line 186):
   ```python
       default_auth=CONST_AUTH_MODE.AZURE_AD,
       supported_auth=frozenset({
           CONST_AUTH_MODE.AZURE_AD,
           CONST_AUTH_MODE.TOKEN,
           CONST_AUTH_MODE.PASSWORD,
           CONST_AUTH_MODE.NONE,
       }),
   ```

4. Update `_adapter()` to accept `auth` and forward it.

- [ ] **Step 4: Update ssh_settings.py**

1. Replace auth imports (line 21):
   ```python
   # Before:
   from mountainash_auth_client import CertificateAuth, KerberosAuth, PasswordAuth
   # After:
   from mountainash_auth_client import CONST_AUTH_MODE
   ```

2. Remove `StorageAuthBase` import, update class bases.

3. Replace `auth_modes` (line 161):
   ```python
       default_auth=CONST_AUTH_MODE.PASSWORD,
       supported_auth=frozenset({
           CONST_AUTH_MODE.PASSWORD,
           CONST_AUTH_MODE.CERTIFICATE,
           CONST_AUTH_MODE.KERBEROS,
       }),
   ```

4. Update `_adapter()`.

- [ ] **Step 5: Update ftp_settings.py**

1. Replace auth imports (line 16):
   ```python
   # Before:
   from mountainash_auth_client import NoAuth, PasswordAuth
   # After:
   from mountainash_auth_client import CONST_AUTH_MODE
   ```

2. Remove `StorageAuthBase` import, update class bases.

3. Replace `auth_modes` (line 126):
   ```python
       default_auth=CONST_AUTH_MODE.PASSWORD,
       supported_auth=frozenset({
           CONST_AUTH_MODE.PASSWORD,
           CONST_AUTH_MODE.NONE,
       }),
   ```

4. Update `_adapter()`.

- [ ] **Step 6: Update smb_settings.py**

1. Replace auth imports (line 27):
   ```python
   # Before:
   from mountainash_auth_client import KerberosAuth, PasswordAuth
   # After:
   from mountainash_auth_client import CONST_AUTH_MODE
   ```

2. Remove `StorageAuthBase` import, update class bases.

3. Replace `auth_modes` (line 101):
   ```python
       default_auth=CONST_AUTH_MODE.PASSWORD,
       supported_auth=frozenset({
           CONST_AUTH_MODE.PASSWORD,
           CONST_AUTH_MODE.KERBEROS,
       }),
   ```

4. Update `_adapter()`.

- [ ] **Step 7: Update http_settings.py**

1. Replace auth imports (line 10):
   ```python
   # Before:
   from mountainash_auth_client import NoAuth, PasswordAuth, TokenAuth
   # After:
   from mountainash_auth_client import CONST_AUTH_MODE
   ```

2. Remove `StorageAuthBase` import, update class bases.

3. Replace `auth_modes` (line 81):
   ```python
       default_auth=CONST_AUTH_MODE.NONE,
       supported_auth=frozenset({
           CONST_AUTH_MODE.NONE,
           CONST_AUTH_MODE.TOKEN,
           CONST_AUTH_MODE.PASSWORD,
       }),
   ```

4. Update `_adapter()`.

- [ ] **Step 8: Update github_settings.py**

1. Replace auth imports (line 25):
   ```python
   # Before:
   from mountainash_auth_client import JWTAuth, NoAuth, OAuth2Auth, TokenAuth
   # After:
   from mountainash_auth_client import CONST_AUTH_MODE
   ```

2. Remove `StorageAuthBase` import, update class bases.

3. Replace `auth_modes` (line 91):
   ```python
       default_auth=CONST_AUTH_MODE.TOKEN,
       supported_auth=frozenset({
           CONST_AUTH_MODE.TOKEN,
           CONST_AUTH_MODE.OAUTH2,
           CONST_AUTH_MODE.JWT,
           CONST_AUTH_MODE.NONE,
       }),
   ```

4. Update `_adapter()`.

- [ ] **Step 9: Update local_settings.py**

1. Replace auth imports (line 31):
   ```python
   # Before:
   from mountainash_auth_client import NoAuth
   # After:
   from mountainash_auth_client import CONST_AUTH_MODE
   ```

2. Remove `StorageAuthBase` import, update class bases.

3. Replace `auth_modes` (line 83):
   ```python
       default_auth=CONST_AUTH_MODE.NONE,
       supported_auth=frozenset({CONST_AUTH_MODE.NONE}),
   ```

4. Update `_adapter()`.

- [ ] **Step 10: Run lint**

```bash
hatch run ruff:check 2>&1 | head -30
```

Expected: No import errors from provider files. Adapter files may still have issues (fixed in next task).

- [ ] **Step 11: Commit**

```bash
git add src/mountainash_utils_files/settings/providers/
git commit -m "refactor: drop StorageAuthBase and auth_modes from all providers

Each provider now declares default_auth and supported_auth via
CONST_AUTH_MODE. Auth type imports move to adapter files."
```

---

### Task 5: Update all 9 adapter files

Each adapter gains `auth: AuthMode | None = None` as a second parameter, replaces `type(auth).__name__` with `isinstance()`, and uses UPPERCASE field names.

**Files:**
- Modify: `src/mountainash_utils_files/settings/adapters/s3.py`
- Modify: `src/mountainash_utils_files/settings/adapters/gcs.py`
- Modify: `src/mountainash_utils_files/settings/adapters/azure.py`
- Modify: `src/mountainash_utils_files/settings/adapters/ssh.py`
- Modify: `src/mountainash_utils_files/settings/adapters/ftp.py`
- Modify: `src/mountainash_utils_files/settings/adapters/smb.py`
- Modify: `src/mountainash_utils_files/settings/adapters/http.py`
- Modify: `src/mountainash_utils_files/settings/adapters/github.py`
- Modify: `src/mountainash_utils_files/settings/adapters/local.py`

- [ ] **Step 1: Update s3.py adapter**

In `src/mountainash_utils_files/settings/adapters/s3.py`:

1. Add auth imports after the existing imports (after line 15):
   ```python
   from mountainash_auth_client import AuthMode, IAMAuth, TokenAuth
   ```

2. Change `build_handler_kwargs` signature (line 73):
   ```python
   def build_handler_kwargs(profile: "StorageProfile", auth: AuthMode | None = None) -> dict[str, t.Any]:
   ```

3. Replace the auth block (lines 119-133) with:
   ```python
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
   ```

- [ ] **Step 2: Update gcs.py adapter**

In `src/mountainash_utils_files/settings/adapters/gcs.py`:

1. Add auth imports:
   ```python
   from mountainash_auth_client import (
       AuthMode, IAMAuth, NoAuth, OAuth2Auth, ServiceAccountAuth, TokenAuth,
   )
   ```

2. Change `_resolve_credentials` signature:
   ```python
   def _resolve_credentials(auth: AuthMode | None) -> t.Any:
   ```

3. Replace all `auth_type = type(auth).__name__` + string checks with `isinstance()`:
   ```python
       if auth is None:
           return None
       if isinstance(auth, ServiceAccountAuth):
           # ... file or info path unchanged, but use UPPERCASE fields:
           sa_file = getattr(auth, "FILE", None)
           sa_info = getattr(auth, "INFO", None)
           ...
       elif isinstance(auth, TokenAuth):
           token = _unwrap_secret(auth.TOKEN)
           ...
       elif isinstance(auth, OAuth2Auth):
           token = _unwrap_secret(auth.TOKEN)
           ...
       elif isinstance(auth, (IAMAuth, NoAuth)):
           return None
       return None
   ```

4. Change `build_handler_kwargs` signature:
   ```python
   def build_handler_kwargs(profile: "StorageProfile", auth: AuthMode | None = None) -> dict[str, t.Any]:
   ```

5. Update the body to pass `auth` directly instead of extracting from profile:
   ```python
       credentials = _resolve_credentials(auth)
   ```

6. Update the NoAuth check:
   ```python
       if isinstance(auth, NoAuth):
           base["anonymous"] = True
   ```

- [ ] **Step 3: Update azure.py adapter**

In `src/mountainash_utils_files/settings/adapters/azure.py`:

1. Add auth imports:
   ```python
   from mountainash_auth_client import (
       AuthMode, AzureADAuth, NoAuth, PasswordAuth, TokenAuth,
   )
   ```

2. Change `_resolve_credential` signature:
   ```python
   def _resolve_credential(auth: AuthMode | None, account_name: t.Optional[str]) -> t.Any:
   ```

3. Replace string checks with `isinstance()` and UPPERCASE fields:
   ```python
       if auth is None or isinstance(auth, NoAuth):
           return None
       if isinstance(auth, AzureADAuth):
           tenant_id = auth.TENANT_ID
           client_id = auth.CLIENT_ID
           client_secret = auth.CLIENT_SECRET
           managed_identity = auth.MANAGED_IDENTITY
           ...
       elif isinstance(auth, TokenAuth):
           token = _unwrap_secret(auth.TOKEN)
           ...
       elif isinstance(auth, PasswordAuth):
           username = auth.USERNAME or account_name
           password = _unwrap_secret(auth.PASSWORD)
           ...
       return None
   ```

4. Change `build_handler_kwargs` signature:
   ```python
   def build_handler_kwargs(profile: "StorageProfile", auth: AuthMode | None = None) -> dict[str, t.Any]:
   ```

5. Update body to pass `auth` directly instead of extracting from profile.

- [ ] **Step 4: Update ssh.py adapter**

In `src/mountainash_utils_files/settings/adapters/ssh.py`:

1. Add auth imports:
   ```python
   from mountainash_auth_client import (
       AuthMode, CertificateAuth, KerberosAuth, PasswordAuth,
   )
   ```

2. Change `_auth_kwargs` signature:
   ```python
   def _auth_kwargs(auth: AuthMode | None, host: t.Optional[str]) -> dict[str, t.Any]:
   ```

3. Replace string checks with `isinstance()` and UPPERCASE fields.

4. Change `build_handler_kwargs` signature:
   ```python
   def build_handler_kwargs(profile: "StorageProfile", auth: AuthMode | None = None) -> dict[str, t.Any]:
   ```

- [ ] **Step 5: Update ftp.py adapter**

Same pattern. Auth types: `PasswordAuth`, `NoAuth`. UPPERCASE fields.

1. Add: `from mountainash_auth_client import AuthMode, NoAuth, PasswordAuth`
2. Update `_auth_kwargs(auth: AuthMode | None)` with `isinstance()`.
3. Update `build_handler_kwargs` signature.

- [ ] **Step 6: Update smb.py adapter**

Same pattern. Auth types: `PasswordAuth`, `KerberosAuth`. UPPERCASE fields.

1. Add: `from mountainash_auth_client import AuthMode, KerberosAuth, PasswordAuth`
2. Update `_auth_kwargs(auth: AuthMode | None, ...)` with `isinstance()`.
3. Update `build_handler_kwargs` signature.

- [ ] **Step 7: Update http.py adapter**

Same pattern. Auth types: `NoAuth`, `TokenAuth`, `JWTAuth`, `PasswordAuth`, `OAuth2Auth`, `OAuth2AuthCodeAuth`.

1. Add:
   ```python
   from mountainash_auth_client import (
       AuthMode, JWTAuth, NoAuth, OAuth2Auth, OAuth2AuthCodeAuth,
       PasswordAuth, TokenAuth,
   )
   ```
2. Update `_resolve_auth_headers(auth: AuthMode | None)` with `isinstance()` and UPPERCASE fields.
3. Update `build_handler_kwargs` signature.

- [ ] **Step 8: Update github.py adapter**

Same pattern. Auth types: `TokenAuth`, `JWTAuth`, `OAuth2Auth`, `NoAuth`.

1. Add: `from mountainash_auth_client import AuthMode, JWTAuth, NoAuth, OAuth2Auth, TokenAuth`
2. Update `_token_from_auth(auth: AuthMode | None)` with `isinstance()` and UPPERCASE fields.
3. Update `build_handler_kwargs` signature.

- [ ] **Step 9: Update local.py adapter**

Minimal change — local adapter doesn't use auth fields.

1. Add: `from mountainash_auth_client import AuthMode`
2. Update `build_handler_kwargs` signature to accept `auth: AuthMode | None = None` (ignored).

- [ ] **Step 10: Commit**

```bash
git add src/mountainash_utils_files/settings/adapters/
git commit -m "refactor: type adapters with AuthMode, use isinstance() and UPPERCASE fields

All 9 adapters now accept auth: AuthMode | None as a second parameter.
String-based type(auth).__name__ checks replaced with isinstance().
Auth field names updated to UPPERCASE per auth-client Profile convention."
```

---

### Task 6: Update registry, facade, and public API

**Files:**
- Modify: `src/mountainash_utils_files/storage_registry/registry.py`
- Modify: `src/mountainash_utils_files/storage_facade/facade.py`
- Modify: `src/mountainash_utils_files/storage_facade/read_bytes.py`
- Modify: `src/mountainash_utils_files/__init__.py`

- [ ] **Step 1: Update storage_registry/registry.py**

Replace the full contents of `src/mountainash_utils_files/storage_registry/registry.py`:

```python
# storage_registry/registry.py

import typing as t

from mountainash_auth_client import AuthMode
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE

if t.TYPE_CHECKING:
    from mountainash_utils_files.settings.profile import StorageProfile

_backend_registry: dict[CONST_STORAGE_PROVIDER_TYPE, type] = {}


def register_storage_backend(provider_type: CONST_STORAGE_PROVIDER_TYPE) -> t.Callable[[type], type]:
    """Decorator that registers a backend class for a provider type."""
    def decorator(cls: type) -> type:
        _backend_registry[provider_type] = cls
        return cls
    return decorator


def get_storage_backend(
    provider_type: CONST_STORAGE_PROVIDER_TYPE,
    profile: "StorageProfile | None",
    *,
    auth: AuthMode | None = None,
) -> t.Any:
    """Instantiate and return a backend for the given provider type."""
    cls = _backend_registry.get(provider_type)
    if cls is None:
        raise ValueError(f"No backend registered for {provider_type!r}")
    return cls(profile, auth=auth)


def get_registered_backends() -> dict[CONST_STORAGE_PROVIDER_TYPE, type]:
    """Return a copy of all registered backends."""
    return dict(_backend_registry)


def clear_registry() -> None:
    """Clear all registered backends. For testing only."""
    _backend_registry.clear()
```

- [ ] **Step 2: Update storage_facade/facade.py**

In `src/mountainash_utils_files/storage_facade/facade.py`:

1. Add auth import at the top:
   ```python
   from mountainash_auth_client import AuthMode
   ```

2. Add `StorageProfile` TYPE_CHECKING import:
   ```python
   if typing.TYPE_CHECKING:
       from mountainash_utils_files.settings.profile import StorageProfile
   ```

3. Update `__init__` (lines 71-83):
   ```python
       def __init__(
           self,
           provider_type: CONST_STORAGE_PROVIDER_TYPE,
           profile: "StorageProfile | None" = None,
           *,
           auth: AuthMode | None = None,
       ) -> None:
           self._backend = get_storage_backend(provider_type, profile, auth=auth)
   ```

4. Update `for_local` (line 92):
   ```python
       @classmethod
       def for_local(cls) -> StorageFacade:
           """Return a StorageFacade backed by the local filesystem."""
           return cls(CONST_STORAGE_PROVIDER_TYPE.LOCAL, profile=None)
   ```

5. Update `from_path` (lines 95-120):
   ```python
       @classmethod
       def from_path(
           cls,
           path: str,
           profile: "StorageProfile | None" = None,
           *,
           auth: AuthMode | None = None,
       ) -> StorageFacade:
           """Construct a facade whose provider is inferred from a path's URL scheme."""
           provider = detect_provider_from_path(path)
           return cls(provider_type=provider, profile=profile, auth=auth)
   ```

- [ ] **Step 3: Update storage_facade/read_bytes.py**

In `src/mountainash_utils_files/storage_facade/read_bytes.py`:

1. Add imports:
   ```python
   from mountainash_auth_client import AuthMode
   ```

2. Update function signature:
   ```python
   def read_bytes(
       path: str,
       profile: typing.Any = None,
       *,
       auth: AuthMode | None = None,
       infer: bool = False,
       gpg: GPG | None = None,
       gzip: Gzip | None = None,
   ) -> bytes:
   ```

3. Update the facade construction call:
   ```python
       facade = StorageFacade.from_path(path, profile, auth=auth)
   ```

- [ ] **Step 4: Update __init__.py**

In `src/mountainash_utils_files/__init__.py`, update the `storage()` function:

```python
def storage(provider_type: CONST_STORAGE_PROVIDER_TYPE = CONST_STORAGE_PROVIDER_TYPE.LOCAL,
            profile=None, *, auth=None) -> StorageFacade:
    """Convenience factory for creating a StorageFacade."""
    return StorageFacade(provider_type, profile, auth=auth)
```

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/storage_registry/registry.py \
        src/mountainash_utils_files/storage_facade/facade.py \
        src/mountainash_utils_files/storage_facade/read_bytes.py \
        src/mountainash_utils_files/__init__.py
git commit -m "refactor: rename auth_params to profile, type with AuthMode throughout

Facade, registry, read_bytes(), and storage() now accept
profile: StorageProfile | None and auth: AuthMode | None.
Removed _accepts_auth() introspection and hasattr guard."
```

---

### Task 7: Update all 3 backend __init__ signatures

**Files:**
- Modify: `src/mountainash_utils_files/storage_backends/s3/__init__.py`
- Modify: `src/mountainash_utils_files/storage_backends/s3/s3_connection.py`
- Modify: `src/mountainash_utils_files/storage_backends/local/__init__.py`
- Modify: `src/mountainash_utils_files/storage_backends/http/__init__.py`

- [ ] **Step 1: Update S3 backend __init__**

In `src/mountainash_utils_files/storage_backends/s3/__init__.py`, update the `__init__`:

```python
    def __init__(self, profile=None, *, auth=None) -> None:
        self.auth_params = profile
        self.auth = auth
        self._client: t.Any = None
```

Note: We keep `self.auth_params` internally for now so the connection mixin doesn't need a full rewrite. The external API changes from `S3StorageBackend(auth_params)` to `S3StorageBackend(profile, auth=auth)`.

- [ ] **Step 2: Update S3 connection mixin**

In `src/mountainash_utils_files/storage_backends/s3/s3_connection.py`, update `_resolve_kwargs()` to pass auth through Shape 1:

Change line 71 from:
```python
            kwargs = auth_params.to_handler_kwargs()
```
to:
```python
            kwargs = auth_params.to_handler_kwargs(auth=getattr(self, "auth", None))
```

- [ ] **Step 3: Update Local backend __init__**

In `src/mountainash_utils_files/storage_backends/local/__init__.py`, update:

```python
    def __init__(self, profile=None, *, auth=None) -> None:
        self.auth_params = profile
```

Local backend ignores auth entirely.

- [ ] **Step 4: Update HTTP backend __init__ and _get_client()**

In `src/mountainash_utils_files/storage_backends/http/__init__.py`:

1. Update `__init__` (line 62):
   ```python
       def __init__(self, profile=None, *, auth=None) -> None:
           self.auth_params = profile
           self.auth = auth
           self._client: httpx.Client | None = None
   ```

2. Simplify `_get_client()` — remove the dual auth path. All auth handling now goes through the adapter via `to_handler_kwargs(auth=)`:

   ```python
       def _get_client(self) -> httpx.Client:
           if self._client is None:
               kwargs: dict[str, t.Any] = {}
               if hasattr(self.auth_params, "to_handler_kwargs"):
                   kwargs = self.auth_params.to_handler_kwargs(auth=self.auth)
               self._client = httpx.Client(**kwargs)
           return self._client
   ```

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/storage_backends/
git commit -m "refactor: update backend __init__ signatures for profile + auth separation

All backends accept (profile, *, auth=None). S3 connection mixin
forwards auth through to_handler_kwargs(). HTTP backend dual-auth
path replaced with single adapter-driven path."
```

---

### Task 8: Create load_storage() convenience

**Files:**
- Create: `src/mountainash_utils_files/settings/loader.py`

- [ ] **Step 1: Create loader.py**

Create `src/mountainash_utils_files/settings/loader.py`:

```python
"""Config-driven storage + auth materialisation.

Application-layer convenience that creates SettingsParameters for both
the storage profile and the auth mode, calls get_settings(), and returns
materialised instances. The facade and backends never see
SettingsParameters — they receive materialised Profile instances.
"""

from __future__ import annotations

from mountainash_auth_client import AUTH_REGISTRY, AuthMode, CONST_AUTH_MODE
from mountainash_settings import SettingsParameters, get_settings

from .profile import StorageProfile
from .registry import STORAGE_REGISTRY

__all__ = ["load_storage"]


def load_storage(
    provider: str,
    *,
    config_file: str | None = None,
    secrets_provider: str | None = None,
    auth_mode: CONST_AUTH_MODE | None = None,
) -> tuple[StorageProfile, AuthMode]:
    """Materialise a storage profile and auth instance from config.

    Args:
        provider: Storage provider name (e.g. ``"s3"``, ``"gcs"``).
        config_file: Path to a YAML/TOML config file. Both the profile
            and auth classes load from the same file (each picks its own
            fields via ``extra="ignore"``).
        secrets_provider: Secrets provider name for secret resolution.
        auth_mode: Override the provider's default auth mode.

    Returns:
        A ``(profile, auth)`` tuple of materialised settings instances.

    Raises:
        ValueError: If *auth_mode* is not in the provider's
            ``supported_auth`` set.
    """
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

- [ ] **Step 2: Export from settings/__init__.py**

Add `load_storage` to `src/mountainash_utils_files/settings/__init__.py`:

```python
from .loader import load_storage
```

And add `"load_storage"` to the `__all__` list.

- [ ] **Step 3: Commit**

```bash
git add src/mountainash_utils_files/settings/loader.py \
        src/mountainash_utils_files/settings/__init__.py
git commit -m "feat: add load_storage() for config-driven profile + auth materialisation"
```

---

### Task 9: Update tests

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/facade/test_facade.py`
- Modify: `tests/storage_facade/test_read_bytes.py`
- Modify: `tests/storage_facade/test_from_path.py`
- Modify: `tests/backends/test_http.py`
- Modify: `tests/backends/test_s3.py`
- Modify: `tests/backends/test_local.py`
- Modify: `tests/test_registry.py`
- Modify: `tests/test_unit/settings/test_profile.py`
- Modify: `tests/test_unit/settings/test_registry.py`
- Modify: `tests/test_unit/settings/test_descriptor_invariants.py`
- Modify: `tests/test_unit/backends/test_http_backend.py`
- Modify: All provider test files under `tests/test_unit/settings/providers/`
- Modify: `tests/test_constants_and_exceptions.py`

- [ ] **Step 1: Update conftest.py**

In `tests/conftest.py`, update the `local_facade` fixture from:
```python
StorageFacade(CONST_STORAGE_PROVIDER_TYPE.LOCAL, auth_params=None)
```
to:
```python
StorageFacade(CONST_STORAGE_PROVIDER_TYPE.LOCAL, profile=None)
```

- [ ] **Step 2: Bulk-rename auth_params → profile in test files**

Run a targeted find-and-replace across all test files. For each test file that references `auth_params`:

```bash
grep -rn "auth_params" tests/
```

Replace all `auth_params=` with `profile=` in test call sites. The most common patterns:

- `StorageFacade(provider, auth_params=...)` → `StorageFacade(provider, profile=...)`
- `get_storage_backend(provider, auth_params)` → `get_storage_backend(provider, profile)`
- `SomeBackend(auth_params=...)` → `SomeBackend(profile=..., auth=...)`

- [ ] **Step 3: Update test_constants_and_exceptions.py**

Remove tests that reference `CONST_STORAGE_AUTH_METHOD`.

- [ ] **Step 4: Update provider settings tests**

In each `tests/test_unit/settings/providers/test_*_settings.py`:

- Remove any references to `auth_modes` on specs
- Remove any tests that construct `StorageAuthBase` directly
- Update any tests that check `profile.auth` (no longer exists)
- Add tests verifying `spec.default_auth` and `spec.supported_auth`

- [ ] **Step 5: Update test_profile.py**

In `tests/test_unit/settings/test_profile.py`:

- Update `to_handler_kwargs()` tests to pass `auth=` parameter
- Remove any tests checking for the nested `auth` field on profiles

- [ ] **Step 6: Update HTTP backend tests**

In `tests/test_unit/backends/test_http_backend.py`:

- Update backend construction from `HTTPStorageBackend(auth_params=..., auth=...)` to `HTTPStorageBackend(profile=..., auth=...)`
- Replace any `type(auth).__name__` assertions with isinstance checks

- [ ] **Step 7: Run full test suite**

```bash
hatch run test:test -v 2>&1 | tail -30
```

Expected: All tests pass.

- [ ] **Step 8: Run lint**

```bash
hatch run ruff:check
```

Expected: Clean.

- [ ] **Step 9: Commit**

```bash
git add tests/
git commit -m "test: update all tests for auth separation

Renamed auth_params to profile at all call sites. Removed
StorageAuthBase and CONST_STORAGE_AUTH_METHOD test references.
Updated provider settings tests for default_auth/supported_auth."
```

---

### Task 10: Update providers/__init__.py exports

**Files:**
- Modify: `src/mountainash_utils_files/settings/providers/__init__.py`

- [ ] **Step 1: Remove StorageAuthBase references from providers __init__**

In `src/mountainash_utils_files/settings/providers/__init__.py`, remove any `StorageAuthBase` imports or re-exports. Keep all provider class exports and descriptor exports. Update any deprecated name mappings that reference `auth_modes`.

- [ ] **Step 2: Run full lint + test**

```bash
hatch run ruff:check && hatch run test:test -v 2>&1 | tail -10
```

Expected: Clean lint, all tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/mountainash_utils_files/settings/providers/__init__.py
git commit -m "chore: clean up providers __init__ exports after StorageAuthBase removal"
```
