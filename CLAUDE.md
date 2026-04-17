# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**mountainash-utils-files** is a Python package for unified file operations across multiple storage systems — local filesystem, S3 (AWS + R2 + MinIO + B2 + S3 Express via flavor discriminator), Azure Blob/Files, GCS, SFTP/SSH, FTP, SMB, and GitHub (read-only). It provides a consistent interface for file operations, path manipulation, and data synchronization across different storage backends.

Settings follow the **descriptor-driven profiles pattern** (Phase 4, 2026-04-17) — see the Settings Architecture section below. Configuration uses upstream `mountainash_settings.profiles.DescriptorProfile` + typed `AuthSpec` discriminated union from `mountainash_settings.auth`.

## Architecture

### Core Components

- **StorageFacade**: Unified API class providing consistent file operations across storage backends
- **StorageBackend (registry)**: Per-provider backend implementations registered against `CONST_STORAGE_PROVIDER_TYPE` values
- **Storage protocols**: Read/Write/List/Delete/Metadata/Copy/Directory/Connection protocols that backends implement à la carte
- **Descriptor-driven settings**: Consolidated settings classes (see next section) that produce SDK-ready kwargs via per-provider adapters

### Settings Architecture (descriptor-driven)

Settings follow the Mountain Ash Phase 4 descriptor pattern:

**Base classes:**
- `StorageProfile(DescriptorProfile)` — generic mechanism inherited from `mountainash_settings.profiles`; adds `to_handler_kwargs()` that walks MRO for an `__adapter__`
- `StorageAuthBase(MountainAshBaseSettings)` — shared-fields mixin (TIMEOUT, ROOT_PATH, CREATE_PATH, USERNAME, PASSWORD, etc.)
- `StorageDescriptor(ProfileDescriptor)` — typed metadata (`sdk_package`, `handler_module`, `handler_class`, `supports_streaming`, `supports_multipart`, `read_only`)

**Consolidated provider classes (15 legacy → 8):**

| Settings class | Replaces | Discriminator |
|----------------|----------|---------------|
| `S3Settings` | S3, S3Express, R2, MinIO, Backblaze B2 | `FLAVOR: Literal["aws","express","r2","minio","b2"]` |
| `GCSSettings` | GCS | — |
| `AzureStorageSettings` | Azure Blob + Azure Files | `SERVICE_TYPE: Literal["blob","files"]` |
| `SSHSettings` | SSH + SFTP (same paramiko connect) | — (auth type via AuthSpec) |
| `FTPSettings` | FTP + FTPS | `USE_TLS: bool` |
| `SMBSettings` | SMB | — |
| `LocalSettings` | Local + NFS/CIFS (pre-mount) | `MOUNT_SPEC: Optional[dict]` |
| `GitHubRepoSettings` | GitHub (scope-cut: read-only, fsspec-backed) | — |

Legacy class names (`S3StorageAuthSettings`, `R2StorageAuthSettings`, …, `NFSStorageAuthSettings`, `GitHubStorageAuthSettings`) were aliased during Phase 4 and removed in Phase 4b. Downstream callers must use the new consolidated class names + discriminator fields.

**Registry + factory:**
- `STORAGE_REGISTRY = Registry("storage")` — descriptor registry for lookup by name
- `@register(DESCRIPTOR)` decorator populates the registry
- `get_descriptor(name)` / `get_settings_class(name)` lookups
- Typed `AuthSpec` discriminated union — `auth: Union[IAMAuth, TokenAuth, ServiceAccountAuth, AzureADAuth, PasswordAuth, CertificateAuth, KerberosAuth, OAuth2Auth, JWTAuth, NoAuth]` (per-provider subset via `auth_modes` in descriptor)

**Pattern B (declarative templates):**
- `ParameterSpec.template` auto-resolves composite fields (e.g. Azure `ACCOUNT_URL` from `ACCOUNT_NAME` + `ENDPOINT_SUFFIX`; S3 R2 endpoint URL from `ACCOUNT_ID`)

### Package Structure

