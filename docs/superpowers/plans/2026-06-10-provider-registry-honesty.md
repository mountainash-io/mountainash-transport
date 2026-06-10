# Provider Registry Honesty — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the provider registry honest — fix the SFTP/SSH identity confusion, decouple connections from profiles to plain kwargs, add fail-fast `BackendNotImplementedError` for unimplemented providers, clean up aspirational scheme entries, and add drift tests.

**Architecture:** Six coordinated changes: (1) rename SSH storage provider to SFTP, (2) decouple leaf connections from `ProfileProtocol` to `connect_kwargs: dict`, (3) add `BackendNotImplementedError` + `implemented` flag + three-step lookup, (4) remove describe-only schemes, (5) drop dead `auth_profile` param, (6) create backlog items. All connection construction now goes through the factory, which extracts kwargs from profiles.

**Tech Stack:** Python typing, pytest parametrize, dataclasses

**Spec:** `docs/superpowers/specs/2026-06-10-provider-registry-honesty-design.md`
**Prerequisite:** `docs/superpowers/plans/2026-06-10-profile-hierarchy-abstraction.md` must be merged first.

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Rename | `src/.../settings/storage/profiles/ssh_storage_profile.py` → `sftp_storage_profile.py` | Profile rename SSH→SFTP |
| Modify | `src/.../settings/storage/profiles/__init__.py` | Re-export renamed profile |
| Modify | `src/.../storage/backends/sftp/__init__.py:19` | Re-register under SFTP |
| Modify | `src/.../connections/__init__.py` | SFTP dispatch, kwargs decoupling, provider map |
| Modify | `src/.../connections/ssh.py` | Accept `connect_kwargs: dict` |
| Modify | `src/.../connections/http.py` | Accept `connect_kwargs: dict` |
| Modify | `src/.../connections/s3.py` | Accept `connect_kwargs: dict` |
| Modify | `src/.../_core/exceptions.py` | Add `BackendNotImplementedError` |
| Modify | `src/.../settings/profile_spec.py` | Add `implemented: bool` field |
| Modify | `src/.../storage/registry/registry.py` | Three-step lookup, drop `auth_profile` |
| Modify | `src/.../storage/path_helpers/scheme.py` | Remove describe-only schemes |
| Modify | `src/.../_core/auth/resolver.py:68` | Add SFTP to SSH-family dispatch |
| Modify | `src/mountainash_transport/__init__.py` | Export `BackendNotImplementedError` |
| Modify | 5 profile specs | Set `implemented=False` on GCS, Azure, FTP, SMB, GitHub |
| Rewrite | `tests/storage/protocols/test_registry_completeness.py` | Drift test + scheme conformance |
| Modify | `tests/connections/test_factory.py` | Update for kwargs + SFTP dispatch |
| Modify | `tests/connections/test_ssh_connection.py` | Pass kwargs dict |
| Modify | `tests/connections/test_http_connection.py` | Pass kwargs dict |
| Modify | `tests/connections/test_s3_connection.py` | Pass kwargs dict |
| Rename | `tests/settings/storage/profiles/test_ssh_settings.py` → `test_sftp_settings.py` | Profile test rename |
| Modify | `tests/storage/registry/test_backend_detection.py` | Update scheme expectations |
| Modify | `tests/storage/path_helpers/test_scheme.py` | Update scheme count |
| Modify | `tests/settings/storage/test_registry.py` | Update descriptor set |
| Create | Backlog files in mountainash-central | SSH backend + unimplemented providers |

---

### Task 1: Add `BackendNotImplementedError` Exception

**Files:**
- Modify: `src/mountainash_transport/_core/exceptions.py:31`
- Modify: `src/mountainash_transport/__init__.py`

- [ ] **Step 1: Write a test for the new exception**

Add to a new section at the end of `tests/_core/test_constants_and_exceptions.py` (or create inline):

```python
from mountainash_transport._core.exceptions import BackendNotImplementedError, StorageError


def test_backend_not_implemented_error_is_storage_error():
    exc = BackendNotImplementedError("GCS backend not yet implemented")
    assert isinstance(exc, StorageError)
    assert "GCS" in str(exc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `hatch run test:test tests/_core/test_constants_and_exceptions.py::test_backend_not_implemented_error_is_storage_error -v`
Expected: FAIL with `ImportError: cannot import name 'BackendNotImplementedError'`

- [ ] **Step 3: Add the exception**

In `src/mountainash_transport/_core/exceptions.py`, after `TransformError` (line 31), add:

```python
class BackendNotImplementedError(StorageError):
    """Raised when a storage provider has no backend implementation yet."""
