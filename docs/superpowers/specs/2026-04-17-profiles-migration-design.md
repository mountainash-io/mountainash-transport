# Phase 4: mountainash-utils-files profiles migration — design spec

**Author:** Nathaniel Ramm
**Date:** 2026-04-17
**Status:** Draft
**Depends on:** mountainash-settings v26.4.0 (released, includes `profiles/` + `auth/` sub-packages)
**Prior art:** Phase 2 (mountainash-data PR #75), Phase 3 (mountainash-utils-secrets PR #1)

## Problem

`mountainash-utils-files` currently has **15 provider settings classes** inheriting a flat `StorageAuthBase`, with flat `AUTH_METHOD` StrEnum + conditional secret fields, no discriminated union, and no registry. This is structurally out-of-step with Phases 2-3 and has accumulated non-trivial tech debt:

- **Runtime bugs**: GCS references undeclared `API_VERSION` (AttributeError at `gcs.py:304`); GitHub references undeclared `TIMEOUT` (`github.py:263`); FTP references commented-out `USE_TLS`.
- **Pydantic v1 syntax**: `const=False` in S3Express silently breaks under pydantic v2.
- **Incorrect SDK integration**: Azure classes mislabel `ClientSecretCredential` (service principal) as "managed identity"; pass `SecretStr` objects to SDKs that require plain strings.
- **Fictional parameters**: SMB has `VERSION`/`MIN_VERSION`/`MAX_VERSION`/`PREFERRED_DIALECT`/`FALLBACK_VERSIONS` — none are real `smbprotocol` params (dialect auto-negotiates). SFTP has `host_keys_filename`, `COMPRESSION_LEVEL`, `PREFERRED_AUTH_METHODS` — none are paramiko `connect()` kwargs. NFS's entire schema is `mount` CLI flags (no Python SDK exists).
- **Redundant providers**: S3, S3EXPRESS, R2, MINIO, B2 all wrap boto3 for data-plane; differences collapse to an `endpoint_url` + `flavor`. Azure Blob + Azure Files share identical auth. SFTP + SSH wrap the same paramiko `SSHClient.connect()`.
- **Misplaced provider**: GitHub is not a storage backend in the S3/GCS/Azure sense; its "storage types" (Releases, Packages, Actions, Pages) are not filesystem-shaped.

## Goals

1. **Consolidate** 15 provider classes → 7 (delete or scope-cut GitHub) with discriminators where multiple providers share an SDK/auth surface.
2. **Migrate** consolidated classes to the upstream Pattern A + Pattern B primitives (`DescriptorProfile`, `ProfileDescriptor`, `ParameterSpec` with `template`, `Registry`, typed `AuthSpec` discriminated union).
3. **Fix** the identified runtime bugs, pydantic v1 syntax, and fake SDK parameters.
4. **Collapse** the 5 S3-family backend directories into a single `s3/` backend with flavor dispatch (R2, S3Express, MinIO all wrap boto3 with different endpoint URLs; no native-SDK capabilities are in use per repo grep).
5. **Preserve** the public API surface of `mountainash_utils_files.__init__` (StorageFacade, get_storage_backend, CONST_STORAGE_PROVIDER_TYPE, protocols).

## Non-goals

- Implementing the 10 currently-unimplemented backends (GCS, Azure, SFTP, FTP, SMB, etc.). Settings classes migrate; backends remain TBD.
- MinIO admin-ops or B2 key-management via native SDKs (repo grep: zero usage — if ever needed, add slim `MinioNativeSettings` / `B2NativeSettings` later).
- NFS as a Python-SDK provider (no mature library exists; fold into `LocalSettings` with optional `mount_spec` for declarative pre-mount metadata).
- Full GitHub storage semantics. Scope-cut to read-only `GitHubRepoSettings` backed by `fsspec.GithubFileSystem`.

## Architecture

### Class consolidation

| Current classes | New class | Discriminator |
|-----------------|-----------|---------------|
| `S3StorageAuthSettings`, `S3ExpressStorageAuthSettings`, `R2StorageAuthSettings`, `MinIOStorageAuthSettings`, `BackblazeB2StorageAuthSettings` | **`S3Settings`** | `flavor: Literal["aws","express","r2","minio","b2"]` |
| `GCSStorageAuthSettings` | **`GCSSettings`** | — |
| `AzureBlobStorageAuthSettings`, `AzureFilesStorageAuthSettings` | **`AzureStorageSettings`** | `service_type: Literal["blob","files"]` |
| `SFTPStorageAuthSettings`, `SSHStorageAuthSettings` | **`SSHSettings`** | — (auth type via `AuthSpec` discriminator: password vs key vs kerberos) |
| `FTPStorageAuthSettings` | **`FTPSettings`** | — |
| `SMBStorageAuthSettings` | **`SMBSettings`** | — |
| `NFSStorageAuthSettings` | **deleted; fold into `LocalSettings`** | `mount_spec` optional field |
| `LocalStorageAuthSettings` | **`LocalSettings`** | — |
| `GitHubStorageAuthSettings` | **`GitHubRepoSettings`** (scope-cut: read-only, repository mode only) | — |

**Net: 15 → 8 classes** (S3, GCS, AzureStorage, SSH, FTP, SMB, Local, GitHubRepo).

### Backend consolidation

The 5 implemented backends (`local`, `s3`, `s3express`, `r2`, `minio`) collapse to 2:
- **`s3/`** — single backend, dispatches on `settings.flavor` for endpoint URL, addressing style, session-auth toggles. Reads MinIO / B2 / R2 specifics from the consolidated `S3Settings`.
- **`local/`** — unchanged.

The storage registry shrinks from 5 entries to 2. `CONST_STORAGE_PROVIDER_TYPE` enum values (`S3`, `S3EXPRESS`, `R2`, `MINIO`, `B2`) all map to the single `S3Settings` class — one class, five public provider-type identifiers preserved for backwards compatibility.

### Package structure

```
src/mountainash_utils_files/settings/
├── __init__.py                    # public re-exports
├── descriptor.py                  # StorageDescriptor(ProfileDescriptor) — adds SDK metadata
├── profile.py                     # StorageProfile(DescriptorProfile) — adds to_driver_kwargs / to_handler_kwargs
├── registry.py                    # STORAGE_REGISTRY = Registry("storage") + bound register/get_descriptor/get_settings_class
├── base.py                        # StorageAuthBase mixin for shared fields (TIMEOUT, RETRIES, ROOT_PATH, etc.)
├── adapters/
│   ├── __init__.py
│   ├── s3.py                      # boto3 kwargs builder with flavor dispatch
│   ├── gcs.py                     # google.cloud.storage kwargs builder
│   ├── azure.py                   # azure.storage.blob + azure.storage.fileshare kwargs builder
│   ├── ssh.py                     # paramiko connect() kwargs builder
│   ├── ftp.py                     # ftplib kwargs builder
│   ├── smb.py                     # smbprotocol kwargs builder
│   ├── local.py                   # pass-through + optional mount resolution
│   └── github.py                  # fsspec GithubFileSystem kwargs builder
├── providers/
│   ├── __init__.py
│   ├── s3_settings.py             # S3Settings + S3_DESCRIPTOR
│   ├── gcs_settings.py
│   ├── azure_settings.py
│   ├── ssh_settings.py
│   ├── ftp_settings.py
│   ├── smb_settings.py
│   ├── local_settings.py
│   └── github_settings.py
└── templates.py                   # (preserved; inline most templates via ParameterSpec.template, keep module for URL-generation helpers)
```

### StorageDescriptor

```python
@dataclass(frozen=True, kw_only=True)
class StorageDescriptor(ProfileDescriptor):
    sdk_package: str                # e.g. "boto3", "google-cloud-storage"
    handler_module: str             # e.g. "mountainash_utils_files.storage_backends.s3"
    handler_class: str              # e.g. "S3StorageBackend"
    supports_streaming: bool = True
    supports_multipart: bool = True
    read_only: bool = False         # GitHub = True
```

### StorageProfile

```python
class StorageProfile(DescriptorProfile):
    def to_handler_kwargs(self) -> dict[str, t.Any]:
        """Build the SDK-client kwargs dict via adapter MRO walk."""
        adapter = type(self).__dict__.get("__adapter__")
        if adapter is None:
            for base in type(self).__mro__[1:]:
                candidate = base.__dict__.get("__adapter__")
                if candidate is not None:
                    adapter = candidate
                    break
        if adapter is not None:
            return adapter(self)
        kwargs = self._default_kwargs()
        kwargs.update(self._auth_kwargs())
        return kwargs
```

### S3Settings (example — full shape)

```python
class S3Settings(StorageProfile, StorageAuthBase):
    __descriptor__ = S3_DESCRIPTOR
    __adapter__ = staticmethod(s3_adapter.build_kwargs)

S3_DESCRIPTOR = StorageDescriptor(
    name="s3",
    provider_type=CONST_STORAGE_PROVIDER_TYPE.S3,
    sdk_package="boto3",
    handler_module="mountainash_utils_files.storage_backends.s3",
    handler_class="S3StorageBackend",
    parameters=[
        ParameterSpec(name="FLAVOR", type=str, default="aws",
                      tier="core", validator=validate_flavor),
        ParameterSpec(name="REGION", type=str, default="us-east-1", tier="core",
                      driver_key="region_name"),
        ParameterSpec(name="BUCKET", type=str, default=None, tier="core"),
        ParameterSpec(name="ENDPOINT_URL", type=t.Optional[str], default=None,
                      tier="advanced", driver_key="endpoint_url",
                      template=None),  # set per-flavor in adapter
        ParameterSpec(name="USE_SSL", type=bool, default=True,  # FIXED: was False
                      tier="advanced", driver_key="use_ssl"),
        ParameterSpec(name="ADDRESSING_STYLE", type=str, default="auto",
                      tier="advanced"),
        # ... dropped: PATH_STYLE (redundant with ADDRESSING_STYLE),
        #              ACCOUNT_ID (not a boto3 param)
    ],
    auth_modes=("iam", "token", "none"),
    metadata={
        "flavor_endpoints": {
            "aws": None,  # boto3 auto-generates
            "express": None,  # SDK auto-detects from bucket name
            "r2": "https://{account_id}.r2.cloudflarestorage.com",
            "minio": None,  # user-provided ENDPOINT_URL required
            "b2": "https://s3.{region}.backblazeb2.com",
        },
    },
)
```

### AuthSpec mapping

| Provider | Allowed AuthSpecs |
|----------|-------------------|
| S3 | `IAMAuth`, `TokenAuth`, `NoAuth` |
| GCS | `ServiceAccountAuth`, `IAMAuth`, `OAuth2Auth`, `TokenAuth`, `NoAuth` |
| AzureStorage | `AzureADAuth`, `TokenAuth`, `PasswordAuth` (shared key), `NoAuth` |
| SSH | `PasswordAuth`, `CertificateAuth` (private key), `KerberosAuth` |
| FTP | `PasswordAuth`, `NoAuth` |
| SMB | `PasswordAuth`, `KerberosAuth` |
| Local | `NoAuth` |
| GitHubRepo | `TokenAuth`, `OAuth2Auth`, `JWTAuth`, `NoAuth` (public repos) |

### Registry + factory

```python
# registry.py
STORAGE_REGISTRY = Registry("storage")
register = STORAGE_REGISTRY.decorator()

def get_descriptor(name: str) -> ProfileDescriptor: ...
def get_settings_class(name: str) -> type[StorageProfile]: ...
```

Factory (`storage_registry/registry.py`) rewired to dispatch via descriptor's `handler_module` + `handler_class` (importlib), matching Phase 3's pattern — replaces the current eager-import dict in `storage_backends/__init__.py`.

## Backwards-compatibility strategy

- `CONST_STORAGE_PROVIDER_TYPE` enum values preserved (all 5 S3-flavors remain distinct identifiers).
- `get_storage_backend(provider_type, auth_params)` signature unchanged; factory resolves `auth_params` class via registry.
- Public `__init__.py` exports unchanged.
- Old provider settings class names (`S3StorageAuthSettings`, `R2StorageAuthSettings`, etc.) added as **thin aliases** to `S3Settings` for downstream-consumer grace period. Removed in a follow-up (Phase 4b) after downstream migrates.
- The 10 currently-unimplemented provider types (`SFTP`, `SSH`, `FTP`, `SMB`, `NFS`, `GCS`, `AZURE_BLOB`, `AZURE_FILES`, `B2`, `GITHUB`) keep their `CONST_STORAGE_PROVIDER_TYPE` entries; settings classes exist; backend implementations remain TBD.

## Template (Pattern B) usage

| Setting | Template | Flavor-gated |
|---------|----------|--------------|
| `S3.ENDPOINT_URL` | `"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"` | `flavor=="r2"` only |
| `AzureStorage.ACCOUNT_URL` | `"https://{ACCOUNT_NAME}.{service_type}.{ENDPOINT_SUFFIX}"` | unconditional |
| `SSH.CONNECTION_URL` | `"ssh://{USERNAME}@{HOST}:{PORT}{ROOT_PATH}"` | unconditional |
| `FTP.CONNECTION_URL` | `"{scheme}://{USERNAME}@{HOST}:{PORT}"` (scheme = `ftps` if TLS else `ftp`) | unconditional |
| `GitHubRepo.CONNECTION_URL` | `"github://{ORG}/{REPO}@{REF}"` | unconditional |

Conditional templates (flavor-gated) use a small adapter-level resolver since `DescriptorProfile.post_init` only handles unconditional template strings. Unconditional ones use `ParameterSpec.template=...` directly.

## Testing strategy

- **`descriptor_invariants_for(STORAGE_REGISTRY)`** pytest class — 10 invariants × 8 descriptors = 80 parametric cases.
- **Per-provider test files** (`test_s3_settings.py`, `test_gcs_settings.py`, etc.) — field validation + auth dispatch + template resolution.
- **S3-family flavor matrix tests** — 5 flavor values × core-field matrix to verify each produces the right adapter kwargs.
- **Migration compatibility tests** — old class names (`S3StorageAuthSettings`) resolve to the same class as `S3Settings`.
- **Backend tests** — existing `tests/backends/test_s3_family.py`, `test_local.py` should pass with minimal changes (dispatch is now via flavor, not provider_type; field access unchanged).

## Risks

1. **Aliased class names risk downstream breakage** — if any downstream consumer does `isinstance(x, S3StorageAuthSettings)` rather than duck-typing. Mitigate with full aliasing (not subclass) so isinstance still passes.
2. **Eager backend imports remove `import minio`** — if the minio package isn't installed, the import chain previously broke loudly. Consolidation to boto3 removes that import; MinIO usage now requires only boto3. (Net improvement: fewer optional deps.)
3. **Template ordering across flavor-gated endpoints** — adapter resolves `ENDPOINT_URL` after `ACCOUNT_ID`/`REGION` in the flavor dispatch; needs explicit ordering in `S3_DESCRIPTOR.parameters`.
4. **GitHub scope-cut** may surprise downstream if anyone uses GITHUB-as-Releases or GITHUB-as-Packages. Grep will be done pre-execution; if found, widen the scope-cut to preserve those modes.
5. **The 10 settings-only providers** (GCS, Azure Blob/Files, SSH/SFTP, FTP, SMB, NFS, B2) get migrated with no backend to validate them end-to-end. Descriptor invariants + unit field tests are the safety net. Accepted risk — the classes currently aren't exercised by any test either.

## Post-merge follow-ups (not in this PR)

- Remove class aliases once downstream migrates (Phase 4b).
- Implement backends for Azure, GCS, SSH, FTP, SMB as needed by consumers.
- If MinIO admin / B2 key-mgmt becomes a requirement, add slim `MinioNativeSettings` / `B2NativeSettings`.
- Principle update in `mountainash-central`: document the acrds-core deferral rationale (see `project_phase5_deferred.md`) and the utils-files consolidation pattern.