```
src/mountainash_utils_files/
├── __init__.py                    # Public API (StorageFacade, registry, protocols, constants)
├── __version__.py
├── constants.py                   # CONST_STORAGE_PROVIDER_TYPE, CONST_STORAGE_AUTH_METHOD
├── dataclasses/                   # FileMetadata
├── exceptions.py                  # StorageError hierarchy
├── path_helpers/
├── storage_backends/              # Backend implementations
│   ├── __init__.py                # Imports trigger @register_storage_backend
│   ├── local/                     # LocalStorageBackend
│   └── s3/                        # S3StorageBackend (flavor-dispatched — serves AWS/Express/R2/MinIO/B2)
├── storage_facade/                # StorageFacade + cross_backend utilities
├── storage_protocols/             # 8 granular protocols
├── storage_registry/              # get_storage_backend + provider detection
└── settings/
    ├── __init__.py                # StorageAuthBase, exceptions, templates
    ├── descriptor.py              # StorageDescriptor(ProfileDescriptor)
    ├── profile.py                 # StorageProfile(DescriptorProfile)
    ├── registry.py                # STORAGE_REGISTRY = Registry("storage")
    ├── base.py                    # StorageAuthBase mixin (shared fields)
    ├── templates.py               # Legacy URL templates (most inlined as ParameterSpec.template)
    ├── adapters/                  # Per-SDK kwargs builders (lazy SDK imports)
    │   ├── s3.py                  # boto3 kwargs — flavor dispatch
    │   ├── gcs.py                 # google-cloud-storage kwargs
    │   ├── azure.py               # azure.storage.{blob,fileshare} kwargs
    │   ├── ssh.py                 # paramiko.SSHClient.connect kwargs
    │   ├── ftp.py                 # ftplib.FTP / FTP_TLS kwargs
    │   ├── smb.py                 # smbprotocol Session kwargs
    │   ├── local.py               # pass-through + optional mount_spec
    │   └── github.py              # fsspec.GithubFileSystem kwargs
    └── providers/                 # Shell classes + descriptor literals + 15 legacy aliases
        ├── s3_settings.py
        ├── gcs_settings.py
        ├── azure_settings.py
        ├── ssh_settings.py
        ├── ftp_settings.py
        ├── smb_settings.py
        ├── local_settings.py
        └── github_settings.py
```

### Test Structure

```
tests/
├── test_data_storage.py        # FileInterface functionality tests
└── test_path_utils.py          # PathHelper functionality tests
```


## Build/Test/Lint Commands
- Build: `hatch build`
- Lint: `hatch run ruff:check` or `hatch run ruff:fix` to auto-fix
- Tests: `hatch run test:test` or `hatch run test:cov` for coverage
- Single test: `pytest tests/path/to/test_file.py::TestClass::test_function -v`
- Type check: `hatch run mypy:check`

## Dependencies

### Core Dependencies
- **pandas>=2.2.0**: Data manipulation and analysis
- **polars==1.16.0**: Fast DataFrame library for data processing
- **pydantic==2.9.2**: Data validation and settings management
- **pydantic-settings==2.6.1**: Settings management with Pydantic
- **universal_pathlib==0.2.2**: Universal path library for different storage systems
- **pyarrow==17.0.0**: Apache Arrow columnar data format
- **boltons==24.0.0**: Collection of over 230 BSD-licensed utilities
- **minio==7.2.7**: High-performance object storage SDK
- **boto3==1.34.136**: AWS SDK for Python
- **smart-open[all]==7.0.4**: Utils for streaming large files
- **lxml>=4.5.0**: XML and HTML processing library
- **xsdata[lxml]>=24.4**: XML data binding library

### Optional Dependencies
- **S3**: boto3, s3fs, minio
- **GCS**: google-cloud-storage, gcsfs
- **Azure**: azure-storage-blob, adlfs
- **SFTP**: paramiko, smart-open[ssh]
- **Encryption**: gnupg, python-gnupg

### Internal Mountain Ash Dependencies
- **mountainash-settings**: Configuration and authentication management
- **mountainash-constants**: Shared constants and enumerations
- **mountainash-utils-gpg**: GPG encryption utilities
- **mountainash-utils-ssh**: SSH connection utilities

### Development Dependencies
- pytest==8.3.5
- pytest-check, pytest-cov, pytest-mock
- ruff==0.3.7
- mypy==1.10.1
- radon==6.0.1

## GitHub Actions Workflows

### Testing
- **python-run-pytest.yml**: Runs unit tests on pull requests, supports Python 3.12
- **python-run-ruff.yml**: Code linting and formatting checks
- **python-run-radon.yml**: Complexity analysis and code quality metrics
- **main-release-branch-validation.yml**: Validates release branch requirements

### Release Process
- **build-and-release-package.yml**: Automated release workflow
- **main-release-build-dependencies.yml**: Builds and validates dependencies
- Supports production, RC, and beta releases
- Generates SBOMs (Software Bill of Materials)
- Creates releases in GitHub and mountainash-wheels repository