```

- [ ] **Step 4: Export from package root**

In `src/mountainash_transport/__init__.py`, add `BackendNotImplementedError` to the import from `._core.exceptions` and to `__all__`.

- [ ] **Step 5: Run test to verify it passes**

Run: `hatch run test:test tests/_core/test_constants_and_exceptions.py::test_backend_not_implemented_error_is_storage_error -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/_core/exceptions.py src/mountainash_transport/__init__.py tests/_core/test_constants_and_exceptions.py
git commit -m "feat: add BackendNotImplementedError exception"
```

---

### Task 2: Add `implemented` Flag to StorageProfileSpec

**Files:**
- Modify: `src/mountainash_transport/settings/profile_spec.py:31-59`
- Modify: 5 profile spec files (GCS, Azure, FTP, SMB, GitHub)

- [ ] **Step 1: Write a test for the new field**

```python
# tests/settings/test_profile_spec.py (add to existing or create)
from mountainash_transport.settings.profile_spec import StorageProfileSpec


def test_implemented_defaults_to_true():
    spec = StorageProfileSpec(name="test", provider_type="test", parameters=[])
    assert spec.implemented is True


def test_implemented_can_be_false():
    spec = StorageProfileSpec(name="test", provider_type="test", parameters=[], implemented=False)
    assert spec.implemented is False
```

- [ ] **Step 2: Run to verify failure**

Run: `hatch run test:test tests/settings/test_profile_spec.py -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'implemented'`

- [ ] **Step 3: Add the field**

In `src/mountainash_transport/settings/profile_spec.py`, add after `supported_auth` (line 58):

```python
    implemented: bool = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `hatch run test:test tests/settings/test_profile_spec.py -v`
Expected: PASS

- [ ] **Step 5: Set `implemented=False` on 5 unimplemented profile specs**

In `src/mountainash_transport/settings/storage/profiles/gcs_storage_profile.py`, add `implemented=False` to `GCS_SPEC`:
```python
GCS_SPEC = StorageProfileSpec(
    ...
    implemented=False,
)
```

Repeat for:
- `azure_storage_profile.py` → `AZURE_STORAGE_SPEC`
- `ftp_storage_profile.py` → `FTP_SPEC`
- `smb_storage_profile.py` → `SMB_SPEC`
- `github_storage_profile.py` → `GITHUB_REPO_SPEC`

- [ ] **Step 6: Verify existing tests still pass**

Run: `hatch run test:test tests/settings/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_transport/settings/profile_spec.py src/mountainash_transport/settings/storage/profiles/gcs_storage_profile.py src/mountainash_transport/settings/storage/profiles/azure_storage_profile.py src/mountainash_transport/settings/storage/profiles/ftp_storage_profile.py src/mountainash_transport/settings/storage/profiles/smb_storage_profile.py src/mountainash_transport/settings/storage/profiles/github_storage_profile.py tests/settings/test_profile_spec.py
git commit -m "feat: add implemented flag to StorageProfileSpec

Set implemented=False on GCS, Azure, FTP, SMB, and GitHub profiles
that have no storage backend yet."
```

---

### Task 3: SFTP Provider Identity Fix — Profile Rename

**Files:**
- Rename: `src/.../settings/storage/profiles/ssh_storage_profile.py` → `sftp_storage_profile.py`
- Modify: `src/.../settings/storage/profiles/__init__.py`
- Rename: `tests/settings/storage/profiles/test_ssh_settings.py` → `test_sftp_settings.py`

- [ ] **Step 1: Create the new file by copying and modifying**

Create `src/mountainash_transport/settings/storage/profiles/sftp_storage_profile.py` with these changes from the original `ssh_storage_profile.py`:

- Module docstring: replace "SSH + SFTP" with "SFTP storage profile"
- `SSH_SPEC` → `SFTP_SPEC`
- `name="ssh"` → `name="sftp"`
- `provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH` → `provider_type=CONST_STORAGE_PROVIDER_TYPE.SFTP`
- `handler_class="SSHStorageBackend"` → `handler_class="SFTPStorageBackend"`
- `__all__` → `["SFTP_SPEC", "SFTPStorageProfile"]`
- Class `SSHStorageProfile` → `SFTPStorageProfile`
- Class docstring: replace "SSH / SFTP" with "SFTP"
- `get_connection_url`: change `ssh://` prefix to `sftp://`
- Username validation message: "USERNAME is required for SFTP."

- [ ] **Step 2: Delete the old file**

```bash
git rm src/mountainash_transport/settings/storage/profiles/ssh_storage_profile.py
```

