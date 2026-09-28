# mountainash-transport

![Python](https://img.shields.io/badge/python-3.12%2B-blue) ![Category](https://img.shields.io/badge/category-utils-purple) ![Tests](https://img.shields.io/badge/tests-✓-green) ![Docs](https://img.shields.io/badge/docs-✓-blue)

Unified file operations across multiple storage systems. Read, write, list, copy, and delete files with a consistent API regardless of whether the data lives on local disk, S3, Azure, GCS, SFTP, HTTP, or any other supported backend.
Requires Python 3.12 or later.

> CI's development rehearsal verifies transport with checked-out settings, secrets, and auth-client packages. A separate opt-in `verify_public=true` manual run uses only public PyPI dependencies and performs no upload when `release=false` and `publish=false`; it may correctly fail until siblings are public. Publication requires that gate, and post-publication installation accepts no local dependency. See [RELEASE.md](RELEASE.md) and the [shared release procedures](https://github.com/mountainash-io/mountainash-central/blob/main/05.devops/releases/shared/README.md).

## Features

- **Consistent API** — `StorageFacade` provides the same read/write/list/delete/copy/metadata interface across all backends
- **Scheme-driven dispatch** — `StorageFacade.from_path("s3://bucket/key")` infers the provider from the URL scheme
- **8 granular protocols** — backends implement Connection, Read, Write, List, Delete, Metadata, Copy, and Directory à la carte
- **Stream transforms** — composable `Pipeline` of `Gzip` and `GPG` transforms for compression and encryption
- **Suffix-aware inference** — `StorageFacade.from_path("s3://bucket/data.parquet.gz").read("s3://bucket/data.parquet.gz", infer=True)` auto-decompresses based on file extensions
- **Profile + auth separation** — storage configuration (profile) and authentication (auth profile) are independent concerns
- **Three-layer connections** — auth strategies inject credentials, connections create SDK clients, backends are stateless operations
- **SSH tunnelling** — `TunnelledConnection` routes any backend through an SSH bastion via local TCP forwarding

## Supported Storage Backends

| Backend | Provider types | Protocols |
|---------|---------------|-----------|
| **Local** | `LOCAL` | Connection, Read, Write, List, Delete, Metadata, Copy, Directory |
| **S3** | `S3`, `S3EXPRESS`, `R2`, `MINIO` | Connection, Read, Write, List, Delete, Metadata, Copy |
| **HTTP/HTTPS** | `HTTP` | Read, Write, Metadata |
| **Azure** | Blob, Files | Via profile (not yet backend-implemented) |
| **GCS** | Google Cloud Storage | Via profile (not yet backend-implemented) |
| **SSH/SFTP** | `SSH` | Read, Write, List, Delete, Metadata |
| **FTP** | FTP, FTPS | Via profile (not yet backend-implemented) |
| **SMB** | SMB | Via profile (not yet backend-implemented) |
| **GitHub** | GitHub repos (read-only) | Via profile (not yet backend-implemented) |

## Installation

Requires Python **3.12+**, `mountainash-settings>=0.1.0,<0.2`, and
`mountainash-auth-client>=0.1.0,<0.2`.

The coordinated development baseline is **0.1.0**. Hatch selects sibling source
checkouts for development and CI. Record source commits and artifact hashes for
verification; matching version numbers alone do not identify artifacts.

```bash
pip install mountainash-transport

# With optional extras
pip install mountainash-transport[s3]        # s3fs, minio
pip install mountainash-transport[gcs]       # google-cloud-storage, gcsfs
pip install mountainash-transport[azure]     # azure-storage-blob, adlfs
pip install mountainash-transport[sftp]      # paramiko, smart-open[ssh]
pip install mountainash-transport[encryption] # python-gnupg
pip install mountainash-transport[all]       # everything
```

## Quick Start

```python
from mountainash_transport import StorageFacade

# Read from any supported scheme
facade = StorageFacade.from_path("s3://my-bucket/data.parquet")
data = facade.read("s3://my-bucket/data.parquet")
page = StorageFacade.from_path("https://example.com/page.html").read("https://example.com/page.html")
local = StorageFacade.from_path("/tmp/local-file.csv").read("/tmp/local-file.csv")

# Facade for richer operations
facade = StorageFacade.from_path("s3://my-bucket/prefix/")
files = facade.list_files("s3://my-bucket/prefix/")
facade.copy("s3://my-bucket/src.txt", "s3://my-bucket/dst.txt")

# Stream transforms — auto-decompress based on suffix
plaintext = StorageFacade.from_path("s3://bucket/data.parquet.gz").read("s3://bucket/data.parquet.gz", infer=True)

# Explicit pipeline
from mountainash_transport import Pipeline, Gzip
facade.write("s3://bucket/out.gz", data, pipeline=Pipeline(Gzip()))

# SSH/SFTP connection
from mountainash_transport import create_connection
from mountainash_auth_client import PasswordAuth

conn = create_connection(ssh_profile, auth_profile=PasswordAuth(USERNAME="user", PASSWORD="pass"))
conn.connect()
# conn.client is a paramiko.SFTPClient — ready for file operations
```

## Named Profiles

Use `resolve_storage()` to load named profiles from configuration:

```python
from mountainash_transport import resolve_storage, StorageFacade

profile, auth = resolve_storage("lake")           # from MOUNTAINASH_PROFILES_CONFIG
facade = StorageFacade.from_path("s3://my-lake/x.parquet", profile, auth_profile=auth)
data = facade.read("s3://my-lake/x.parquet")
```

### Explicit configuration reader

For example, `profiles.yaml` can select an S3 profile and an IAM credential:

```yaml
storage_profiles:
  lake:
    provider: s3
    parameters:
      BUCKET: my-lake
      REGION: ap-southeast-2
    auth:
      mode: iam
      parameters:
        ACCESS_KEY_ID: example-access-key
        SECRET_ACCESS_KEY: "secret:aws.secret_key"
```

Select a reader at the application boundary. Here the application has provisioned
an `aws` record containing a `secret_key` field in its private config-record root:

```python
from pathlib import Path
from mountainash_settings import SettingsParameters
from mountainash_settings.secrets import FilesystemBackend
from mountainash_transport import resolve_storage, StorageFacade

with FilesystemBackend(Path("/private/config-records")) as config_reader:
    params = SettingsParameters.create(
        config_files=["profiles.yaml"], secret_store=config_reader,
    )
    profile, auth = resolve_storage("lake", settings_parameters=params)
    facade = StorageFacade.from_path(
        "s3://my-lake/x.parquet", storage_profile=profile, auth_profile=auth,
    )
    data = facade.read("s3://my-lake/x.parquet")
```

A `secret:` reference requires the selected reader; missing records and failed
lookups are errors, with no provider-name or environment-store fallback. Literal
resolved strings beginning with `secret:` remain a deferred reserved-prefix case.

### Separate managed HTTP OAuth token store

Managed OAuth uses a raw token store, independently of the configuration reader.
The application supplies `provider` and `oauth_auth`; the latter supplies client
credentials and `persist_key()` for the managed OAuth lifecycle.

```python
from pathlib import Path
from mountainash_settings.secrets import FilesystemBackend
from mountainash_transport import StorageFacade
from mountainash_transport.settings.storage.profiles.http_storage_profile import HTTPStorageProfile

with FilesystemBackend(Path("/private/oauth-records")) as tokens:
    facade = StorageFacade.from_path(
        "https://example.test/data", storage_profile=HTTPStorageProfile(),
        auth_profile=oauth_auth, oauth_provider=provider, token_store=tokens,
    )
    data = facade.read("https://example.test/data")
```

Pass the raw store: auth-client applies its OAuth namespace once. Transport
borrows both stores; the application keeps them open until all operations finish
and owns closure. Ordinary local/no-auth use requires neither store:

```python
data = StorageFacade.from_path("/tmp/local-file.csv").read("/tmp/local-file.csv")
```

## Development

```bash
# Build
hatch build

# Run tests
hatch run test:test

# Run tests with coverage
hatch run test:cov

# Lint
hatch run ruff:check
hatch run ruff:fix    # auto-fix

# Type check
hatch run mypy:check

# Single test
pytest tests/path/to/test_file.py::TestClass::test_function -v
```

## Documentation

- **[CLAUDE.md](CLAUDE.md)** — Architecture, settings, and development guide
- **[Mountain Ash Documentation](https://mountainash-io.github.io/mountainash-docs/)** — Complete ecosystem documentation

## Branch Strategy

- `main` — production releases (CalVer `YY.MM.MICRO`)
- `develop` — integration branch for development
- `feature/*`, `bugfix/*`, `hotfix/*` — work branches targeting `develop`

## License

See LICENSE file for details.

## Mountain Ash Ecosystem

This package is part of the [Mountain Ash](https://github.com/mountainash-io) ecosystem of Python packages.
