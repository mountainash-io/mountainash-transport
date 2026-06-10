# Provider Registry Honesty — Design Spec

> **Date:** 2026-06-10
> **Status:** Draft
> **Backlog item:** #8 (provider-registry-honesty.md)
> **Depends on:** Profile Hierarchy Abstraction (2026-06-10-profile-hierarchy-abstraction-design.md)
> **Branch:** TBD (off `develop`, after prerequisite merges)

## Problem

Three registries describe storage providers and they disagree. The result is
confusing failures, silent misrouting, and a scheme table full of aspirational
entries that resolve to nothing.

Specific issues:

1. **SFTP backend registers under `SSH`** — `sftp://` maps to
   `CONST_STORAGE_PROVIDER_TYPE.SFTP` but the backend registers under `SSH`,
   so `from_path("sftp://...")` hits a lookup miss.
2. **Five profiles point at nonexistent backends** — GCS, Azure, FTP, SMB, and
   GitHub profiles construct successfully but `get_storage_backend()` raises an
   opaque `ValueError`.
3. **Eight describe-only schemes** (s3u, dbfs, hdfs, webhdfs, spark, trino,
   gdrive, dropbox, onedrive, sharepoint) map to `provider=None` with no enum,
   profile, or backend — pure clutter.
4. **`get_storage_backend()` accepts an `auth_profile` parameter it never
   uses** — dead code that lies about the API surface.
5. **All leaf connections (SSH, HTTP, S3) take `StorageProfileProtocol`** — the
   connection layer is coupled to storage profiles when it should accept plain
   kwargs. This is most wrong for SSH, which is a general-purpose transport.

## Scope

This spec covers six changes:

1. SFTP provider identity fix (rename SSH storage provider → SFTP)
2. Connection decoupling from `StorageProfileProtocol` → accept `connect_kwargs: dict`
3. `BackendNotImplementedError` + `implemented` flag on `StorageProfileSpec`
4. Scheme table cleanup (remove describe-only entries)
5. Drop unused `auth_profile` param from `get_storage_backend()`
6. New backlog items for unimplemented backends

**Prerequisite:** The Profile Hierarchy Abstraction spec must land first. It
extracts `ProfileProtocol` as the base protocol and widens the connection
factory to accept it. This spec then:
- Decouples connections from profiles entirely (kwargs, not protocol)
- Renames the SSH storage profile to SFTP (storage-specific)
- SSH can later get a `ProfileProtocol`-only profile (not storage) — tracked
  in the SSH backend backlog item (§5a)

Out of scope: implementing any missing backends, OAuth connection decoupling,
async readiness, or messaging family work.

### Findings deferred to other backlog items

These issues were identified during adversarial review and are valid but belong
in other work items:

- **`_PROVIDER_CONNECTION_MAP` returns leaf class, not factory** — a future
  caller of `_connection_for_provider("sftp")` outside the special
  `create_connection` branch would get `SSHConnection` instead of
  `SFTPConnection`. Low risk (map is private), but a factory-based map would
  be cleaner. → Fold into #2 (lifecycle).
- **`get_connection_url()` lost from connection contract** — connections no
  longer have access to the profile's `get_connection_url()`. If diagnostics
  or cache keys need a canonical URL, pass it separately. → Fold into #2.
- **`create_tunnelled_connection()` target-side still profile-coupled** — the
  inner factory passes the target profile to `create_connection()`, which now
  calls `to_handler_kwargs()` internally. The prerequisite widens the target
  type to `ProfileProtocol` and updates `_PatchedEndpointProfile`. No gap
  today, but full kwargs-only tunnelled target construction deferred. →
  Fold into #2.
- **Azure Blob vs Files scheme ambiguity** — `azure://` maps only to
  `AZURE_BLOB`; `SERVICE_TYPE="files"` has no distinct scheme. → Track in
  unimplemented backends backlog item (§5b).
- **Profile/provider mismatch guard** — `get_storage_backend()` doesn't
  validate that `storage_profile.__spec__.provider_type` matches
  `provider_type`. → Fold into #1 (error mapping) or #2 (lifecycle).
- **S3 flavor registry coverage** — single `S3StorageProfile` registered
  under `S3`; flavors are internal. Scheme-table conformance test covers
  drift. No action needed unless flavors get separate profiles.

---

## 1. SFTP Provider Identity Fix

SSH is a connection-layer concern (paramiko `SSHClient`). The storage provider
that does file operations over SFTP should be identified as `SFTP`, not `SSH`.

### Changes

**`SFTPStorageBackend` registration** (`storage/backends/sftp/__init__.py`):
- Register under `CONST_STORAGE_PROVIDER_TYPE.SFTP` instead of `SSH`.

