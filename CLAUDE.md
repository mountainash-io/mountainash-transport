# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**mountainash-transport** is a Python package for unified file operations across multiple storage systems — local filesystem, S3 (AWS + R2 + MinIO + B2 + S3 Express via flavor discriminator), Azure Blob/Files, GCS, SFTP/SSH, FTP, SMB, HTTP/HTTPS, and GitHub (read-only). It provides a consistent interface for file operations, path manipulation, and data synchronization across different storage backends.

Settings follow the **profile + auth separation pattern** — see the Settings Architecture section below. Storage profiles implement `StorageProfileProtocol` (`to_handler_kwargs()` + `get_connection_url()`). Authentication is handled externally via `mountainash-auth-client` auth profiles (`IAMAuth`, `TokenAuth`, `PasswordAuth`, `NoAuth`, etc.).

## Architecture

### Core Components

- **StorageFacade**: Unified API class providing consistent file operations across storage backends, with `from_path()` for scheme-driven dispatch and `read()` method for reading bytes
- **StorageBackend (registry)**: Per-provider backend implementations registered against `CONST_STORAGE_PROVIDER_TYPE` values
- **Storage protocols**: 8 granular protocols (Read/Write/List/Delete/Metadata/Copy/Directory/Connection) that backends implement à la carte
- **Profile-driven settings**: Per-provider profile classes that produce SDK-ready kwargs; auth is a separate parameter, not embedded in the profile

### Settings Architecture (profile + auth separation)

**Core types:**
- `ProfileProtocol` — runtime-checkable base Protocol requiring `to_handler_kwargs()` (universal contract for all profile families)
- `StorageProfileProtocol(ProfileProtocol)` — storage refinement adding `get_connection_url()` for diagnostics
- `StorageProfileSpec(ProfileSpec)` — typed metadata (`sdk_package`, `handler_module`, `handler_class`, `supports_streaming`, `supports_multipart`, `read_only`, `default_auth`, `supported_auth`, `implemented`)

**Storage profile classes (in `settings/profiles/`):**

| Profile class | Covers | Discriminator |
|---------------|--------|---------------|
| `S3StorageProfile` | AWS S3, S3 Express, R2, MinIO, B2 | `FLAVOR: Literal["aws","express","r2","minio","b2"]` |
| `GCSStorageProfile` | Google Cloud Storage | — |
| `AzureStorageProfile` | Azure Blob + Azure Files | `SERVICE_TYPE: Literal["blob","files"]` |
| `SFTPStorageProfile` | SFTP (paramiko SFTP subsystem) | — |
| `FTPStorageProfile` | FTP + FTPS | `USE_TLS: bool` |
| `SMBStorageProfile` | SMB | — |
| `LocalStorageProfile` | Local filesystem + NFS/CIFS (pre-mount) | `MOUNT_SPEC: Optional[dict]` |
| `GitHubStorageProfile` | GitHub (read-only, fsspec-backed) | — |
| `HTTPStorageProfile` | HTTP/HTTPS (httpx-based) | — |

**Auth separation:** Authentication is handled by `mountainash-auth-client` auth profiles (`IAMAuth`, `TokenAuth`, `PasswordAuth`, `CertificateAuth`, `KerberosAuth`, `NoAuth`, etc.). Auth profiles are resolved to auth strategies by `resolve_auth_strategy()`, which injects credentials into SDK kwargs. Profiles return SDK config only via `to_handler_kwargs()` — auth is never embedded in the profile.

**Registry + factory:**
- `STORAGE_REGISTRY = Registry("storage", spec_type=StorageProfileSpec, profile_type=StorageProfileProtocol)` — type-constrained registry
- `register = STORAGE_REGISTRY.decorator()` — populates the registry; reads `cls.__spec__`
- `get_spec(name)` / `get_settings_class(name)` lookups

### Connection Architecture (Three Layers)

**Layer 1 — Auth Strategies** (`_core/auth/`): Small objects that inject credentials into SDK client kwargs. One strategy per auth-mode x SDK family.

