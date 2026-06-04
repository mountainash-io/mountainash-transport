# Auth-Client Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate all auth type imports from the defunct `mountainash_settings.auth` to `mountainash_auth_client`, fix the HTTP backend to use auth configuration, and add a new `auth=AuthSpec` parameter for direct auth-client integration.

**Architecture:** Three layered changes: (1) mechanical import migration across 9 provider files + 12 test files + 2 commented stubs, (2) HTTP backend wired to profile kwargs, (3) new `auth=` parameter threaded from `read_bytes()` → `StorageFacade` → registry → `HTTPStorageBackend` with `inspect.signature`-based forwarding and auth-header-level precedence.

**Tech Stack:** Python 3.12, mountainash-auth-client (pydantic-based AuthSpec types), httpx, pytest

**Spec:** `docs/superpowers/specs/2026-06-04-auth-client-integration-design.md`

---

### Task 1: Add mountainash-auth-client Dependency

**Files:**
- Modify: `pyproject.toml:25-47` (core dependencies)
- Modify: `hatch.toml` (test, default, build_github, test_github environments)

- [ ] **Step 1: Add core dependency to pyproject.toml**

In `pyproject.toml`, add `mountainash-auth-client` to the `dependencies` list after `httpx`:

```python
    "httpx>=0.27",
    "mountainash-auth-client>=26.5.0",
]
```

- [ ] **Step 2: Add to hatch.toml test environment**

In `hatch.toml` under `[envs.test]` dependencies, add alongside the other mountainash local-path deps:

```toml
    "mountainash_auth_client @ {root:uri}/../mountainash-auth-client",
```

- [ ] **Step 3: Add to hatch.toml default environment**

In `hatch.toml` under `[envs.default]`, uncomment and add:

```toml
    "mountainash_auth_client @ {root:uri}/../mountainash-auth-client",
```

- [ ] **Step 4: Add to hatch.toml build_github environment**

In `hatch.toml` under `[envs.build_github]` dependencies, add:

```toml
    "mountainash_auth_client @ {root:uri}/temp/mountainash-auth-client",
```

- [ ] **Step 5: Add to hatch.toml test_github environment (if it has its own deps)**

Check if `[envs.test_github]` has its own `dependencies` list. If so, add the same line as the test environment. If it inherits from test, no change needed.

- [ ] **Step 6: Recreate the test venv and verify auth-client is importable**

Run:
```bash
hatch env remove test && hatch run test:python -c "from mountainash_auth_client import NoAuth, TokenAuth, AuthSpec; print('OK')"
```
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml hatch.toml
git commit -m "build: add mountainash-auth-client as core dependency"
```

---

### Task 2: Migrate Provider Settings Imports (9 files)

**Files:**
- Modify: `src/mountainash_utils_files/settings/providers/s3_settings.py:19`
- Modify: `src/mountainash_utils_files/settings/providers/gcs_settings.py:16`
- Modify: `src/mountainash_utils_files/settings/providers/azure_settings.py:23`
- Modify: `src/mountainash_utils_files/settings/providers/ssh_settings.py:21`
- Modify: `src/mountainash_utils_files/settings/providers/ftp_settings.py:16`
- Modify: `src/mountainash_utils_files/settings/providers/smb_settings.py:27`
- Modify: `src/mountainash_utils_files/settings/providers/local_settings.py:31`
- Modify: `src/mountainash_utils_files/settings/providers/github_settings.py:25`
- Modify: `src/mountainash_utils_files/settings/providers/http_settings.py:10`

Each file gets one import line changed. The rule is:

```python
# Before
from mountainash_settings.auth import X, Y, Z