**Profile rename** — `SSHStorageProfile` → `SFTPStorageProfile`:
- Rename file: `ssh_storage_profile.py` → `sftp_storage_profile.py`
- Rename class: `SSHStorageProfile` → `SFTPStorageProfile`
- Rename spec: `SSH_SPEC` → `SFTP_SPEC`, `name="ssh"` → `name="sftp"`
- Change registration: `CONST_STORAGE_PROVIDER_TYPE.SSH` →
  `CONST_STORAGE_PROVIDER_TYPE.SFTP`

**`_PROVIDER_CONNECTION_MAP`** (`connections/__init__.py`):
- Add `"sftp"` entry pointing to `SSHConnection` (SFTP provider uses SSH
  connection layer internally; the `create_connection` SFTP branch wraps it
  in `SFTPConnection`).
- Remove or leave absent any `"ssh"` entry — SSH has no storage backend yet
  and should not silently fall through to `HTTPConnection`.
- After the connection decoupling (§2), `_connection_for_provider()` should
  accept a provider type string directly instead of extracting it from a
  profile object — the profile is no longer available at that point.

**`create_connection()` dispatch** (`connections/__init__.py`):
- Change the SSH/SFTP branch from
  `if provider_type == SSH` to `if provider_type == SFTP`.
- The wiring stays the same: `SSHConnection` → `SFTPConnection` chain.

**Scheme table** (`path_helpers/scheme.py`):
- `sftp://` already maps to `SFTP` — no change needed.
- `ssh://` stays, maps to `SSH` — becomes an unimplemented provider.

**Connection layer untouched** — `SSHConnection` and `SFTPConnection` keep
their class names and file locations. SSH is correct naming for the connection.

**Enum** — both `SSH` and `SFTP` stay in `CONST_STORAGE_PROVIDER_TYPE`. `SSH`
becomes an unimplemented provider with no backend and no profile (the profile
is renamed to `SFTPStorageProfile` and moves to `SFTP`). A future SSH-as-local
storage backend is a separate backlog item.

**Auth resolver** — `resolve_auth_strategy()` currently maps `SSH` →
SSH-family strategies (`SSHPasswordStrategy`, `SSHKeyStrategy`,
`SSHKerberosStrategy`). Add `SFTP` to the same SSH-family dispatch so that
`resolve_auth_strategy(auth_profile, provider_type=SFTP)` resolves correctly.
The SFTP provider uses SSH connections internally, so the auth strategies are
identical.

### Public API re-exports

Update `__init__.py` and any `__all__` lists that export `SSHStorageProfile`
to export `SFTPStorageProfile` instead.

---

## 2. Connection Decoupling from ProfileProtocol → Plain kwargs

After the prerequisite lands, leaf connections accept `ProfileProtocol` (base)
instead of `StorageProfileProtocol`. This spec takes the next step: remove the
profile dependency entirely. Connections accept `connect_kwargs: dict` — they
don't need any protocol, just the kwargs dict.

### Interface change

Before:
```python
class SSHConnection(ConnectionProtocol):
    def __init__(self, profile: StorageProfileProtocol, auth_strategy: AuthStrategy):
        self._profile = profile
        self._auth_strategy = auth_strategy

    def connect(self) -> Self:
        kwargs = self._profile.to_handler_kwargs()
        kwargs = self._auth_strategy.apply(kwargs)
        # ...create client...
```

After:
```python
class SSHConnection(ConnectionProtocol):
    def __init__(self, connect_kwargs: dict[str, Any], auth_strategy: AuthStrategy):
        self._connect_kwargs = connect_kwargs
        self._auth_strategy = auth_strategy

    def connect(self) -> Self:
        kwargs = dict(self._connect_kwargs)   # defensive copy
        kwargs = self._auth_strategy.apply(kwargs)
        # ...create client...
```

Apply identically to `HTTPConnection` and `S3Connection`.

### Factory absorbs profile→kwargs

`create_connection()` calls `profile.to_handler_kwargs()` before constructing
the connection:

```python
def create_connection(
    profile: ProfileProtocol,          # widened by prerequisite
    auth_profile: AuthProfile | None = None,
    *,
    auto_authorize: bool = False,
) -> ConnectionProtocol:
    # ...OAuth dispatch (unchanged)...

    provider_type = _provider_type_from_profile(profile)
    kwargs = profile.to_handler_kwargs()       # extracted here, not in connection

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

### `create_tunnelled_connection()` — same treatment

```python
def create_tunnelled_connection(bastion_profile, bastion_auth, ...):
    bastion_kwargs = bastion_profile.to_handler_kwargs()
    ssh_conn = SSHConnection(
        bastion_kwargs,
        resolve_auth_strategy(bastion_auth, provider_type=...),
    )
    # ...rest unchanged...