| Strategy | Auth Profile | SDK family | Injects |
|----------|-------------|------------|---------|
| `NoAuthStrategy` | `NoAuth` / None | Any | passthrough |
| `BearerTokenStrategy` | `TokenAuth`, `JWTAuth`, `OAuth2Auth` | HTTP | `Authorization: Bearer ...` header |
| `BasicAuthStrategy` | `PasswordAuth` | HTTP | `Authorization: Basic ...` header |
| `IAMCredentialStrategy` | `IAMAuth` | AWS | `aws_access_key_id`, `aws_secret_access_key` |
| `OAuth1SignedStrategy` | `OAuth1Auth` | HTTP | authlib `auth=` parameter |
| `SSHPasswordStrategy` | `PasswordAuth` | SSH | `password` kwarg |
| `SSHKeyStrategy` | `CertificateAuth` | SSH | `key_filename` or `pkey` + `passphrase` |
| `SSHKerberosStrategy` | `KerberosAuth` | SSH | `gss_auth`, `gss_kex`, `gss_host` |

`resolve_auth_strategy(auth_profile, provider_type=None)` maps auth profiles to strategies. The `provider_type` parameter (a `CONST_STORAGE_PROVIDER_TYPE` enum) determines which SDK family is targeted — e.g., `PasswordAuth` resolves to `BasicAuthStrategy` for HTTP but `SSHPasswordStrategy` for SSH/SFTP.

**Layer 2 — Connections** (`connections/`): Create authenticated SDK clients from `connect_kwargs: dict` + auth strategy. Leaf connections are decoupled from profiles — the factory extracts kwargs via `profile.to_handler_kwargs()`.

| Connection | Type | Client | Notes |
|-----------|------|--------|-------|
| `HTTPConnection` | leaf | `httpx.Client` | accepts `connect_kwargs: dict` |
| `S3Connection` | leaf | `boto3.client("s3")` | accepts `connect_kwargs: dict`, lazy boto3 import |
| `SSHConnection` | leaf | `paramiko.SSHClient` | accepts `connect_kwargs: dict`, lazy paramiko import |
| `NullConnection` | leaf | `None` | for local filesystem |
| `SFTPConnection` | decorator | `paramiko.SFTPClient` | wraps SSHConnection |
| `TunnelledConnection` | decorator | inner connection's client | local TCP listener through SSH bastion |
| `OAuth2Connection` | decorator | `httpx.Client` | token lifecycle + HTTPConnection |
| `OAuth1Connection` | decorator | `httpx.Client` | OAuth1 signing + HTTPConnection |

- `create_connection(profile, auth_profile)` — factory that accepts `ProfileProtocol`, extracts kwargs, builds the right connection chain
- `create_tunnelled_connection(bastion_profile, bastion_auth, target_profile, target_auth, remote_host, remote_port)` — SSH tunnel factory

**Layer 3 — Backends** (`storage/backends/`): Stateless operation handlers that receive a connected client via a connection object.

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
right-to-left into a `Pipeline`. `StorageFacade.read()` accepts an opt-in `infer=True`
flag that routes through this inference.