# After
from mountainash_auth_client import X, Y, Z
```

- [ ] **Step 1: Apply the import change to all 9 files**

The exact replacements:

| File | Old | New |
|------|-----|-----|
| `s3_settings.py:19` | `from mountainash_settings.auth import IAMAuth, NoAuth, TokenAuth` | `from mountainash_auth_client import IAMAuth, NoAuth, TokenAuth` |
| `gcs_settings.py:16` | `from mountainash_settings.auth import (` ... `)` | `from mountainash_auth_client import (` ... `)` |
| `azure_settings.py:23` | `from mountainash_settings.auth import (` ... `)` | `from mountainash_auth_client import (` ... `)` |
| `ssh_settings.py:21` | `from mountainash_settings.auth import CertificateAuth, KerberosAuth, PasswordAuth` | `from mountainash_auth_client import CertificateAuth, KerberosAuth, PasswordAuth` |
| `ftp_settings.py:16` | `from mountainash_settings.auth import NoAuth, PasswordAuth` | `from mountainash_auth_client import NoAuth, PasswordAuth` |
| `smb_settings.py:27` | `from mountainash_settings.auth import KerberosAuth, PasswordAuth` | `from mountainash_auth_client import KerberosAuth, PasswordAuth` |
| `local_settings.py:31` | `from mountainash_settings.auth import NoAuth` | `from mountainash_auth_client import NoAuth` |
| `github_settings.py:25` | `from mountainash_settings.auth import JWTAuth, NoAuth, OAuth2Auth, TokenAuth` | `from mountainash_auth_client import JWTAuth, NoAuth, OAuth2Auth, TokenAuth` |
| `http_settings.py:10` | `from mountainash_settings.auth import NoAuth, PasswordAuth, TokenAuth` | `from mountainash_auth_client import NoAuth, PasswordAuth, TokenAuth` |

- [ ] **Step 2: Verify all 9 provider modules import cleanly**

Run:
```bash
hatch run test:python -c "
from mountainash_utils_files.settings.providers.s3_settings import S3Settings
from mountainash_utils_files.settings.providers.gcs_settings import GCSSettings
from mountainash_utils_files.settings.providers.azure_settings import AzureStorageSettings
from mountainash_utils_files.settings.providers.ssh_settings import SSHSettings
from mountainash_utils_files.settings.providers.ftp_settings import FTPSettings
from mountainash_utils_files.settings.providers.smb_settings import SMBSettings
from mountainash_utils_files.settings.providers.local_settings import LocalSettings
from mountainash_utils_files.settings.providers.github_settings import GitHubRepoSettings
from mountainash_utils_files.settings.providers.http_settings import HTTPSettings
print('All 9 provider settings imported OK')
"
```
Expected: `All 9 provider settings imported OK`

- [ ] **Step 3: Commit**

```bash
git add src/mountainash_utils_files/settings/providers/
git commit -m "fix: migrate auth imports from mountainash_settings.auth to mountainash_auth_client"
```

---

### Task 3: Migrate Test + Utility Imports (14 files)

**Files:**
- Modify: `tests/test_unit/settings/providers/test_http_settings.py:6`
- Modify: `tests/test_unit/settings/providers/test_azure_settings.py:9`
- Modify: `tests/test_unit/settings/providers/test_gcs_settings.py:7`
- Modify: `tests/test_unit/settings/providers/test_github_settings.py:7`
- Modify: `tests/test_unit/settings/providers/test_local_settings.py:7`
- Modify: `tests/test_unit/settings/providers/test_s3_settings.py:12`
- Modify: `tests/test_unit/settings/providers/test_smb_settings.py:7`
- Modify: `tests/test_unit/settings/providers/test_ssh_settings.py:7`
- Modify: `tests/test_unit/settings/providers/test_ftp_settings.py:7`
- Modify: `tests/test_unit/settings/test_profile.py:12`
- Modify: `tests/test_unit/settings/test_registry.py:124,153`
- Modify: `src/mountainash_utils_files/settings/utils/connection.py:10`
- Modify: `src/mountainash_utils_files/settings/utils/validation.py:10`

Same mechanical change as Task 2.

- [ ] **Step 1: Apply import change to all test files**

The exact replacements:

| File | Old | New |
|------|-----|-----|
| `test_http_settings.py:6` | `from mountainash_settings.auth import NoAuth, PasswordAuth, TokenAuth` | `from mountainash_auth_client import NoAuth, PasswordAuth, TokenAuth` |
| `test_azure_settings.py:9` | `from mountainash_settings.auth import AzureADAuth, NoAuth, PasswordAuth, TokenAuth` | `from mountainash_auth_client import AzureADAuth, NoAuth, PasswordAuth, TokenAuth` |
| `test_gcs_settings.py:7` | `from mountainash_settings.auth import NoAuth, TokenAuth` | `from mountainash_auth_client import NoAuth, TokenAuth` |
| `test_github_settings.py:7` | `from mountainash_settings.auth import JWTAuth, NoAuth, OAuth2Auth, TokenAuth` | `from mountainash_auth_client import JWTAuth, NoAuth, OAuth2Auth, TokenAuth` |
| `test_local_settings.py:7` | `from mountainash_settings.auth import NoAuth` | `from mountainash_auth_client import NoAuth` |
| `test_s3_settings.py:12` | `from mountainash_settings.auth import IAMAuth, NoAuth` | `from mountainash_auth_client import IAMAuth, NoAuth` |
| `test_smb_settings.py:7` | `from mountainash_settings.auth import KerberosAuth, PasswordAuth` | `from mountainash_auth_client import KerberosAuth, PasswordAuth` |
| `test_ssh_settings.py:7` | `from mountainash_settings.auth import CertificateAuth, KerberosAuth, PasswordAuth` | `from mountainash_auth_client import CertificateAuth, KerberosAuth, PasswordAuth` |
| `test_ftp_settings.py:7` | `from mountainash_settings.auth import NoAuth, PasswordAuth` | `from mountainash_auth_client import NoAuth, PasswordAuth` |
| `test_profile.py:12` | `from mountainash_settings.auth import NoAuth, TokenAuth` | `from mountainash_auth_client import NoAuth, TokenAuth` |
| `test_registry.py:124` | `from mountainash_settings.auth import NoAuth` | `from mountainash_auth_client import NoAuth` |
| `test_registry.py:153` | `from mountainash_settings.auth import NoAuth` | `from mountainash_auth_client import NoAuth` |

- [ ] **Step 2: Update commented-out imports in utility stubs**

In `src/mountainash_utils_files/settings/utils/connection.py:10`, change:
```python
# from mountainash_settings.auth.storage.exceptions import (
```
to:
```python
# from mountainash_auth_client import (  # storage exceptions TBD
```

In `src/mountainash_utils_files/settings/utils/validation.py:10`, change:
```python
# from mountainash_settings.auth.storage.exceptions import StorageValidationError
```
to:
```python
# from mountainash_auth_client import StorageValidationError  # TBD
```

These are dead code (fully commented out), but updating prevents confusion.

- [ ] **Step 3: Run all settings tests to verify migration**

Run:
```bash
hatch run test:test tests/test_unit/settings/ -v
```
Expected: All tests PASS (no more `ModuleNotFoundError`).

- [ ] **Step 4: Verify no residual mountainash_settings.auth imports remain**

Run:
```bash
grep -rn "from mountainash_settings.auth" src/ tests/ --include="*.py"
```
Expected: No output (zero matches), or only the updated comments.

- [ ] **Step 5: Commit**

```bash
git add tests/test_unit/settings/ src/mountainash_utils_files/settings/utils/
git commit -m "fix: migrate test + utility auth imports to mountainash_auth_client"
```

---

### Task 4: Fix HTTP Backend to Use Profile kwargs

**Files:**
- Modify: `src/mountainash_utils_files/storage_backends/http/__init__.py:62-69`
- Test: `tests/test_unit/backends/test_http_backend.py` (create)

- [ ] **Step 1: Write the failing test for profile-based client creation**

Create `tests/test_unit/backends/test_http_backend.py`:

```python
"""Tests for HTTPStorageBackend — auth and profile integration."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import httpx
import pytest

from mountainash_utils_files.storage_backends.http import HTTPStorageBackend


@pytest.mark.unit
class TestHTTPBackendClientCreation:
    def test_bare_client_when_no_auth_params(self):
        """No auth_params → bare httpx.Client()."""
        backend = HTTPStorageBackend(auth_params=None)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock(spec=httpx.Client)
            backend._get_client()
            mock_client.assert_called_once_with()

    def test_profile_kwargs_forwarded_to_client(self):
        """auth_params with to_handler_kwargs() → kwargs forwarded to httpx.Client."""
        profile = MagicMock()
        expected_kwargs = {
            "timeout": httpx.Timeout(connect=5.0, read=15.0, write=60.0, pool=5.0),
            "follow_redirects": True,
            "max_redirects": 10,
            "verify": True,
            "headers": {"Authorization": "Bearer tok123"},
        }
        profile.to_handler_kwargs.return_value = expected_kwargs

        backend = HTTPStorageBackend(auth_params=profile)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock(spec=httpx.Client)
            backend._get_client()
            mock_client.assert_called_once_with(**expected_kwargs)

    def test_client_cached_after_first_call(self):
        """_get_client() returns the same client on repeated calls."""
        backend = HTTPStorageBackend(auth_params=None)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock(spec=httpx.Client)
            c1 = backend._get_client()
            c2 = backend._get_client()
            assert c1 is c2
            mock_client.assert_called_once()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
hatch run test:test tests/test_unit/backends/test_http_backend.py -v
```
Expected: `test_profile_kwargs_forwarded_to_client` FAILS (profile kwargs not used).

- [ ] **Step 3: Implement profile-aware _get_client()**

In `src/mountainash_utils_files/storage_backends/http/__init__.py`, replace lines 66-69:

```python
    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client()
        return self._client
```

with:

```python
    def _get_client(self) -> httpx.Client:
        if self._client is None:
            kwargs: dict[str, t.Any] = {}
            if hasattr(self.auth_params, "to_handler_kwargs"):
                kwargs = self.auth_params.to_handler_kwargs()
            self._client = httpx.Client(**kwargs)
        return self._client
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
hatch run test:test tests/test_unit/backends/test_http_backend.py -v
```
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/storage_backends/http/__init__.py tests/test_unit/backends/test_http_backend.py
git commit -m "fix: HTTP backend now uses profile kwargs for httpx.Client"
```

---

### Task 5: Extend _resolve_auth_headers for OAuth2 Types

**Files:**
- Modify: `src/mountainash_utils_files/settings/adapters/http.py:23-37`
- Modify: `tests/test_unit/settings/providers/test_http_settings.py` (add tests)

- [ ] **Step 1: Write failing tests for OAuth2 auth header mapping**

Append to `tests/test_unit/settings/providers/test_http_settings.py`:

```python
@pytest.mark.unit
class TestResolveAuthHeaders:
    """Direct tests for _resolve_auth_headers — covers OAuth2 types."""

    def test_noauth_returns_empty(self):
        from mountainash_utils_files.settings.adapters.http import _resolve_auth_headers
        from mountainash_auth_client import NoAuth
        assert _resolve_auth_headers(NoAuth()) == {}

    def test_oauth2_with_token(self):
        from mountainash_utils_files.settings.adapters.http import _resolve_auth_headers
        from mountainash_auth_client import OAuth2Auth
        auth = OAuth2Auth(token=SecretStr("oauthtoken"))
        assert _resolve_auth_headers(auth) == {"Authorization": "Bearer oauthtoken"}

    def test_oauth2_without_token(self):
        from mountainash_utils_files.settings.adapters.http import _resolve_auth_headers
        from mountainash_auth_client import OAuth2Auth
        auth = OAuth2Auth(client_id="id", client_secret=SecretStr("secret"))
        assert _resolve_auth_headers(auth) == {}

    def test_oauth2_authcode_with_access_token(self):
        from mountainash_utils_files.settings.adapters.http import _resolve_auth_headers
        from mountainash_auth_client import OAuth2AuthCodeAuth
        auth = OAuth2AuthCodeAuth(
            client_id="id",
            client_secret=SecretStr("secret"),
            access_token=SecretStr("myaccess"),
        )
        assert _resolve_auth_headers(auth) == {"Authorization": "Bearer myaccess"}

    def test_oauth2_authcode_without_access_token(self):
        from mountainash_utils_files.settings.adapters.http import _resolve_auth_headers
        from mountainash_auth_client import OAuth2AuthCodeAuth
        auth = OAuth2AuthCodeAuth(
            client_id="id",
            client_secret=SecretStr("secret"),
        )
        assert _resolve_auth_headers(auth) == {}

    def test_none_returns_empty(self):
        from mountainash_utils_files.settings.adapters.http import _resolve_auth_headers
        assert _resolve_auth_headers(None) == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
hatch run test:test tests/test_unit/settings/providers/test_http_settings.py::TestResolveAuthHeaders -v
```
Expected: OAuth2 tests FAIL (not handled in `_resolve_auth_headers`).

- [ ] **Step 3: Extend _resolve_auth_headers**

In `src/mountainash_utils_files/settings/adapters/http.py`, replace `_resolve_auth_headers`:

```python
def _resolve_auth_headers(auth: t.Any) -> dict[str, str]:
    """Build Authorization header from an AuthSpec instance."""
    if auth is None:
        return {}
    auth_type = type(auth).__name__
    if auth_type == "NoAuth":
        return {}
    if auth_type == "TokenAuth" or auth_type == "JWTAuth":
        token = _unwrap_secret(getattr(auth, "token", None))
        if token:
            return {"Authorization": f"Bearer {token}"}
    elif auth_type == "PasswordAuth":
        username = getattr(auth, "username", None) or ""
        password = _unwrap_secret(getattr(auth, "password", None)) or ""
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}
    elif auth_type == "OAuth2Auth":
        token = _unwrap_secret(getattr(auth, "token", None))
        if token:
            return {"Authorization": f"Bearer {token}"}
    elif auth_type == "OAuth2AuthCodeAuth":
        token = _unwrap_secret(getattr(auth, "access_token", None))
        if token:
            return {"Authorization": f"Bearer {token}"}
    return {}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
hatch run test:test tests/test_unit/settings/providers/test_http_settings.py -v
```
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/settings/adapters/http.py tests/test_unit/settings/providers/test_http_settings.py
git commit -m "feat: extend _resolve_auth_headers for OAuth2 and OAuth2AuthCode types"
```

---

### Task 6: Add auth= Parameter to Storage Registry

**Files:**
- Modify: `src/mountainash_utils_files/storage_registry/registry.py:18-23`
- Test: `tests/test_unit/backends/test_http_backend.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_unit/backends/test_http_backend.py`:

```python
from mountainash_utils_files.storage_registry.registry import get_storage_backend
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE


@pytest.mark.unit
class TestRegistryAuthForwarding:
    def test_auth_forwarded_to_http_backend(self):
        """get_storage_backend forwards auth= to HTTPStorageBackend."""
        from mountainash_auth_client import TokenAuth
        from pydantic import SecretStr

        auth = TokenAuth(token=SecretStr("tok"))
        backend = get_storage_backend(
            CONST_STORAGE_PROVIDER_TYPE.HTTP, auth_params=None, auth=auth,
        )
        assert backend.auth is auth

    def test_auth_ignored_for_backend_without_auth_param(self):
        """get_storage_backend does not pass auth= to backends that don't accept it."""
        from mountainash_auth_client import TokenAuth
        from pydantic import SecretStr

        auth = TokenAuth(token=SecretStr("tok"))
        # S3 backend's __init__ does not accept auth= — should not raise.
        backend = get_storage_backend(
            CONST_STORAGE_PROVIDER_TYPE.S3, auth_params=None, auth=auth,
        )
        assert not hasattr(backend, "auth") or backend.auth is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