- [ ] **Step 3: Update `__init__.py` re-exports**

In `src/mountainash_transport/settings/storage/profiles/__init__.py`, replace:

```python
from .ssh_storage_profile import SSH_SPEC, SSHStorageProfile
```

with:

```python
from .sftp_storage_profile import SFTP_SPEC, SFTPStorageProfile
```

Update `__all__` — replace `"SSH_SPEC"`, `"SSHStorageProfile"` with `"SFTP_SPEC"`, `"SFTPStorageProfile"`.

Update the module docstring line about SSH+SFTP to say:
```
* SFTP → :class:`SFTPStorageProfile` (paramiko SFTP subsystem)
```

- [ ] **Step 4: Rename the test file and update references**

```bash
git mv tests/settings/storage/profiles/test_ssh_settings.py tests/settings/storage/profiles/test_sftp_settings.py
```

In the renamed test file, update all references:
- `SSHStorageProfile` → `SFTPStorageProfile`
- `SSH_SPEC` → `SFTP_SPEC`
- `ssh_storage_profile` → `sftp_storage_profile`
- Import paths
- Any assertion on `spec.name` from `"ssh"` to `"sftp"`
- Any assertion on `provider_type` from `SSH` to `SFTP`

- [ ] **Step 5: Run settings tests**

Run: `hatch run test:test tests/settings/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: rename SSHStorageProfile → SFTPStorageProfile

SSH is a connection-layer concern. The storage provider that does file
operations via the SFTP subsystem is correctly identified as SFTP."
```

---

### Task 4: SFTP Provider Identity Fix — Backend and Factory

**Files:**
- Modify: `src/mountainash_transport/storage/backends/sftp/__init__.py:19`
- Modify: `src/mountainash_transport/connections/__init__.py:51-59,88-94`
- Modify: `src/mountainash_transport/_core/auth/resolver.py:68`

- [ ] **Step 1: Write a test for SFTP provider type dispatch**

Add to `tests/connections/test_factory.py`:

```python
class FakeSFTPProfile:
    class __spec__:
        provider_type = "sftp"

    def to_handler_kwargs(self) -> dict:
        return {
            "hostname": "example.com",
            "port": 22,
            "username": "user",
            "_post_connect": {"host_key_policy": "auto_add"},
        }

    def get_connection_url(self) -> str:
        return "sftp://user@example.com:22"


class TestCreateConnectionSFTP:
    def test_sftp_profile_returns_sftp_connection(self):
        from mountainash_auth_client import PasswordAuth
        conn = create_connection(
            FakeSFTPProfile(), auth_profile=PasswordAuth(USERNAME="u", PASSWORD="p")
        )
        assert isinstance(conn, SFTPConnection)

    def test_sftp_profile_no_auth_returns_sftp_connection(self):
        conn = create_connection(FakeSFTPProfile())
        assert isinstance(conn, SFTPConnection)
```

- [ ] **Step 2: Run to verify it fails**

Run: `hatch run test:test tests/connections/test_factory.py::TestCreateConnectionSFTP -v`
Expected: FAIL — the factory dispatches on `SSH`, not `SFTP`

- [ ] **Step 3: Re-register backend under SFTP**

In `src/mountainash_transport/storage/backends/sftp/__init__.py`, change line 19:

```python
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.SFTP)
```

- [ ] **Step 4: Update factory dispatch**

In `src/mountainash_transport/connections/__init__.py`:

Add `"sftp"` to `_PROVIDER_CONNECTION_MAP` (after `"b2"` entry):
```python
"sftp": SSHConnection,
```

Change the SFTP branch (line 91) from:
```python
    if provider_type == CONST_STORAGE_PROVIDER_TYPE.SSH:
```
to:
```python
    if provider_type == CONST_STORAGE_PROVIDER_TYPE.SFTP:
```

Update auth resolution in the same block (line 92) from:
```python
        strategy = resolve_auth_strategy(auth_profile, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH)
```
to:
```python
        strategy = resolve_auth_strategy(auth_profile, provider_type=CONST_STORAGE_PROVIDER_TYPE.SFTP)
```

- [ ] **Step 5: Add SFTP to SSH-family auth dispatch**

In `src/mountainash_transport/_core/auth/resolver.py`, change line 68 from:

```python
    if provider_type == CONST_STORAGE_PROVIDER_TYPE.SSH:
```

to:

```python
    if provider_type in (CONST_STORAGE_PROVIDER_TYPE.SSH, CONST_STORAGE_PROVIDER_TYPE.SFTP):
```

- [ ] **Step 6: Update old SSH tests to use SFTP**