```

### SFTPConnection untouched

Already takes `SSHConnection`, not a profile — no change needed.

### OAuth connections out of scope

`OAuth2Connection` and `OAuth1Connection` have their own flow and profile
coupling. Decoupling those is tracked in the OAuth extraction backlog item.

---

## 3. `BackendNotImplementedError` + `implemented` Flag

### New exception

Add to `_core/exceptions.py`:

```python
class BackendNotImplementedError(StorageError):
    """Raised when a provider has a profile but no storage backend yet."""
```

### `StorageProfileSpec.implemented` field

Add to `settings/profile_spec.py`:

```python
@dataclass(frozen=True, kw_only=True)
class StorageProfileSpec(ProfileSpec):
    # ...existing fields...
    implemented: bool = True
```

Set `implemented=False` on these profile specs:
- `GCSStorageProfile` (GCS_SPEC)
- `AzureStorageProfile` (AZURE_STORAGE_SPEC)
- `FTPStorageProfile` (FTP_SPEC)
- `SMBStorageProfile` (SMB_SPEC)
- `GitHubRepoStorageProfile` (GITHUB_REPO_SPEC)

Note: SSH currently shares a profile with SFTP. After the rename, the SFTP
profile gets `implemented=True`. SSH has no profile and no backend — it exists
only as an enum value and scheme entry. It does not appear in
`STORAGE_REGISTRY` and therefore is not covered by the profile-level drift
test (which iterates over registered profiles).

SSH is handled at the backend lookup level: `get_storage_backend()` raises
`BackendNotImplementedError` for any provider type that has no registered
backend, regardless of whether a profile exists. The lookup-miss logic is:

1. Check `_backend_registry` — if found, instantiate and return.
2. Check `STORAGE_REGISTRY` for a descriptor whose
   `spec.provider_type == provider_type` and `spec.implemented == False` —
   if found, raise `BackendNotImplementedError` with actionable message.
3. Otherwise raise `ValueError` (truly unknown provider).

Step 2 handles profiled-but-unimplemented providers (GCS, Azure, etc.).
For providers with no profile at all (SSH), step 2 finds no match and step 3
fires — but `ValueError` is unhelpful for a valid enum value. To handle this
cleanly, add a step 2b: if `provider_type` is a valid
`CONST_STORAGE_PROVIDER_TYPE` member but has neither a backend nor a profile,
raise `BackendNotImplementedError` (not `ValueError`). This covers SSH and any
future enum-only providers.

### `get_storage_backend()` changes

1. Remove `auth_profile` parameter (dead code).
2. On lookup miss, apply the three-step resolution described above:
   backend registry → profile registry (matched by `provider_type`) →
   valid enum check. All three miss paths raise the appropriate error.

New signature:
```python
def get_storage_backend(
    provider_type: CONST_STORAGE_PROVIDER_TYPE,
    storage_profile: StorageProfileProtocol | None,
    *,
    connection=None,
) -> Any:
```

### Drift test

Parametrized conformance test:

```python
@pytest.mark.parametrize("name, descriptor", STORAGE_REGISTRY.descriptors.items())
def test_implemented_flag_matches_backend_registry(name, descriptor):
    """spec.implemented must be True iff a backend is registered."""
    has_backend = descriptor.spec.provider_type in get_registered_backends()
    assert descriptor.spec.implemented == has_backend, (
        f"Profile '{name}' has implemented={descriptor.spec.implemented} "
        f"but backend registered={has_backend}"
    )