hatch run test:test tests/test_unit/backends/test_http_backend.py::TestRegistryAuthForwarding -v
```
Expected: FAIL — `get_storage_backend` doesn't accept `auth` kwarg.

- [ ] **Step 3: Implement auth forwarding in the registry**

Replace `src/mountainash_utils_files/storage_registry/registry.py`:

```python
# storage_registry/registry.py

import inspect
import typing as t

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE

_backend_registry: dict[CONST_STORAGE_PROVIDER_TYPE, type] = {}


def register_storage_backend(provider_type: CONST_STORAGE_PROVIDER_TYPE) -> t.Callable[[type], type]:
    """Decorator that registers a backend class for a provider type."""
    def decorator(cls: type) -> type:
        _backend_registry[provider_type] = cls
        return cls
    return decorator


def _accepts_auth(cls: type) -> bool:
    """Check if a backend class's __init__ accepts an 'auth' parameter."""
    try:
        sig = inspect.signature(cls.__init__)
        return "auth" in sig.parameters
    except (ValueError, TypeError):
        return False


def get_storage_backend(
    provider_type: CONST_STORAGE_PROVIDER_TYPE,
    auth_params: t.Any,
    *,
    auth: t.Any = None,
) -> t.Any:
    """Instantiate and return a backend for the given provider type."""
    cls = _backend_registry.get(provider_type)
    if cls is None:
        raise ValueError(f"No backend registered for {provider_type!r}")
    if auth is not None and _accepts_auth(cls):
        return cls(auth_params, auth=auth)
    return cls(auth_params)