In `tests/connections/test_factory.py`, update the existing `FakeSSHProfile` class:

Change `provider_type = "ssh"` to `provider_type = "sftp"` and rename the class to `FakeSFTPProfile` (or keep the old name but update the `provider_type`). Update `TestCreateConnectionSSH` to use the new provider_type and rename to `TestCreateConnectionSFTP_Legacy` (or fold into the new test class).

- [ ] **Step 7: Run tests**

Run: `hatch run test:test tests/connections/test_factory.py -v`
Expected: ALL PASS

Also: `hatch run test:test tests/_core/auth/ -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/mountainash_transport/storage/backends/sftp/__init__.py src/mountainash_transport/connections/__init__.py src/mountainash_transport/_core/auth/resolver.py tests/connections/test_factory.py
git commit -m "feat: register SFTP backend under SFTP provider type

Update factory dispatch, auth resolver, and connection map to use
SFTP instead of SSH for the storage provider identity."
```

---

### Task 5: Decouple Leaf Connections from Profiles to kwargs

**Files:**
- Modify: `src/mountainash_transport/connections/ssh.py`
- Modify: `src/mountainash_transport/connections/http.py`
- Modify: `src/mountainash_transport/connections/s3.py`
- Modify: `src/mountainash_transport/connections/__init__.py` (factory)
- Modify: `tests/connections/test_ssh_connection.py`
- Modify: `tests/connections/test_http_connection.py`
- Modify: `tests/connections/test_s3_connection.py`

- [ ] **Step 1: Write test for SSHConnection accepting kwargs**

Update `tests/connections/test_ssh_connection.py`. Replace the fake profile mocks with plain dicts. The test currently creates a mock profile and passes it to `SSHConnection(profile, strategy)`. Change to `SSHConnection(connect_kwargs, strategy)`:

```python
FAKE_SSH_KWARGS = {
    "hostname": "example.com",
    "port": 22,
    "username": "testuser",
    "_post_connect": {"host_key_policy": "auto_add"},
}

# Replace SSHConnection(profile, strategy) with:
conn = SSHConnection(FAKE_SSH_KWARGS, strategy)
```

Remove the fake profile classes from this test file — they're no longer needed.

- [ ] **Step 2: Run to verify it fails**

Run: `hatch run test:test tests/connections/test_ssh_connection.py -v`
Expected: FAIL — `SSHConnection.__init__` still expects a `ProfileProtocol`

- [ ] **Step 3: Rewrite SSHConnection**

In `src/mountainash_transport/connections/ssh.py`:

Remove the `ProfileProtocol` import. Change `__init__`:

```python
class SSHConnection(ConnectionProtocol):
    """Creates an authenticated paramiko.SSHClient from connection kwargs + auth strategy."""

    def __init__(
        self,
        connect_kwargs: dict[str, t.Any],
        auth_strategy: AuthStrategy,
    ) -> None:
        self._connect_kwargs = connect_kwargs
        self._auth_strategy = auth_strategy
        self._client: t.Any = None

    def connect(self) -> Self:
        if paramiko is None:
            raise TransportConnectionError(
                "paramiko is required for SSH connections — "
                "install with: pip install mountainash-transport[sftp]"
            )

        if self._client is not None:
            self.disconnect()

        kwargs = dict(self._connect_kwargs)
        kwargs = self._auth_strategy.apply(kwargs)

        post_connect = kwargs.pop("_post_connect", {})

        client = paramiko.SSHClient()
        client.load_system_host_keys()

        policy_name = post_connect.get("host_key_policy", "reject")
        policy_attr = _HOST_KEY_POLICIES.get(policy_name)
        if policy_attr:
            client.set_missing_host_key_policy(getattr(paramiko, policy_attr)())
        else:
            client.set_missing_host_key_policy(paramiko.RejectPolicy())

        known_hosts = post_connect.get("known_hosts_file")
        if known_hosts:
            client.load_host_keys(known_hosts)

        try:
            client.connect(**kwargs)
        except socket.timeout as exc:
            raise ConnectionTimeoutError(f"SSH connection timed out: {exc}") from exc
        except socket.gaierror as exc:
            raise TransportConnectionError(f"SSH DNS resolution failed: {exc}") from exc
        except OSError as exc:
            raise TransportConnectionError(f"SSH connection failed: {exc}") from exc
        except Exception as exc:
            raise TransportConnectionError(f"SSH connection failed: {exc}") from exc

        self._client = client
        return self
```

The rest of the class (`disconnect`, `client`, `is_connected`, context manager) stays unchanged.

- [ ] **Step 4: Rewrite HTTPConnection the same way**