```

---

## 4. Scheme Table Cleanup

### Remove describe-only schemes

Delete these entries from `SCHEMES` in `path_helpers/scheme.py`:

| Scheme | Reason |
|--------|--------|
| `s3u` | No provider, no profile, no backend |
| `dbfs` | Aspirational — Databricks |
| `hdfs` | Aspirational — Hadoop |
| `webhdfs` | Aspirational — Hadoop |
| `spark` | Aspirational |
| `trino` | Aspirational |
| `gdrive` | Aspirational — Google Drive |
| `dropbox` | Aspirational |
| `onedrive` | Aspirational |
| `sharepoint` | Aspirational |

These schemes can be re-added when backend work begins. The new backlog item
for unimplemented backends tracks this.

### Remaining scheme table (after cleanup)

| Scheme | Provider | Backend |
|--------|----------|---------|
| `""` / `file` | LOCAL | LocalStorageBackend |
| `s3` | S3 | S3StorageBackend |
| `s3express` | S3EXPRESS | S3StorageBackend |
| `r2` | R2 | S3StorageBackend |
| `minio` | MINIO | S3StorageBackend |
| `b2` | B2 | S3StorageBackend |
| `gs` (alias: `gcs`) | GCS | not implemented |
| `azure` (alias: `az`) | AZURE_BLOB | not implemented |
| `sftp` | SFTP | SFTPStorageBackend |
| `ssh` | SSH | not implemented |
| `ftp` | FTP | not implemented |
| `smb` | SMB | not implemented |
| `github` | GITHUB | not implemented |
| `http` / `https` | HTTP | HTTPStorageBackend |

Unimplemented schemes stay because they have valid enum values — the
`BackendNotImplementedError` path handles them honestly. Most also have
profiles (GCS, Azure, FTP, SMB, GitHub); SSH has an enum value and scheme
but no profile.

---

## 5. New Backlog Items

### 5a. SSH Storage Backend

Design an SSH-as-local storage backend. Once an SSH connection is established,
the remote filesystem appears local — operations via shell commands or an
sshfs-style approach. Includes the profile design question: inherit from
`SFTPStorageProfile` or create a separate class.

The connection decoupling from this spec makes this clean to implement — the
SSH backend can construct `SSHConnection` with plain kwargs without needing a
storage profile.

### 5b. Unimplemented Provider Backends (Incremental)

Track incremental implementation of storage backends for providers that
currently have profiles but no backends:

- **GCS** — google-cloud-storage SDK, optional extra `[gcs]` already declared
- **Azure Blob** — azure-storage-blob SDK, optional extra `[azure]` already
  declared
- **Azure Files** — via Azure profile's `SERVICE_TYPE` discriminator
- **FTP/FTPS** — stdlib `ftplib`, profile already exists
- **SMB** — smbprotocol, optional extra needed
- **GitHub** — read-only, fsspec-backed, profile already exists

Each backend is a self-contained sub-item that can be picked up independently.
GCS and Azure are natural first candidates.

---

## 6. Test Strategy

### Registry completeness test (rewrite)

Replace hardcoded `REQUIRED_BACKENDS` / `ASPIRATIONAL_BACKENDS` sets with the
drift test from §3 — the `implemented` flag is the single source of truth.

### Scheme-table conformance test (new)

Parametrized over every entry in `SCHEMES` that has a non-None `provider`:

- If the provider has a registered backend → the scheme is usable end-to-end.
  Verify `get_storage_backend(provider)` does not raise.
- If the provider has no registered backend → verify
  `get_storage_backend(provider)` raises `BackendNotImplementedError`.
- If the provider has a profile in `STORAGE_REGISTRY` → verify
  `spec.implemented` matches backend registration (cross-check with drift
  test).

This catches scheme→provider mappings that drift from the backend/profile
state — the exact class of bug this spec is eliminating.

### Backend detection tests

- Update `sftp://` to expect `SFTP` provider type.
- Remove test cases for deleted describe-only schemes (s3u, dbfs, etc.).
- Add test: `ssh://` resolves to `SSH` provider type (unimplemented but valid).

### Scheme tests

- Update expected scheme count.
- Remove assertions about deleted entries.

### Settings registry tests

- Update expected provider set: `"ssh"` → `"sftp"` in
  `STORAGE_REGISTRY.descriptors`.

### Connection tests

- All three leaf connection test files: update to pass `connect_kwargs: dict`
  instead of mock `StorageProfileProtocol`.
- `create_connection` tests: verify `profile.to_handler_kwargs()` is called in
  the factory, and the resulting dict is passed to the connection constructor.
- `create_tunnelled_connection` tests: same treatment for bastion profile.

### Profile tests

- Rename `test_ssh_storage_profile.py` → `test_sftp_storage_profile.py`.
- Update class references and spec name assertions.

---

## Acceptance Criteria

1. `StorageFacade.from_path("sftp://host/path", profile, auth)` works —
   resolves to SFTP provider, gets SFTPStorageBackend.
2. `StorageFacade.from_path("gs://bucket/key")` raises
   `BackendNotImplementedError` with actionable message listing implemented
   providers.
3. `StorageFacade.from_path("ssh://host/path")` raises
   `BackendNotImplementedError` (SSH is unimplemented as a storage provider).
4. Leaf connections (`SSHConnection`, `HTTPConnection`, `S3Connection`) accept
   `connect_kwargs: dict` — no `StorageProfileProtocol` import or dependency.
5. `create_connection()` calls `profile.to_handler_kwargs()` and passes the
   dict to the connection constructor.
6. Drift test passes: `spec.implemented` matches backend registration for
   every profile in `STORAGE_REGISTRY`.
7. No describe-only schemes remain in the scheme table.
8. `get_storage_backend()` has no `auth_profile` parameter.
9. `resolve_auth_strategy(PasswordAuth(...), provider_type=SFTP)` returns
   `SSHPasswordStrategy` (SFTP added to SSH-family dispatch).
10. Scheme-table conformance test passes: every scheme with a provider either
    resolves to a backend or raises `BackendNotImplementedError`.
11. All existing tests pass; new assertions covered by unit tests.