def get_registered_backends() -> dict[CONST_STORAGE_PROVIDER_TYPE, type]:
    """Return a copy of all registered backends."""
    return dict(_backend_registry)


def clear_registry() -> None:
    """Clear all registered backends. For testing only."""
    _backend_registry.clear()
```

- [ ] **Step 4: Add auth parameter to HTTPStorageBackend.__init__**

In `src/mountainash_utils_files/storage_backends/http/__init__.py`, change:

```python
    def __init__(self, auth_params: t.Any) -> None:
        self.auth_params = auth_params
        self._client: httpx.Client | None = None
```

to:

```python
    def __init__(self, auth_params: t.Any, *, auth: t.Any = None) -> None:
        self.auth_params = auth_params
        self.auth = auth
        self._client: httpx.Client | None = None
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:
```bash
hatch run test:test tests/test_unit/backends/test_http_backend.py -v
```
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_utils_files/storage_registry/registry.py src/mountainash_utils_files/storage_backends/http/__init__.py
git commit -m "feat: registry forwards auth= to backends that accept it"
```

---

### Task 7: Wire auth= Through HTTPStorageBackend._get_client()

**Files:**
- Modify: `src/mountainash_utils_files/storage_backends/http/__init__.py:66-72`
- Test: `tests/test_unit/backends/test_http_backend.py` (extend)

- [ ] **Step 1: Write the failing tests for auth-header-level precedence**

Append to `tests/test_unit/backends/test_http_backend.py`:

```python
from mountainash_auth_client import NoAuth, TokenAuth, PasswordAuth, OAuth2Auth
from pydantic import SecretStr


