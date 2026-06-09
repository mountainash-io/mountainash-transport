# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**mountainash-transport** is a Python package for unified file operations across multiple storage systems — local filesystem, S3 (AWS + R2 + MinIO + B2 + S3 Express via flavor discriminator), Azure Blob/Files, GCS, SFTP/SSH, FTP, SMB, HTTP/HTTPS, and GitHub (read-only). It provides a consistent interface for file operations, path manipulation, and data synchronization across different storage backends.

Settings follow the **profile + auth separation pattern** — see the Settings Architecture section below. Storage profiles implement `StorageProfileProtocol` (`to_handler_kwargs()` + `get_connection_url()`). Authentication is handled externally via `mountainash-auth-client` auth profiles (`IAMAuth`, `TokenAuth`, `PasswordAuth`, `NoAuth`, etc.).

## Architecture

### Core Components

- **StorageFacade**: Unified API class providing consistent file operations across storage backends, with `from_path()` for scheme-driven dispatch and `read_bytes()` convenience function
- **StorageBackend (registry)**: Per-provider backend implementations registered against `CONST_STORAGE_PROVIDER_TYPE` values
- **Storage protocols**: 8 granular protocols (Read/Write/List/Delete/Metadata/Copy/Directory/Connection) that backends implement à la carte
- **Profile-driven settings**: Per-provider profile classes that produce SDK-ready kwargs; auth is a separate parameter, not embedded in the profile

### Settings Architecture (profile + auth separation)

**Core types:**
- `StorageProfileProtocol` — runtime-checkable Protocol requiring `to_handler_kwargs(auth_profile=...)` and `get_connection_url()`
- `StorageProfileSpec(ProfileSpec)` — typed metadata (`sdk_package`, `handler_module`, `handler_class`, `supports_streaming`, `supports_multipart`, `read_only`, `default_auth`, `supported_auth`)

**Storage profile classes (in `settings/profiles/`):**

| Profile class | Covers | Discriminator |
|---------------|--------|---------------|
| `S3StorageProfile` | AWS S3, S3 Express, R2, MinIO, B2 | `FLAVOR: Literal["aws","express","r2","minio","b2"]` |
| `GCSStorageProfile` | Google Cloud Storage | — |
| `AzureStorageProfile` | Azure Blob + Azure Files | `SERVICE_TYPE: Literal["blob","files"]` |
| `SSHStorageProfile` | SSH + SFTP (paramiko) | — |
| `FTPStorageProfile` | FTP + FTPS | `USE_TLS: bool` |
| `SMBStorageProfile` | SMB | — |
| `LocalStorageProfile` | Local filesystem + NFS/CIFS (pre-mount) | `MOUNT_SPEC: Optional[dict]` |
| `GitHubStorageProfile` | GitHub (read-only, fsspec-backed) | — |
| `HTTPStorageProfile` | HTTP/HTTPS (httpx-based) | — |

**Auth separation:** Authentication is handled by `mountainash-auth-client` auth profiles (`IAMAuth`, `TokenAuth`, `PasswordAuth`, `NoAuth`, etc.). Auth profiles are passed to `to_handler_kwargs(auth_profile=...)` rather than being embedded in the storage profile. Backends accept `auth_profile` as a separate constructor parameter.

**Registry + factory:**
- `STORAGE_REGISTRY = Registry("storage", spec_type=StorageProfileSpec, profile_type=StorageProfileProtocol)` — type-constrained registry
- `register = STORAGE_REGISTRY.decorator()` — populates the registry; reads `cls.__spec__`
- `get_spec(name)` / `get_settings_class(name)` lookups

### Stream Transforms

Facade-level stream decorators for compression and encryption (restored 2026-04-17, spec at `docs/superpowers/specs/2026-04-17-stream-transforms-design.md`).

- `storage_transforms/Pipeline(outer, ..., inner)` — ordered stack matching file-extension order (last-applied = outermost).
- `Gzip(level=6, mtime=0)` — stdlib-based, reproducible by default, zero new dependency.
- `GPG(recipients=[...], gnupghome=..., ...)` — requires the `[encryption]` optional extra (python-gnupg).
- `StorageFacade.read/read_stream/write/write_stream` accept a keyword-only `pipeline=` argument.
- `copy_between` accepts separate `source_pipeline=` and `destination_pipeline=` arguments.
- `storage_transforms.util.materialize(stream, to=...)` — opt-in buffering to recover a known length.

The same `Pipeline` instance is used on both read and write paths; the facade applies transforms in the correct direction automatically.

### Suffix-Aware Transform Inference (Phase 6, 2026-04-18)

`infer_pipeline(path, gpg=..., gzip=...)` parses a path's suffix chain
right-to-left into a `Pipeline`. `read_bytes` accepts an opt-in `infer=True`
flag that routes through this inference.