In `src/mountainash_transport/connections/http.py`:

Remove the `ProfileProtocol` import. Change `__init__` and `connect`:

```python
class HTTPConnection(ConnectionProtocol):
    """Creates an authenticated httpx.Client from connection kwargs + auth strategy."""

    def __init__(
        self,
        connect_kwargs: dict[str, t.Any],
        auth_strategy: AuthStrategy,
    ) -> None:
        self._connect_kwargs = connect_kwargs
        self._auth_strategy = auth_strategy
        self._client: httpx.Client | None = None

    def connect(self) -> Self:
        kwargs = dict(self._connect_kwargs)
        kwargs = self._auth_strategy.apply(kwargs)
        try:
            self._client = httpx.Client(**kwargs)
        except httpx.TimeoutException as exc:
            raise ConnectionTimeoutError(
                f"Timeout creating HTTP client: {exc}"
            ) from exc
        except httpx.ConnectError as exc:
            raise TransportConnectionError(
                f"Connection failed: {exc}"
            ) from exc
        except Exception as exc:
            raise TransportConnectionError(
                f"Failed to create HTTP client: {exc}"
            ) from exc
        return self
```

Update `tests/connections/test_http_connection.py` — replace fake profiles with plain dicts:

```python
FAKE_HTTP_KWARGS = {"timeout": 30}

# Replace HTTPConnection(profile, strategy) with:
conn = HTTPConnection(FAKE_HTTP_KWARGS, strategy)
```

- [ ] **Step 5: Rewrite S3Connection the same way**

In `src/mountainash_transport/connections/s3.py`:

Remove the `ProfileProtocol` import. Change `__init__` and `connect`:

```python
class S3Connection(ConnectionProtocol):
    """Creates an authenticated boto3 S3 client from connection kwargs + auth strategy."""

    def __init__(
        self,
        connect_kwargs: dict[str, t.Any],
        auth_strategy: AuthStrategy,
    ) -> None:
        self._connect_kwargs = connect_kwargs
        self._auth_strategy = auth_strategy
        self._client: t.Any = None

    def connect(self) -> Self:
        try:
            import boto3
        except ImportError as exc:
            raise TransportConnectionError(
                "boto3 is required for S3 connections"
            ) from exc

        kwargs = dict(self._connect_kwargs)
        kwargs = self._auth_strategy.apply(kwargs)

        kwargs.pop("service_name", None)

        try:
            self._client = boto3.client("s3", **kwargs)
        except Exception as exc:
            raise TransportConnectionError(
                f"Failed to create S3 client: {exc}"
            ) from exc

        return self
```

Update `tests/connections/test_s3_connection.py` — replace fake profiles with plain dicts.

- [ ] **Step 6: Update factory to extract kwargs before constructing connections**

In `src/mountainash_transport/connections/__init__.py`, update `create_connection()`. After the OAuth dispatch and provider detection, add kwargs extraction:

```python
    provider_type = _provider_type_from_profile(profile)
    kwargs = profile.to_handler_kwargs()

    if provider_type == CONST_STORAGE_PROVIDER_TYPE.SFTP:
        strategy = resolve_auth_strategy(auth_profile, provider_type=provider_type)
        ssh_conn = SSHConnection(kwargs, strategy)
        return SFTPConnection(ssh_conn)

    strategy = resolve_auth_strategy(auth_profile, provider_type=provider_type)
    leaf_cls = _connection_for_provider(provider_type)
    if leaf_cls is NullConnection:
        return NullConnection()
    return leaf_cls(kwargs, strategy)
```

Change `_connection_for_provider` to accept a provider type string instead of a profile:

```python
def _connection_for_provider(provider_type: CONST_STORAGE_PROVIDER_TYPE | None) -> type:
    """Map provider_type to a leaf connection class."""
    provider_str = str(provider_type.value) if hasattr(provider_type, "value") else str(provider_type)
    return _PROVIDER_CONNECTION_MAP.get(provider_str, HTTPConnection)
```

Update `create_tunnelled_connection()`:

```python
def create_tunnelled_connection(
    bastion_profile: ProfileProtocol,
    bastion_auth: AuthProfile | None,
    target_profile: ProfileProtocol,
    target_auth: AuthProfile | None,
    remote_host: str,
    remote_port: int,
) -> TunnelledConnection:
    bastion_kwargs = bastion_profile.to_handler_kwargs()
    ssh_conn = SSHConnection(
        bastion_kwargs,
        resolve_auth_strategy(bastion_auth, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH),
    )

    def inner_factory(local_port: int) -> ConnectionProtocol:
        patched = _PatchedEndpointProfile(target_profile, "127.0.0.1", local_port)
        return create_connection(patched, target_auth)

    return TunnelledConnection(ssh_conn, inner_factory, remote_host, remote_port)
```