@pytest.mark.unit
class TestHTTPBackendAuthPrecedence:
    def test_direct_auth_creates_headers(self):
        """auth= without profile → client gets auth headers only."""
        auth = TokenAuth(token=SecretStr("direct"))
        backend = HTTPStorageBackend(auth_params=None, auth=auth)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock(spec=httpx.Client)
            backend._get_client()
            call_kwargs = mock_client.call_args[1]
            assert call_kwargs["headers"]["Authorization"] == "Bearer direct"

    def test_auth_overrides_profile_auth_header(self):
        """auth= overrides profile Authorization header but preserves other config."""
        profile = MagicMock()
        profile.to_handler_kwargs.return_value = {
            "timeout": httpx.Timeout(connect=5.0, read=15.0, write=60.0, pool=5.0),
            "follow_redirects": True,
            "verify": True,
            "headers": {"Authorization": "Bearer old", "X-Custom": "keep"},
        }
        auth = TokenAuth(token=SecretStr("new"))
        backend = HTTPStorageBackend(auth_params=profile, auth=auth)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock(spec=httpx.Client)
            backend._get_client()
            call_kwargs = mock_client.call_args[1]
            assert call_kwargs["headers"]["Authorization"] == "Bearer new"
            assert call_kwargs["headers"]["X-Custom"] == "keep"
            assert "timeout" in call_kwargs

    def test_noauth_strips_profile_authorization(self):
        """auth=NoAuth() removes Authorization header from profile."""
        profile = MagicMock()
        profile.to_handler_kwargs.return_value = {
            "headers": {"Authorization": "Bearer fromprofile", "X-Custom": "keep"},
        }
        backend = HTTPStorageBackend(auth_params=profile, auth=NoAuth())
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock(spec=httpx.Client)
            backend._get_client()
            call_kwargs = mock_client.call_args[1]
            assert "Authorization" not in call_kwargs.get("headers", {})
            assert call_kwargs["headers"]["X-Custom"] == "keep"

    def test_profile_only_no_auth(self):
        """auth_params only (no auth=) → profile kwargs used as-is."""
        profile = MagicMock()
        profile.to_handler_kwargs.return_value = {
            "headers": {"Authorization": "Bearer profonly"},
        }
        backend = HTTPStorageBackend(auth_params=profile)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock(spec=httpx.Client)
            backend._get_client()
            call_kwargs = mock_client.call_args[1]
            assert call_kwargs["headers"]["Authorization"] == "Bearer profonly"

    def test_password_auth_direct(self):
        """auth=PasswordAuth → Basic header."""
        import base64
        auth = PasswordAuth(username="user", password=SecretStr("pass"))
        backend = HTTPStorageBackend(auth_params=None, auth=auth)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            mock_client.return_value = MagicMock(spec=httpx.Client)
            backend._get_client()
            call_kwargs = mock_client.call_args[1]
            expected = "Basic " + base64.b64encode(b"user:pass").decode()
            assert call_kwargs["headers"]["Authorization"] == expected
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
hatch run test:test tests/test_unit/backends/test_http_backend.py::TestHTTPBackendAuthPrecedence -v
```
Expected: FAIL — `_get_client()` doesn't use `self.auth`.

- [ ] **Step 3: Implement auth-header-level precedence in _get_client()**

In `src/mountainash_utils_files/storage_backends/http/__init__.py`, replace `_get_client()` with:

```python
    def _get_client(self) -> httpx.Client:
        if self._client is None:
            kwargs: dict[str, t.Any] = {}

            # Start from profile kwargs if available.
            if hasattr(self.auth_params, "to_handler_kwargs"):
                kwargs = self.auth_params.to_handler_kwargs()

            # Override auth headers if direct auth= is provided.
            if self.auth is not None:
                from mountainash_utils_files.settings.adapters.http import (
                    _resolve_auth_headers,
                )

                auth_headers = _resolve_auth_headers(self.auth)
                existing_headers = dict(kwargs.get("headers", {}))
                # NoAuth: strip Authorization; others: override it.
                if type(self.auth).__name__ == "NoAuth":
                    existing_headers.pop("Authorization", None)
                else:
                    existing_headers.update(auth_headers)
                if existing_headers:
                    kwargs["headers"] = existing_headers
                elif "headers" in kwargs:
                    del kwargs["headers"]

            self._client = httpx.Client(**kwargs)
        return self._client
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
hatch run test:test tests/test_unit/backends/test_http_backend.py -v
```
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/storage_backends/http/__init__.py tests/test_unit/backends/test_http_backend.py
git commit -m "feat: HTTP backend auth-header-level precedence for auth= vs profile"
```