### Branch Strategy
- `main`: Production releases (only release/* and hotfix/* branches)
- `develop`: Development and RC releases
- `feature/*`, `bugfix/*`, `hotfix/*`: Feature branches
- Protected branches require code owner approval (@discreteds)

## Code Style Guidelines
- Formatting: Uses ruff for formatting and linting
- Imports: Standard lib first, third-party next, project imports last
- Types: Use typing annotations (e.g., `import typing as t`) for all functions
- Naming: CamelCase for classes, snake_case for functions/variables, UPPER_CASE for constants
- Error handling: Use ValueError for validation errors, custom exceptions for specific cases
- Documentation: Use Google-style docstrings for classes and methods
- Organization: Follow modular design with clear separation of concerns
- Testing: Create unit tests with appropriate markers (unit, integration, performance)

## Development Environments

### Hatch Environments
- `default`: Local development
- `test`: Local testing with extended pytest plugins
- `test_github`: GitHub Actions testing
- `build_github`: GitHub Actions building
- `ruff`: Linting and formatting
- `radon`: Complexity analysis
- `mypy`: Type checking

## Key Features

### Unified File Operations
- **Cross-platform compatibility**: Works with local, cloud, and remote storage
- **Consistent API**: Same interface regardless of storage backend
- **Stream-based operations**: Efficient handling of large files
- **Path-to-path copying**: Direct transfers between different storage systems
- **Compression and encryption**: Built-in support for gzip compression and GPG encryption

### Storage System Support
- **Local filesystem**: Native file operations
- **AWS S3**: Standard and S3 Express support
- **Cloudflare R2**: R2-specific optimizations
- **Google Cloud Storage**: Native GCS operations
- **Azure Blob Storage**: Azure-specific implementations
- **SFTP/SSH**: Secure file transfer protocols

### Advanced Capabilities
- **File synchronization**: Orchestrated sync between storage systems
- **Metadata handling**: Rich file metadata support
- **Connection management**: Automatic connection pooling and management
- **Error handling**: Comprehensive error handling and retries
- **Authentication**: Integration with mountainash-settings for secure auth

## Usage Examples

### Descriptor-driven settings (Phase 4)

```python
from mountainash_utils_files.settings.providers import (
    S3Settings, AzureStorageSettings, SSHSettings, LocalSettings,
)
from mountainash_settings.auth import IAMAuth, AzureADAuth, PasswordAuth, NoAuth

# S3-family: single class discriminated by FLAVOR
s3 = S3Settings(FLAVOR="aws", REGION="us-east-1", BUCKET="mybucket",
                auth=IAMAuth(access_key_id="AKIA...", secret_access_key="..."))
r2 = S3Settings(FLAVOR="r2", ACCOUNT_ID="abc123",  # endpoint auto-derived
                auth=IAMAuth(access_key_id="...", secret_access_key="..."))
kwargs = s3.to_handler_kwargs()  # → dict ready for boto3.client("s3", **kwargs)

# Azure: single class discriminated by SERVICE_TYPE
blob = AzureStorageSettings(SERVICE_TYPE="blob", ACCOUNT_NAME="myaccount",
                            auth=AzureADAuth(tenant_id="...", client_id="...",
                                             client_secret="..."))
files = AzureStorageSettings(SERVICE_TYPE="files", ACCOUNT_NAME="myaccount",
                             auth=AzureADAuth(...))

# SSH / SFTP: same class — caller picks subsystem
ssh = SSHSettings(HOST="example.com", USERNAME="user",
                  auth=PasswordAuth(username="user", password="..."))

# Local (+ NFS/CIFS pre-mount)
local = LocalSettings(ROOT_PATH="/data", auth=NoAuth())
nfs = LocalSettings(ROOT_PATH="/mnt/nfs", auth=NoAuth(),
                    MOUNT_SPEC={"mount_type": "nfs", "server": "nfs.example.com",
                                "export_path": "/exports/data"})

# Legacy class names (S3StorageAuthSettings, R2StorageAuthSettings, etc.)
# were removed in Phase 4b. Migrate to the consolidated class + FLAVOR field.
```

### Storage facade (unchanged public API)
```python
from mountainash_utils_files import StorageFacade
from mountainash_utils_files.storage_registry import get_storage_backend

backend = get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3, auth_params=s3)
facade = StorageFacade(provider_type="s3", auth_params=s3)
# ... use facade for cross-backend operations
```

## Versioning Strategy

Uses CalVer (Calendar Versioning) with semantic versioning:
- Format: `YYYY.MM.MICRO`
- Release candidate: `YYYY.MM.0`
- Production: `YYYY.MM.1`
- Patches: `YYYY.MM.X`

## License
MIT License