- [ ] **Step 7: Update factory test fake profiles**

In `tests/connections/test_factory.py`, the fake profiles remain (the factory still takes profiles). But update `FakeSSHProfile` provider_type from `"ssh"` to `"sftp"` if not already done in Task 4.

- [ ] **Step 8: Run all connection tests**

Run: `hatch run test:test tests/connections/ -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add src/mountainash_transport/connections/ssh.py src/mountainash_transport/connections/http.py src/mountainash_transport/connections/s3.py src/mountainash_transport/connections/__init__.py tests/connections/
git commit -m "refactor: decouple leaf connections from ProfileProtocol to plain kwargs

SSHConnection, HTTPConnection, and S3Connection now accept
connect_kwargs: dict instead of a profile. The factory extracts
kwargs via profile.to_handler_kwargs() before construction."
```

---

### Task 6: Three-Step Backend Lookup and Drop Dead `auth_profile` Param

**Files:**
- Modify: `src/mountainash_transport/storage/registry/registry.py`
- Modify: `src/mountainash_transport/storage/facade/facade.py` (remove `auth_profile` kwarg from `get_storage_backend` call)

- [ ] **Step 1: Write tests for the new lookup behaviour**

```python
# tests/storage/registry/test_backend_not_implemented.py
import pytest
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.exceptions import BackendNotImplementedError
from mountainash_transport.storage.registry import get_storage_backend
import mountainash_transport.storage.backends  # trigger registrations


class TestBackendNotImplementedError:
    def test_profiled_unimplemented_raises(self):
        """GCS has a profile but no backend — should raise BackendNotImplementedError."""
        with pytest.raises(BackendNotImplementedError, match="not yet implemented"):
            get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.GCS, None)

    def test_enum_only_unimplemented_raises(self):
        """SSH has an enum value but no profile and no backend — should raise BackendNotImplementedError."""
        with pytest.raises(BackendNotImplementedError):
            get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.SSH, None)

    def test_implemented_provider_works(self):
        """LOCAL has a backend — should return an instance."""
        backend = get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL, None)
        assert backend is not None

    def test_sftp_provider_works(self):
        """SFTP has a backend — should return SFTPStorageBackend."""
        backend = get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.SFTP, None)
        assert type(backend).__name__ == "SFTPStorageBackend"

    def test_error_message_lists_implemented_providers(self):
        """The error message should list implemented providers."""
        with pytest.raises(BackendNotImplementedError) as exc_info:
            get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.GCS, None)
        msg = str(exc_info.value)
        assert "LOCAL" in msg or "local" in msg.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `hatch run test:test tests/storage/registry/test_backend_not_implemented.py -v`
Expected: FAIL — current code raises `ValueError`, not `BackendNotImplementedError`

- [ ] **Step 3: Implement three-step lookup**

Rewrite `src/mountainash_transport/storage/registry/registry.py`:

```python
import typing as t

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.exceptions import BackendNotImplementedError
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol


_backend_registry: dict[CONST_STORAGE_PROVIDER_TYPE, type] = {}


def register_storage_backend(provider_type: CONST_STORAGE_PROVIDER_TYPE) -> t.Callable[[type], type]:
    """Decorator that registers a backend class for a provider type."""
    def decorator(cls: type) -> type:
        _backend_registry[provider_type] = cls
        return cls
    return decorator


def get_storage_backend(
    provider_type: CONST_STORAGE_PROVIDER_TYPE,
    storage_profile: StorageProfileProtocol | None,
    *,
    connection: t.Any = None,
) -> t.Any:
    """Instantiate and return a backend for the given provider type.

    Three-step lookup on miss:
    1. Backend registry — if found, instantiate and return.
    2. Profile registry — if a profile with implemented=False exists,
       raise BackendNotImplementedError.
    2b. Valid enum — if provider_type is a valid enum member, raise
        BackendNotImplementedError.
    3. Otherwise raise ValueError (truly unknown provider).
    """
    cls = _backend_registry.get(provider_type)
    if cls is not None:
        return cls(storage_profile, connection=connection)

    implemented_names = [
        pt.value for pt in _backend_registry
    ]

    from mountainash_transport.settings.storage.registry import STORAGE_REGISTRY
    for _name, spec in STORAGE_REGISTRY.descriptors.items():
        if spec.provider_type == provider_type and not spec.implemented:
            raise BackendNotImplementedError(
                f"Storage backend for '{provider_type.value}' is not yet implemented. "
                f"Implemented providers: {', '.join(sorted(implemented_names))}"
            )

    if isinstance(provider_type, CONST_STORAGE_PROVIDER_TYPE):
        raise BackendNotImplementedError(
            f"Storage backend for '{provider_type.value}' is not yet implemented. "
            f"Implemented providers: {', '.join(sorted(implemented_names))}"
        )

    raise ValueError(f"No backend registered for {provider_type!r}")