---

### Task 8: Thread auth= Through StorageFacade and read_bytes()

**Files:**
- Modify: `src/mountainash_utils_files/storage_facade/facade.py:71-106`
- Modify: `src/mountainash_utils_files/storage_facade/read_bytes.py`
- Modify: `src/mountainash_utils_files/__init__.py:54-57` (storage() convenience)
- Test: `tests/test_unit/backends/test_http_backend.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_unit/backends/test_http_backend.py`:

```python
from mountainash_utils_files.storage_facade.facade import StorageFacade
from mountainash_utils_files.storage_facade.read_bytes import read_bytes as _read_bytes


@pytest.mark.unit
class TestFacadeAuthParam:
    def test_from_path_passes_auth_to_backend(self):
        """StorageFacade.from_path(auth=...) forwards to HTTPStorageBackend."""
        auth = TokenAuth(token=SecretStr("facadetok"))
        facade = StorageFacade.from_path("https://example.com/file.txt", auth=auth)
        assert facade._backend.auth is auth

    def test_from_path_without_auth(self):
        """StorageFacade.from_path() without auth= → backend.auth is None."""
        facade = StorageFacade.from_path("https://example.com/file.txt")
        assert facade._backend.auth is None

    def test_non_http_provider_with_auth_raises(self):
        """auth= with a non-HTTP provider raises ValueError."""
        auth = TokenAuth(token=SecretStr("tok"))
        with pytest.raises(ValueError, match="auth= is not supported"):
            StorageFacade(
                provider_type=CONST_STORAGE_PROVIDER_TYPE.S3,
                auth_params=None,
                auth=auth,
            )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
hatch run test:test tests/test_unit/backends/test_http_backend.py::TestFacadeAuthParam -v
```
Expected: FAIL — `from_path` doesn't accept `auth=`.

