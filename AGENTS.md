# AGENTS.md

Guidance for coding agents working in this repository.

## Project Overview

**mountainash-transport** provides unified file operations across storage systems — local filesystem, S3 (AWS + R2 + MinIO + B2 + S3 Express via flavor discriminator), SFTP and HTTP/HTTPS — behind one facade, with path manipulation, cross-backend copy and stream transforms (gzip/GPG). Azure Blob/Files, GCS, FTP, SMB and GitHub (read-only) have settings profiles only; they have no backend yet and raise `BackendNotImplementedError`.

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

This repo keeps no planning documents (specs, plans, backlog) in `docs/`; user documentation such as `docs/typing.md` is fine. Update the central indexes in the same change that adds a record, following `mountainash-central/_meta/superpowers-index-conventions.md`.

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
|`LocalStorageProfile`|Local filesystem (`ROOT_PATH` confines)|`ROOT_PATH: Optional[str]`|
|`GitHubRepoStorageProfile`|GitHub repository (read-only; registry key `github_repo`)|—|
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

- **Protocols** (`storage/protocols/prtcl_*.py`): granular capabilities (Read/Write/Enumerate/Delete/Metadata/Copy/Directory/RangedRead, plus `ConnectionProtocol` in `_core`) implemented à la carte. `RangedReadProtocol` is satisfied structurally by an `open_ranged` method; no mixin subclasses it.
- **Backends** (`storage/backends/`): stateless handlers receiving a connected client — `http` (read/write/metadata/ranged read), `local` (all but ranged read; random mode uses the native file handle), `s3` (flavor-dispatched; all but directory), `sftp` (all but copy). `tests/storage/protocols/test_backend_conformance.py` asserts the seven core protocols (it has no RangedRead column or B2 row yet). GCS, Azure, FTP, SMB and GitHub profiles have no backend yet (`BackendNotImplementedError`). The root README's support matrix must match `get_registered_backends()`. Every backend package must import on a base install: SDKs and `[http]`-stack modules are imported inside functions (`tests/test_slim_install.py` blocks every non-base import).
- **Facade** (`storage/facade/`): `StorageFacade`, `from_path()` scheme dispatch, `read()`, `cross_backend` copy.
- **Registry** (`storage/registry/`): `get_storage_backend`, `get_registered_backends`, `detect_provider_from_path`.
- **Path helpers** (`storage/path_helpers/`): `StoragePath`, suffixes, S3 paths. The scheme registry (`SchemeSpec`, `SCHEMES`) lives in `_schemes.py`; `location.py` owns confinement.

### Stream transforms (`_core/transforms/`)

- `Pipeline(outer, ..., inner)` — order matches file-extension order (last-applied = outermost); the same instance serves read and write, the facade picks direction.
- `Gzip(level=6, mtime=0)` — stdlib, reproducible by default. `GPG(...)` — needs the `[encryption]` extra.
- `StorageFacade.read/read_stream/write/write_stream` take keyword-only `pipeline=`; `copy_between` takes `source_pipeline=` / `destination_pipeline=`.
- `materialize(stream, to=...)` — opt-in buffering to recover a known length.
- `infer_pipeline(path, gpg=..., gzip=...)` / `facade.read(..., infer=True)` — read-only suffix inference (`.gz`/`.gzip` → `Gzip`; `.gpg`/`.asc`/`.pgp` → `GPG`, requires a `gpg=` instance). Parsing stops at the first unknown suffix. No write-side inference.

### Read access modes

`read_stream(access="sequential" | "random" | "buffered")` defaults to native
forward-only remote streams. Random mode uses `RangedReadProtocol` on HTTP/S3/SFTP
and native local handles; buffered mode materializes decoded bytes in memory.
`RangePolicy` precedence is call → profile `RANGE_*` fields → readahead/1 MiB.
See `docs/read-access-modes.md` for migration, error timing and Parquet tuning.

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
hatch run mypy:check                      # mypy 1.10.1 over src + tests, --warn-unused-ignores
hatch run mypy:qualify --output <new-dir-outside-checkouts>  # installed py.typed qualification
hatch build
```

Typing: the package ships `py.typed`; see [docs/typing.md](docs/typing.md) for the
contract and dynamic boundaries. Keep the full `src` + `tests` mypy target; no blanket
ignores. Storage profiles declare their spec-generated fields under `if t.TYPE_CHECKING:`;
`tests/settings/storage/profiles/test_static_field_declarations.py` fails if they drift
from `__spec__`. Public typing changes need a matching `tests/typing/consumer.py` contract.

## Dependencies

Declared in `pyproject.toml` — treat it as the source of truth for versions.

- Core: `typing-extensions` only — local files and `LocationPolicy`.
- Extras: `[http]` (settings, auth-client, pydantic, universal_pathlib, httpx, fsspec — remote storage, profiles, connections); `[s3]`, `[gcs]`, `[azure]`, `[sftp]`, `[oauth1]` (each includes `[http]`); `[encryption]`; `[all]`. Missing extras raise `MissingExtraError` (`_core/extras.py`).

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