def get_registered_backends() -> dict[CONST_STORAGE_PROVIDER_TYPE, type]:
    """Return a copy of all registered backends."""
    return dict(_backend_registry)


def clear_registry() -> None:
    """Clear all registered backends. For testing only."""
    _backend_registry.clear()
```

- [ ] **Step 4: Update facade call site**

In `src/mountainash_transport/storage/facade/facade.py`, find the call to `get_storage_backend()` and remove the `auth_profile=auth_profile` keyword argument if present.

- [ ] **Step 5: Run tests**

Run: `hatch run test:test tests/storage/registry/test_backend_not_implemented.py -v`
Expected: ALL PASS

Run: `hatch run test:test tests/storage/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/storage/registry/registry.py src/mountainash_transport/storage/facade/facade.py tests/storage/registry/test_backend_not_implemented.py
git commit -m "feat: three-step backend lookup with BackendNotImplementedError

Drop dead auth_profile param from get_storage_backend(). On lookup
miss: check profile registry for implemented=False, then check valid
enum membership, then raise ValueError for truly unknown providers."
```

---

### Task 7: Remove Describe-Only Schemes

**Files:**
- Modify: `src/mountainash_transport/storage/path_helpers/scheme.py:38,52-61`
- Modify: `tests/storage/path_helpers/test_scheme.py`
- Modify: `tests/storage/registry/test_backend_detection.py`

- [ ] **Step 1: Remove the 10 describe-only entries from SCHEMES**

In `src/mountainash_transport/storage/path_helpers/scheme.py`, delete these lines:

```python
    "s3u":        SchemeSpec(scheme="s3u"),
    "dbfs":       SchemeSpec(scheme="dbfs"),
    "hdfs":       SchemeSpec(scheme="hdfs"),
    "webhdfs":    SchemeSpec(scheme="webhdfs"),
    "spark":      SchemeSpec(scheme="spark"),
    "trino":      SchemeSpec(scheme="trino"),
    "gdrive":     SchemeSpec(scheme="gdrive"),
    "dropbox":    SchemeSpec(scheme="dropbox"),
    "onedrive":   SchemeSpec(scheme="onedrive"),
    "sharepoint": SchemeSpec(scheme="sharepoint"),
```

- [ ] **Step 2: Update scheme tests**

In `tests/storage/path_helpers/test_scheme.py`, update the expected scheme count and remove any parametrized test cases or assertions that reference the deleted schemes.

In `tests/storage/registry/test_backend_detection.py`, remove test cases that reference describe-only schemes (e.g., `hdfs`, `dbfs`). Update any error-case tests that used these schemes to use a truly unrecognized scheme like `"foobar"`.

- [ ] **Step 3: Run tests**

Run: `hatch run test:test tests/storage/path_helpers/ tests/storage/registry/test_backend_detection.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add src/mountainash_transport/storage/path_helpers/scheme.py tests/storage/path_helpers/test_scheme.py tests/storage/registry/test_backend_detection.py
git commit -m "chore: remove describe-only schemes from scheme table

Delete s3u, dbfs, hdfs, webhdfs, spark, trino, gdrive, dropbox,
onedrive, sharepoint. These had no enum, profile, or backend.
Can be re-added when backend work begins."
```

---

### Task 8: Drift Test and Scheme Conformance Test

**Files:**
- Rewrite: `tests/storage/protocols/test_registry_completeness.py`

- [ ] **Step 1: Rewrite the registry completeness test**

Replace the entire contents of `tests/storage/protocols/test_registry_completeness.py`:

```python
"""Registry honesty — drift test and scheme conformance.

The implemented flag on StorageProfileSpec is the single source of truth.
These tests pin it against the backend registry and scheme table.
"""

import pytest

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.exceptions import BackendNotImplementedError
from mountainash_transport.settings.storage.registry import STORAGE_REGISTRY
from mountainash_transport.storage.registry import get_registered_backends, get_storage_backend
from mountainash_transport.storage.path_helpers.scheme import SCHEMES
import mountainash_transport.storage.backends  # trigger registrations