- [ ] **Step 3: Update StorageFacade to accept auth=**

In `src/mountainash_utils_files/storage_facade/facade.py`, change `__init__`:

```python
    def __init__(
        self,
        provider_type: CONST_STORAGE_PROVIDER_TYPE,
        auth_params: typing.Any = None,
        *,
        auth: typing.Any = None,
    ) -> None:
        self._backend = get_storage_backend(provider_type, auth_params, auth=auth)
        if auth is not None and not hasattr(self._backend, "auth"):
            raise ValueError(
                f"auth= is not supported for provider {provider_type!r}; "
                "use auth_params with a profile instead"
            )
```

Change `from_path`:

```python
    @classmethod
    def from_path(
        cls,
        path: str,
        auth_params: typing.Any = None,
        *,
        auth: typing.Any = None,
    ) -> StorageFacade:
        """Construct a facade whose provider is inferred from a path's URL scheme.

        Args:
            path: Path string, optionally with a URL scheme.
            auth_params: Optional auth params forwarded to the backend.
            auth: Optional AuthSpec instance for direct authentication
                (currently HTTP only).

        Returns:
            A StorageFacade wired to the provider that matches *path*.

        Raises:
            ValueError: If *path*'s scheme is unrecognised or has no backend,
                or if *auth* is provided for a provider that doesn't support it.
        """
        provider = detect_provider_from_path(path)
        return cls(provider_type=provider, auth_params=auth_params, auth=auth)
```