```python
from mountainash_transport import StorageFacade, GPG

# Auto-decompress a gzip-encoded file.
facade = StorageFacade.from_path("s3://bucket/data.parquet.gz")
plaintext = facade.read("s3://bucket/data.parquet.gz", infer=True)

# Auto-decrypt-then-decompress. gpg= supplies key material — a .gpg-family
# suffix without an instance raises ValueError.
facade = StorageFacade.from_path("s3://bucket/data.parquet.gz.gpg")
plaintext = facade.read(
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
├── __init__.py                    # Public API re-exports
├── __version__.py
├── _core/                         # Shared foundation (no upward imports)
│   ├── constants.py               # CONST_STORAGE_PROVIDER_TYPE + other enums
│   ├── exceptions.py              # StorageError hierarchy (incl. BackendNotImplementedError)
│   ├── dataclasses/               # FileMetadata
│   ├── protocols.py               # ConnectionProtocol[C] (generic, runtime-checkable)
│   ├── auth/                      # Auth strategies + resolver
│   │   ├── strategies.py          # AuthStrategy protocol + 8 concrete strategies
│   │   └── resolver.py            # resolve_auth_strategy(auth_profile, provider_type)
│   ├── http.py                    # Stub — future shared httpx client factory
│   └── transforms/                # Stream transforms (Pipeline, Gzip, GPG, materialize)
├── connections/                   # Connection infrastructure
│   ├── __init__.py                # create_connection(), create_tunnelled_connection()
│   ├── http.py                    # HTTPConnection (httpx.Client)
│   ├── s3.py                      # S3Connection (boto3.client)
│   ├── ssh.py                     # SSHConnection (paramiko.SSHClient)
│   ├── sftp.py                    # SFTPConnection decorator (paramiko.SFTPClient)
│   ├── tunnel.py                  # TunnelledConnection + _PatchedEndpointProfile
│   ├── null.py                    # NullConnection (local filesystem)
│   ├── errors.py                  # TransportConnectionError hierarchy
│   ├── oauth2/                    # OAuth2Connection + OAuthFlow
│   ├── oauth1/                    # OAuth1Connection + OAuth1Flow
│   └── server/                    # LocalCallbackServer, manual code entry
├── settings/                      # Profile infrastructure (shared between families)
│   ├── profile_protocol.py        # ProfileProtocol + StorageProfileProtocol (runtime-checkable)
│   ├── profile_spec.py            # StorageProfileSpec(ProfileSpec)
│   ├── exceptions.py              # Settings-specific exceptions
│   ├── types.py                   # Type aliases
│   ├── utils/                     # Shared utilities (connection, secrets, security, validation)
│   ├── storage/                   # Storage-specific settings
│   │   ├── registry.py            # STORAGE_REGISTRY
│   │   ├── templates.py           # URL templates
│   │   ├── loader.py              # resolve_storage() (named-profile resolver)
│   │   └── profiles/              # 9 per-provider profile classes
│   └── messaging/                 # Stub — future messaging profiles
└── storage/                       # Request/response family
    ├── protocols/                 # 8 granular protocols (prtcl_*.py)
    ├── backends/                  # Per-provider backend implementations
    │   ├── http/                  # HTTPStorageBackend (httpx — read/write/metadata)
    │   ├── local/                 # LocalStorageBackend (all 8 protocols)
    │   ├── s3/                    # S3StorageBackend (flavor-dispatched)
    │   └── sftp/                  # SFTPStorageBackend (read/write/list/delete/metadata)
    ├── facade/                    # StorageFacade, from_path(), cross_backend, read/write
    ├── path_helpers/              # StoragePath, SchemeSpec, suffixes, S3 helpers
    └── registry/                  # get_storage_backend, get_registered_backends, detect_provider_from_path
```

### Test Structure