```python
from mountainash_transport import read_bytes, GPG

# Auto-decompress a gzip-encoded file.
plaintext = read_bytes("s3://bucket/data.parquet.gz", infer=True)

# Auto-decrypt-then-decompress. gpg= supplies key material — a .gpg-family
# suffix without an instance raises ValueError.
plaintext = read_bytes(
    "s3://bucket/data.parquet.gz.gpg",
    infer=True,
    gpg=GPG(gnupghome="/path/to/keyring"),
)
```

Baseline suffix map: `.gz`/`.gzip` → `Gzip`, `.gpg`/`.asc`/`.pgp` → `GPG`.
Parsing stops at the first unknown suffix, so `data.parquet.gz.gpg` yields
`Pipeline(GPG, Gzip)` and a stripped path of `data.parquet`. Write-side
inference is intentionally not provided — writes take an explicit
`pipeline=` argument.

### Package Structure

```
src/mountainash_transport/
├── __init__.py                    # Public API (StorageFacade, read_bytes, protocols, constants, transforms)
├── __version__.py
├── constants.py                   # CONST_STORAGE_PROVIDER_TYPE + other storage enums
├── dataclasses/                   # FileMetadata
├── exceptions.py                  # StorageError hierarchy
├── path_helpers/                  # Parse + normalize storage paths (scheme-aware)
│   ├── __init__.py                # StoragePath, SchemeSpec, SCHEMES, infer_pipeline
│   ├── scheme.py                  # SchemeSpec + SCHEMES registry
│   ├── storage_path.py            # StoragePath helper class
│   ├── suffixes.py                # Suffix-aware transform inference
│   └── s3.py                      # s3_bucket, s3_key free functions
├── storage_backends/              # Backend implementations
│   ├── __init__.py                # Imports trigger backend registration
│   ├── http/                      # HTTPStorageBackend (httpx — read/write/metadata for http:// + https://)
│   ├── local/                     # LocalStorageBackend (connection/read/write/list/delete/metadata/copy/directory)
│   └── s3/                        # S3StorageBackend (flavor-dispatched — serves AWS/Express/R2/MinIO/B2)
├── storage_facade/                # StorageFacade, from_path(), cross_backend, read_bytes
├── storage_protocols/             # 8 granular protocols (prtcl_*.py)
├── storage_registry/              # get_storage_backend, detect_provider_from_path, backend_detection
├── storage_transforms/            # Stream transforms (Pipeline, Gzip, GPG, materialize)
└── settings/
    ├── __init__.py                # Exceptions + StorageAuthTemplates
    ├── exceptions.py              # Settings-specific exceptions
    ├── profile_protocol.py        # StorageProfileProtocol (runtime-checkable)
    ├── profile_spec.py            # StorageProfileSpec(ProfileSpec)
    ├── registry.py                # STORAGE_REGISTRY = Registry("storage")
    ├── loader.py                  # load_storage() — config-driven materialisation (WIP)
    ├── templates.py               # URL templates
    ├── types.py                   # Type aliases
    ├── utils/                     # Shared utilities (connection, secrets, security, validation)
    └── profiles/                  # Per-provider profile classes
        ├── s3_storage_profile.py
        ├── gcs_storage_profile.py
        ├── azure_storage_profile.py
        ├── ssh_storage_profile.py
        ├── ftp_storage_profile.py
        ├── smb_storage_profile.py
        ├── local_storage_profile.py
        ├── github_storage_profile.py
        └── http_storage_profile.py
```

### Test Structure

```
tests/
├── conftest.py
├── test_public_api.py                          # Public API surface tests
├── test_constants_and_exceptions.py            # Constants + exception hierarchy
├── cross_backend/                              # Cross-backend integration tests
│   ├── test_delete.py, test_list.py
│   ├── test_metadata.py, test_read_write.py
├── path_helpers/                               # StoragePath, SchemeSpec, suffixes, S3 path
│   ├── test_s3.py, test_scheme.py
│   ├── test_storage_path.py, test_suffixes.py
├── settings/
│   ├── profiles/                               # Per-provider profile tests (9 files)
│   ├── test_profile_protocol.py
│   ├── test_profile_spec.py
│   └── test_registry.py
├── storage_backends/                           # Per-backend unit tests
│   ├── test_http.py, test_local.py, test_s3.py
├── storage_facade/                             # Facade, from_path, read_bytes, infer
│   ├── test_facade.py, test_facade_infer.py
│   ├── test_from_path.py, test_read_bytes.py
│   └── test_read_bytes_infer.py
├── storage_protocols/                          # Protocol conformance + shapes
│   ├── test_backend_conformance.py             # Data-driven: EXPECTED_PROTOCOLS + EXCLUDED_PROTOCOLS
│   ├── test_protocol_shapes.py
│   └── test_registry_completeness.py
├── storage_registry/                           # Registry + backend detection
│   ├── test_backend_detection.py, test_registry.py
└── storage_transforms/                         # Pipeline, Gzip, GPG, materialize, facade integration
    ├── test_base.py, test_gzip.py, test_gpg.py
    ├── test_pipeline.py, test_materialize.py
    └── test_facade_integration.py
```