class TestImplementedFlagDrift:
    """spec.implemented must be True iff a backend is registered."""

    @pytest.mark.parametrize(
        "name",
        list(STORAGE_REGISTRY.descriptors.keys()),
    )
    def test_implemented_matches_backend_registry(self, name):
        spec = STORAGE_REGISTRY.descriptors[name]
        backends = get_registered_backends()
        has_backend = spec.provider_type in backends
        assert spec.implemented == has_backend, (
            f"Profile '{name}' has implemented={spec.implemented} "
            f"but backend registered={has_backend}"
        )


class TestSchemeConformance:
    """Every scheme with a provider either resolves to a backend or raises
    BackendNotImplementedError — never an opaque ValueError."""

    @pytest.mark.parametrize(
        "scheme_key,spec",
        [
            (k, v) for k, v in SCHEMES.items() if v.provider is not None
        ],
    )
    def test_scheme_provider_is_honest(self, scheme_key, spec):
        backends = get_registered_backends()
        if spec.provider in backends:
            backend = get_storage_backend(spec.provider, None)
            assert backend is not None, (
                f"Scheme '{scheme_key}' → {spec.provider} is implemented but "
                f"get_storage_backend returned None"
            )
        else:
            with pytest.raises(BackendNotImplementedError):
                get_storage_backend(spec.provider, None)
```

- [ ] **Step 2: Run the new tests**

Run: `hatch run test:test tests/storage/protocols/test_registry_completeness.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/storage/protocols/test_registry_completeness.py
git commit -m "test: rewrite registry completeness as drift test + scheme conformance

Replace hardcoded REQUIRED/ASPIRATIONAL sets with parametrized tests
driven by the implemented flag and scheme table."
```

---

### Task 9: Update Settings Registry Test

**Files:**
- Modify: `tests/settings/storage/test_registry.py`

- [ ] **Step 1: Update expected descriptor set**

In `tests/settings/storage/test_registry.py`, find the assertion that checks for the set of registered providers. Replace `"ssh"` with `"sftp"` in the expected set:

```python
{"s3", "gcs", "azure_storage", "sftp", "ftp", "smb", "local", "github_repo", "http"}
```

- [ ] **Step 2: Run test**

Run: `hatch run test:test tests/settings/storage/test_registry.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/settings/storage/test_registry.py
git commit -m "test: update settings registry expected descriptors (ssh → sftp)"
```

---

### Task 10: Full Suite Verification

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `hatch run test:test -v`
Expected: ALL PASS

- [ ] **Step 2: Run mypy**

Run: `hatch run mypy:check`
Expected: PASS (or pre-existing issues only)

- [ ] **Step 3: Run ruff**

Run: `hatch run ruff:check`
Expected: PASS

- [ ] **Step 4: Fix any issues and commit**

```bash
git add -A
git commit -m "fix: resolve lint/type issues from registry honesty changes"
```

---

### Task 11: Create Backlog Items

**Files:**
- Create: `mountainash-central/01.principles/mountainash-utils-files/h.backlog/ssh-storage-backend.md`
- Create: `mountainash-central/01.principles/mountainash-utils-files/h.backlog/unimplemented-provider-backends.md`
- Modify: `mountainash-central/01.principles/mountainash-utils-files/h.backlog/INDEX.md`

- [ ] **Step 1: Create SSH storage backend backlog item**

Write the backlog file with: scope (SSH-as-local backend, shell commands or sshfs-style), profile design question (inherit from SFTPStorageProfile or separate), connection decoupling benefit.

- [ ] **Step 2: Create unimplemented provider backends backlog item**

Write the backlog file with: incremental implementation of GCS, Azure Blob, Azure Files, FTP, SMB, GitHub backends. Each as a sub-item. GCS and Azure first.

- [ ] **Step 3: Update INDEX.md**

Add both new items. Update #8 status from Open to Completed.

- [ ] **Step 4: Commit**

```bash
git add mountainash-central/01.principles/mountainash-utils-files/h.backlog/
git commit -m "docs: add backlog items for SSH backend and unimplemented providers"
```

---

### Task 12: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` in the repo root

- [ ] **Step 1: Update the Architecture section**

Update the provider tables to reflect:
- `SSHStorageProfile` → `SFTPStorageProfile`
- `SSH_SPEC` → `SFTP_SPEC`
- Note that SSH is unimplemented as a storage provider
- Leaf connections accept `connect_kwargs: dict`, not profiles
- Add `BackendNotImplementedError` to the exception hierarchy description
- Add `ProfileProtocol` to the protocols description
- Update the "not implemented" providers list

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for registry honesty changes"
```