- [ ] **Step 4: Update read_bytes() to accept auth=**

In `src/mountainash_utils_files/storage_facade/read_bytes.py`, change the function signature and body:

```python
def read_bytes(
    path: str,
    *,
    auth_params: typing.Any = None,
    auth: typing.Any = None,
    infer: bool = False,
    gpg: GPG | None = None,
    gzip: Gzip | None = None,
) -> bytes:
    """Read the full contents of *path* as bytes, dispatching by URL scheme.

    All recognised schemes route through :meth:`StorageFacade.from_path`.
    When *infer* is True, the facade applies suffix-driven transform
    inference via :func:`infer_pipeline`.

    Args:
        path: Path or URL.
        auth_params: Optional auth params forwarded to the storage facade.
        auth: Optional AuthSpec instance for direct authentication
            (currently HTTP only).
        infer: When True, inspect *path*'s suffix chain and auto-apply a
            read-side ``Pipeline`` for known suffixes (``.gz``, ``.gzip``,
            ``.gpg``, ``.asc``, ``.pgp``). Default False preserves
            byte-for-byte current behaviour.
        gpg: Required when *infer* is True and the suffix chain contains a
            gpg-family suffix. Supplies key material. Ignored when *infer*
            is False.
        gzip: Optional; defaults to ``Gzip()`` when a gzip suffix is seen.
            Ignored when *infer* is False.

    Returns:
        The full content of *path* as ``bytes``, optionally transform-decoded.

    Raises:
        ValueError: If the scheme is unrecognised, describes a backend that
            is not registered, or *infer* is True and a gpg-family suffix
            was seen without a *gpg* instance.
    """
    facade = StorageFacade.from_path(path, auth_params, auth=auth)
    return facade.read(path, infer=infer, gpg=gpg, gzip=gzip)
```

- [ ] **Step 5: Update storage() convenience function in __init__.py**

In `src/mountainash_utils_files/__init__.py`, update the `storage()` function:

```python
def storage(provider_type: CONST_STORAGE_PROVIDER_TYPE = CONST_STORAGE_PROVIDER_TYPE.LOCAL,
            auth_params=None, *, auth=None) -> StorageFacade:
    """Convenience factory for creating a StorageFacade."""
    return StorageFacade(provider_type, auth_params, auth=auth)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run:
```bash
hatch run test:test tests/test_unit/backends/test_http_backend.py -v
```
Expected: All tests PASS.

- [ ] **Step 7: Run the full test suite**

Run:
```bash
hatch run test:test -v
```
Expected: All tests PASS. No regressions.

- [ ] **Step 8: Commit**

```bash
git add src/mountainash_utils_files/storage_facade/ src/mountainash_utils_files/__init__.py tests/test_unit/backends/test_http_backend.py
git commit -m "feat: thread auth= parameter through StorageFacade, read_bytes, and storage()"
```

---

### Task 9: Final Validation

**Files:** None (verification only)

- [ ] **Step 1: Run the full test suite**

Run:
```bash
hatch run test:test -v
```
Expected: All tests PASS.

- [ ] **Step 2: Run linting**

Run:
```bash
hatch run ruff:check
```
Expected: No errors (or only pre-existing ones unrelated to this change).

- [ ] **Step 3: Verify no residual broken imports**

Run:
```bash
grep -rn "from mountainash_settings.auth" src/ tests/ --include="*.py" | grep -v "^.*:#"
```
Expected: No output (zero active imports from the old path).

- [ ] **Step 4: Verify the end-to-end API works**

Run:
```bash
hatch run test:python -c "
from mountainash_auth_client import TokenAuth, NoAuth
from pydantic import SecretStr
from mountainash_utils_files import StorageFacade, read_bytes

# Direct auth with facade
facade = StorageFacade.from_path('https://example.com/test', auth=TokenAuth(token=SecretStr('abc')))
print(f'Backend auth: {facade._backend.auth}')
print(f'Backend type: {type(facade._backend).__name__}')

# NoAuth
facade2 = StorageFacade.from_path('https://example.com/test', auth=NoAuth())
print(f'NoAuth backend auth: {facade2._backend.auth}')

print('End-to-end API OK')
"
```
Expected: Prints backend info and `End-to-end API OK`.