## Build/Test/Lint Commands
- Build: `hatch build`
- Lint: `hatch run ruff:check` or `hatch run ruff:fix` to auto-fix
- Tests: `hatch run test:test` or `hatch run test:cov` for coverage
- Single test: `pytest tests/path/to/test_file.py::TestClass::test_function -v`
- Type check: `hatch run mypy:check`

## Dependencies

### Core Dependencies
- **pydantic==2.9.2**: Data validation and settings management
- **pydantic-settings==2.6.1**: Settings management with Pydantic
- **universal_pathlib==0.2.2**: Universal path library for different storage systems
- **boto3>=1.29.4,<=1.34.113**: AWS SDK for Python (upper-bounded for Taipy compat)
- **httpx>=0.27**: HTTP client for HTTP/HTTPS storage backend

### Optional Dependencies
- **S3** `[s3]`: s3fs, minio
- **GCS** `[gcs]`: google-cloud-storage, gcsfs
- **Azure** `[azure]`: azure-storage-blob, adlfs
- **SFTP** `[sftp]`: paramiko, smart-open[ssh]
- **Encryption** `[encryption]`: python-gnupg

### Internal Mountain Ash Dependencies
- **mountainash-settings**: Profile and registry infrastructure
- **mountainash-auth-client**: Auth profiles (IAMAuth, TokenAuth, PasswordAuth, NoAuth, etc.)

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
- **AWS S3**: Standard and S3 Express support (with configurable connect/read timeouts)
- **Cloudflare R2**: R2-specific optimizations
- **Google Cloud Storage**: Native GCS operations
- **Azure Blob Storage**: Azure-specific implementations
- **SFTP/SSH**: Secure file transfer protocols
- **HTTP/HTTPS**: Read, write (PUT), and metadata via httpx — supports Bearer and Basic auth

### Advanced Capabilities
- **File synchronization**: Orchestrated sync between storage systems
- **Metadata handling**: Rich file metadata support
- **Connection management**: Automatic connection pooling and management
- **Error handling**: Comprehensive error handling and retries
- **Authentication**: Integration with mountainash-settings for secure auth

## Usage Examples

### Profile + auth separation

```python
from mountainash_transport.settings.profiles.s3_storage_profile import S3StorageProfile
from mountainash_transport.settings.profiles.local_storage_profile import LocalStorageProfile
from mountainash_auth_client import IAMAuth, TokenAuth, NoAuth

# S3-family: single class discriminated by FLAVOR
s3_profile = S3StorageProfile(FLAVOR="aws", REGION="us-east-1", BUCKET="mybucket")
auth = IAMAuth(ACCESS_KEY_ID="AKIA...", SECRET_ACCESS_KEY="...")
kwargs = s3_profile.to_handler_kwargs(auth_profile=auth)  # → dict ready for boto3.client("s3", **kwargs)

# R2: endpoint auto-derived from ACCOUNT_ID
r2_profile = S3StorageProfile(FLAVOR="r2", ACCOUNT_ID="abc123")

# Local filesystem
local_profile = LocalStorageProfile(ROOT_PATH="/data")
```

### Storage facade and read_bytes

```python
from mountainash_transport import StorageFacade, read_bytes
from mountainash_auth_client import TokenAuth

# Facade from a path — provider inferred from the URL scheme
facade = StorageFacade.from_path("s3://bucket/key")

# With auth
facade = StorageFacade.from_path(
    "https://example.com/file.txt",
    auth_profile=TokenAuth(TOKEN="..."),
)

# One-liner that reads bytes from any recognised scheme
payload = read_bytes("s3://bucket/data.parquet")
html = read_bytes("https://example.com/page.html")
local = read_bytes("/tmp/local-file")
```

### Storage backend registry

```python
from mountainash_transport.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.storage_registry import get_storage_backend
from mountainash_auth_client import IAMAuth

auth = IAMAuth(ACCESS_KEY_ID="...", SECRET_ACCESS_KEY="...")
backend = get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3, profile, auth_profile=auth)
```

## Versioning Strategy

Uses CalVer (Calendar Versioning) with semantic versioning:
- Format: `YYYY.MM.MICRO`
- Release candidate: `YYYY.MM.0`
- Production: `YYYY.MM.1`
- Patches: `YYYY.MM.X`

## License
MIT License
