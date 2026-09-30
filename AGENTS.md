# AGENTS.md

Guidance for coding agents working in this repository.

## Project Overview

**mountainash-transport** provides unified file operations across storage systems — local filesystem, S3 (AWS + R2 + MinIO + B2 + S3 Express via flavor discriminator), Azure Blob/Files, GCS, SFTP/SSH, FTP, SMB, HTTP/HTTPS and GitHub (read-only) — behind one facade, with path manipulation, cross-backend copy and stream transforms (gzip/GPG).

Settings follow the **profile + auth separation pattern**: storage profiles return SDK config only; credentials come from `mountainash-auth-client` auth profiles and are emitted at connection time.

## mountainash-central (MANDATORY)

Principles, backlog, specs and plans for this package live in the sibling **mountainash-central** repo (`../mountainash-central`). This file routes there; it does not restate that content. Read the actual documents — not summaries or memory.

| What | Where |
|------|-------|
| Design principles (governance, statuses, precedence) | [01.principles/mountainash-transport/PRINCIPLES.md](../mountainash-central/01.principles/mountainash-transport/PRINCIPLES.md) and the `a.architecture/`, `b.protocols/`, `c.api-design/` directories beside it |
| Planning entry (all collections) | [04.planning/mountainash-transport/README.md](../mountainash-central/04.planning/mountainash-transport/README.md) |
| Backlog | [04.planning/mountainash-transport/a.backlog/INDEX.md](../mountainash-central/04.planning/mountainash-transport/a.backlog/INDEX.md) |
| Specs and plans index | [04.planning/mountainash-transport/superpowers/INDEX.md](../mountainash-central/04.planning/mountainash-transport/superpowers/INDEX.md) |
| Cross-package principles | [01.principles/README.md](../mountainash-central/01.principles/README.md) |

### Read principles before

- Architectural decisions (layer boundaries, dispatch, composition)
- Adding or changing storage protocols, backends, profiles or the registry
- Changing the facade surface, path entry points, cross-backend operations or suffix inference
- Resolving design tensions or trade-offs

### Specs & plans location

Save new superpowers specs and plans to mountainash-central, not this repo:

- **Specs:** `mountainash-central/04.planning/mountainash-transport/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- **Plans:** `mountainash-central/04.planning/mountainash-transport/superpowers/plans/YYYY-MM-DD-<topic>.md`

This repo has no `docs/` planning folder; do not create one. Update the central indexes in the same change that adds a record, following `mountainash-central/_meta/superpowers-index-conventions.md`.

### Central documentation workflow

- Edit central docs only in the primary `../mountainash-central` checkout, on `main`; commit directly. No docs branches, worktrees or PRs.
- A code branch/worktree here does not change where docs go.
- Stage and commit only the docs owned by the current task; never stash, reset or overwrite another session's work there.

## Architecture

Package-local map. The *why* behind each layer lives in the central principles.

### Settings (profile + auth separation)

- `ProfileProtocol` — runtime-checkable base requiring `to_handler_kwargs()`.
- `StorageProfileProtocol(ProfileProtocol)` — adds `get_connection_url()` for diagnostics.
- `StorageProfileSpec(ProfileSpec)` — typed metadata (`sdk_package`, `handler_module`, `handler_class`, `supports_streaming`, `supports_multipart`, `read_only`, `default_auth`, `supported_auth`, `implemented`).
- `STORAGE_REGISTRY` (`settings/storage/registry.py`) — type-constrained registry; `register = STORAGE_REGISTRY.decorator()` reads `cls.__spec__`; `get_spec(name)` / `get_settings_class(name)`.
- `resolve_storage()` (`settings/storage/loader.py`) — named-profile resolver.

|Profile class|Covers|Discriminator|
|---|---|---|
|`S3StorageProfile`|AWS S3, S3 Express, R2, MinIO, B2|`FLAVOR: Literal["aws","express","r2","minio","b2"]`|
|`GCSStorageProfile`|Google Cloud Storage|—|
|`AzureStorageProfile`|Azure Blob + Azure Files|`SERVICE_TYPE: Literal["blob","files"]`|
|`SFTPStorageProfile`|SFTP (paramiko)|—|
|`FTPStorageProfile`|FTP + FTPS|`USE_TLS: bool`|
|`SMBStorageProfile`|SMB|—|
|`LocalStorageProfile`|Local filesystem + NFS/CIFS (pre-mount)|`MOUNT_SPEC: Optional[dict]`|
|`GitHubStorageProfile`|GitHub (read-only, fsspec-backed)|—|
|`HTTPStorageProfile`|HTTP/HTTPS (httpx)|—|

### Connections

**Credential emission is owned by `mountainash-auth-client`.** `create_connection(profile, auth_profile)` validates the auth mode against `spec.supported_auth`, maps the provider to an auth-client `TargetFamily`, then builds kwargs via `profile.emit(family)` (or `to_handler_kwargs()`) layered with `auth_profile.emit(family, base=...)`. For BOTO with `ROLE_ARN`/`PROFILE_NAME` it builds a Session-instruction envelope consumed by `S3Connection` (assume-role only for `aws`/`express`). OAuth flows and callback servers are imported from `mountainash_auth_client.oauth`; `connections/auth_strategy.py` only adapts auth-client's `OAuth2TokenManager` to the HTTP engine's refreshable-auth seam.

|Connection|Type|Client|
|---|---|---|
|`HTTPConnection`|leaf|`httpx.Client`|
|`S3Connection`|leaf|`boto3.client("s3")` (lazy import)|
|`SSHConnection`|leaf|`paramiko.SSHClient` (lazy import)|
|`NullConnection`|leaf|`None` (local filesystem)|
|`SFTPConnection`|decorator|`paramiko.SFTPClient` over `SSHConnection`|
|`TunnelledConnection`|decorator|inner connection's client via SSH bastion listener|

`create_tunnelled_connection(bastion_profile, bastion_auth, target_profile, target_auth, remote_host, remote_port)` builds the tunnel chain.

### Storage

- **Protocols** (`storage/protocols/prtcl_*.py`): granular capabilities (Read/Write/Enumerate/Delete/Metadata/Copy/Directory, plus `ConnectionProtocol` in `_core`) implemented à la carte.
- **Backends** (`storage/backends/`): stateless handlers receiving a connected client — `http` (read/write/metadata), `local` (all but enumerate), `s3` (flavor-dispatched; all but directory), `sftp` (read/write/delete/metadata/directory). Other profiled providers have no backend yet (`BackendNotImplementedError`). The root README's support matrix must match `get_registered_backends()`.
- **Facade** (`storage/facade/`): `StorageFacade`, `from_path()` scheme dispatch, `read()`, `cross_backend` copy.
- **Registry** (`storage/registry/`): `get_storage_backend`, `get_registered_backends`, `detect_provider_from_path`.
- **Path helpers** (`storage/path_helpers/`): `StoragePath`, `SchemeSpec`, suffixes, S3 paths.

### Stream transforms (`_core/transforms/`)

- `Pipeline(outer, ..., inner)` — order matches file-extension order (last-applied = outermost); the same instance serves read and write, the facade picks direction.
- `Gzip(level=6, mtime=0)` — stdlib, reproducible by default. `GPG(...)` — needs the `[encryption]` extra.
- `StorageFacade.read/read_stream/write/write_stream` take keyword-only `pipeline=`; `copy_between` takes `source_pipeline=` / `destination_pipeline=`.
- `materialize(stream, to=...)` — opt-in buffering to recover a known length.
- `infer_pipeline(path, gpg=..., gzip=...)` / `facade.read(..., infer=True)` — read-only suffix inference (`.gz`/`.gzip` → `Gzip`; `.gpg`/`.asc`/`.pgp` → `GPG`, requires a `gpg=` instance). Parsing stops at the first unknown suffix. No write-side inference.

### Package structure

```
src/mountainash_transport/
├── __init__.py            # Public API re-exports
├── _core/                 # Shared foundation (no upward imports)
│   ├── constants.py       # CONST_STORAGE_PROVIDER_TYPE + other enums
│   ├── exceptions.py      # StorageError hierarchy (incl. BackendNotImplementedError)
│   ├── protocols.py       # ConnectionProtocol[C]
│   ├── dataclasses/       # FileMetadata
│   ├── http/              # HTTP engine: policy, response, errors, auth protocol
│   └── transforms/        # Pipeline, Gzip, GPG, materialize
├── connections/           # create_connection(), leaf + decorator connections, errors
├── settings/              # ProfileProtocol, StorageProfileSpec, utils
│   └── storage/           # registry, loader, profiles/ (9 profile classes)
├── messaging/             # Stub — future messaging family
└── storage/               # protocols, backends, facade, path_helpers, registry
```

Tests mirror `src/` under `tests/` (`_core/`, `connections/`, `settings/`, `storage/`) plus top-level public-API, lazy-import, installed-contract and release-provenance tests. `tests/examples/` runs every `examples/*/example.py` against its README's expected output and executes the root README quick start; a new recipe needs an index row in `examples/README.md`.

## Commands

```bash
hatch run test:test                       # Full suite with coverage
hatch run test:test-quick                 # No coverage
hatch run test:test-target-quick <path>   # Specific file/test
hatch run ruff:check                      # Lint (ruff:fix to auto-fix)
hatch build
```

## Dependencies

Declared in `pyproject.toml` — treat it as the source of truth for versions.

- Core: `mountainash-settings`, `mountainash-auth-client`, `pydantic`, `universal_pathlib`, `httpx`.
- Extras: `[s3]`, `[gcs]`, `[azure]`, `[sftp]`, `[encryption]`, `[oauth1]`, `[all]`.

## Code Style

- Ruff for lint; imports stdlib → third-party → project.
- `import typing as t`; annotate all functions.
- CamelCase classes, snake_case functions/variables, UPPER_CASE constants and profile fields.
- `ValueError` for validation; custom exceptions at boundaries.
- Google-style docstrings.
- Test markers: `unit`, `integration`, `performance`.

## Git Flow

`feature/*` | `bugfix/*` | `hotfix/*` → `develop` → `release/*` → `main` + CalVer tag. PRs target `develop`; never push directly to `develop` or `main`.

## Usage

```python
from mountainash_transport import StorageFacade, create_connection
from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile
from mountainash_auth_client import TokenAuthProfile

s3_profile = S3StorageProfile(FLAVOR="aws", REGION="us-east-1", BUCKET="mybucket")
r2_profile = S3StorageProfile(FLAVOR="r2", ACCOUNT_ID="abc123")  # endpoint derived

facade = StorageFacade.from_path("https://example.com/file.txt", auth_profile=TokenAuthProfile(TOKEN="..."))
payload = facade.read("https://example.com/file.txt")
```
