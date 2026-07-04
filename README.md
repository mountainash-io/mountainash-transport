# mountainash-transport

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![Category](https://img.shields.io/badge/category-utils-purple) ![Tests](https://img.shields.io/badge/tests-✓-green) ![Docs](https://img.shields.io/badge/docs-✓-blue)

Unified file operations across multiple storage systems. Read, write, list, copy, and delete files with a consistent API regardless of whether the data lives on local disk, S3, Azure, GCS, SFTP, HTTP, or any other supported backend.

## Features

- **Consistent API** — `StorageFacade` provides the same read/write/list/delete/copy/metadata interface across all backends
- **Scheme-driven dispatch** — `StorageFacade.from_path("s3://bucket/key")` infers the provider from the URL scheme
- **8 granular protocols** — backends implement Connection, Read, Write, List, Delete, Metadata, Copy, and Directory à la carte
- **Stream transforms** — composable `Pipeline` of `Gzip` and `GPG` transforms for compression and encryption
- **Suffix-aware inference** — `read_bytes("s3://bucket/data.parquet.gz", infer=True)` auto-decompresses based on file extensions
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