```
tests/
├── conftest.py
├── test_public_api.py                          # Public API surface tests
├── _core/
│   ├── test_constants_and_exceptions.py        # Constants + exception hierarchy
│   ├── test_connection_protocol.py             # ConnectionProtocol conformance
│   └── auth/                                   # Auth strategy + resolver tests
│       ├── test_auth_strategies.py             # HTTP/S3 strategies
│       ├── test_ssh_strategies.py              # SSH strategies (Password, Key, Kerberos)
│       ├── test_auth_resolver.py               # Resolver (HTTP/S3 dispatch)
│       ├── test_resolver_ssh.py                # Resolver (SSH-family dispatch)
│       └── test_iam_strategy.py                # IAMCredentialStrategy
├── connections/                                # Connection lifecycle tests
│   ├── test_http_connection.py                 # HTTPConnection
│   ├── test_s3_connection.py                   # S3Connection
│   ├── test_ssh_connection.py                  # SSHConnection
│   ├── test_sftp_connection.py                 # SFTPConnection decorator
│   ├── test_tunnel_connection.py               # TunnelledConnection + _PatchedEndpointProfile
│   ├── test_null_connection.py                 # NullConnection
│   ├── test_factory.py                         # create_connection() + create_tunnelled_connection()
│   └── oauth2/, oauth1/                        # OAuth connection tests
├── cross_backend/                              # Cross-backend integration tests
├── path_helpers/                               # StoragePath, SchemeSpec, suffixes, S3 path
├── settings/
│   ├── test_profile_protocol.py
│   ├── test_profile_spec.py
│   └── profiles/                               # Per-provider profile tests (9 files)
├── storage/backends/                           # Per-backend unit tests
│   ├── test_http.py                            # HTTPStorageBackend
│   ├── test_local.py                           # LocalStorageBackend
│   ├── test_s3.py                              # S3StorageBackend
│   └── test_sftp.py                            # SFTPStorageBackend
├── storage_facade/                             # Facade, from_path, read/write, infer
├── storage_protocols/                          # Protocol conformance + shapes + registry completeness
├── storage_registry/                           # Registry + backend detection
└── storage_transforms/                         # Pipeline, Gzip, GPG, materialize, facade integration
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
- **httpx>=0.27**: HTTP client for HTTP/HTTPS storage backend

### Optional Dependencies
- **S3** `[s3]`: boto3, s3fs, minio (boto3 now in `[s3]` extra)
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
- **SFTP/SSH**: SFTPStorageBackend via paramiko — read, write, list, delete, metadata. SSHConnection as general-purpose leaf, SFTPConnection decorator, TunnelledConnection for SSH port forwarding
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
from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile
from mountainash_transport.settings.storage.profiles.local_storage_profile import LocalStorageProfile
from mountainash_auth_client import IAMAuth, NoAuth

# Profiles return SDK config only — no auth embedded
s3_profile = S3StorageProfile(FLAVOR="aws", REGION="us-east-1", BUCKET="mybucket")
kwargs = s3_profile.to_handler_kwargs()  # → {"region_name": "us-east-1", ...}

# R2: endpoint auto-derived from ACCOUNT_ID
r2_profile = S3StorageProfile(FLAVOR="r2", ACCOUNT_ID="abc123")

# Local filesystem
local_profile = LocalStorageProfile(ROOT_PATH="/data")
```

### Connection-driven workflow

```python
from mountainash_transport import (
    create_connection, create_tunnelled_connection,
    SSHConnection, SFTPConnection, TunnelledConnection,
)
from mountainash_auth_client import PasswordAuth, CertificateAuth, IAMAuth

# SSH/SFTP: create_connection() builds SSHConnection → SFTPConnection chain
conn = create_connection(ssh_profile, auth_profile=PasswordAuth(USERNAME="u", PASSWORD="p"))
conn.connect()
sftp_client = conn.client  # → paramiko.SFTPClient

# SSH tunnel to an internal HTTP API via bastion
tunnel = create_tunnelled_connection(
    bastion_profile=bastion_ssh_profile,
    bastion_auth=CertificateAuth(PRIVATE_KEY_PATH="/path/to/key"),
    target_profile=http_profile,
    target_auth=None,
    remote_host="internal-api",
    remote_port=8080,
)
tunnel.connect()
httpx_client = tunnel.client  # → httpx.Client routed through SSH tunnel
```

### Storage facade read/write operations

```python
from mountainash_transport import StorageFacade
from mountainash_auth_client import TokenAuth

# Facade from a path — provider inferred from the URL scheme
facade = StorageFacade.from_path("s3://bucket/key")

# With auth
facade = StorageFacade.from_path(
    "https://example.com/file.txt",
    auth_profile=TokenAuth(TOKEN="..."),
)

# Read bytes from any recognised scheme
payload = StorageFacade.from_path("s3://bucket/data.parquet").read("s3://bucket/data.parquet")
html = StorageFacade.from_path("https://example.com/page.html").read("https://example.com/page.html")
local = StorageFacade.from_path("/tmp/local-file").read("/tmp/local-file")
```

## Versioning Strategy

Uses CalVer (Calendar Versioning) with semantic versioning:
- Format: `YYYY.MM.MICRO`
- Release candidate: `YYYY.MM.0`
- Production: `YYYY.MM.1`
- Patches: `YYYY.MM.X`

## License
MIT License
