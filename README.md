# mountainash-transport

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
[![License: Proprietary](https://img.shields.io/badge/license-proprietary-lightgrey)](LICENSE)

One file API across storage systems: read, write, stream, list, copy and delete
on local disk, S3-compatible stores, SFTP and HTTP(S) with the same calls. The
path's scheme selects the backend. Stores are described by storage profiles;
credentials come separately from `mountainash-auth-client` auth profiles.

[Examples](examples/) · [Agent and architecture guide](AGENTS.md) ·
[Release process](RELEASE.md)

## What it provides

| Area | Capabilities | Explore |
|---|---|---|
| File operations | `StorageFacade` read/write/stream, metadata, delete, copy and directories; capability checks before calling | [Files](examples/#files) |
| Stream transforms | Composable `Pipeline` of `Gzip` and `GPG`; opt-in suffix inference on read; transforms applied during cross-backend copy | [Stream transforms](examples/#stream-transforms) |
| Read access modes | Native sequential streams, cached remote byte ranges, or explicit in-memory buffering; Parquet tuning guidance | [Read access modes and migration](docs/read-access-modes.md) |
| Path dispatch | Scheme-to-provider detection, aliases, strict normalisation and joining | [Paths](examples/#paths) |
| Profiles and auth | Per-provider storage profiles emitting SDK kwargs; auth profiles paired and validated at connection time; named profiles from configuration | [Profiles and authentication](examples/#profiles-and-authentication) |
| HTTP transport | `HttpRequestEngine` with retry, timeout and redirect policies and typed errors | [HTTP](examples/#http) |
| Connections | SSH, SFTP and S3 connections; SSH tunnelling to reach internal services through a bastion | [AGENTS.md](AGENTS.md#connections) |

## Supported storage

Operations follow the backend's capability protocols; unsupported calls raise
`UnsupportedOperationError`.

| Provider | Path schemes | Read | Write | Metadata | Delete | Copy | Directories | Prefix listing |
|---|---|---|---|---|---|---|---|---|
| Local filesystem | bare paths, `file://` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | |
| S3, S3 Express, R2, MinIO, B2 | `s3://`, `r2://`, … | ✓ | ✓ | ✓ | ✓ | ✓ | | ✓ |
| SFTP | `sftp://` | ✓ | ✓ | ✓ | ✓ | | ✓ | |
| HTTP/HTTPS | `http://`, `https://` | ✓ | ✓ | ✓ | | | | |

Azure Blob/Files, GCS, FTP/FTPS, SMB and GitHub have storage profiles and
recognised schemes but no backend yet: constructing a facade for them raises
`BackendNotImplementedError`.

## Installation

Requires **Python 3.12+**, **Pydantic 2.10+**, `mountainash-settings` 0.1 and
`mountainash-auth-client` 0.1.

This README describes the **0.1.0 development baseline**. Until the sibling
packages are published, install development checkouts side by side:

```bash
git clone --branch develop https://github.com/mountainash-io/mountainash-transport.git
cd mountainash-transport
python -m pip install -e ".[s3]"
```

| Extra | Adds |
|---|---|
| `[s3]` | boto3, s3fs, minio |
| `[sftp]` | paramiko, smart-open[ssh] |
| `[encryption]` | python-gnupg (for `GPG`) |
| `[oauth1]` | authlib |
| `[gcs]`, `[azure]` | SDKs for the pending GCS and Azure backends |
| `[all]` | all of the above |

## Quick start

Save this as `quickstart.py` and run it with `python quickstart.py`:

```python
import tempfile
from pathlib import Path

from mountainash_transport import Gzip, StorageFacade

with tempfile.TemporaryDirectory() as root:
    path = str(Path(root) / "sales.csv.gz")
    with StorageFacade.from_path(path) as storage:  # bare path -> local backend
        storage.write(path, b"region,total\nnorth,120\n", pipeline=Gzip())
        text = storage.read(path, infer=True).decode()  # .gz suffix -> gunzip
        print(f"{storage.get_size(path)} bytes stored; first row: {text.splitlines()[1]}")
```

Output:

```text
43 bytes stored; first row: north,120
```

`from_path()` picks the backend from the scheme, so the same calls work with
`s3://reports/2026/sales.csv.gz` once a profile and credentials are supplied.

## Connecting to remote stores

Pass a storage profile and an auth profile. Profiles never embed credentials:

```python
from mountainash_auth_client import IAMAuthProfile
from mountainash_transport import StorageFacade
from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile

profile = S3StorageProfile(FLAVOR="aws", REGION="ap-southeast-2", BUCKET="reports")
auth = IAMAuthProfile(ROLE_ARN="arn:aws:iam::123456789012:role/reports-reader")
with StorageFacade.from_path("s3://reports/2026/sales.csv", profile, auth_profile=auth) as storage:
    data = storage.read("s3://reports/2026/sales.csv")
```

The pairing is validated against the profile's supported auth modes before any
connection opens ([auth compatibility](examples/auth_compatibility/)).

### Named profiles and secret references

`resolve_storage(name)` materialises `(storage_profile, auth_profile)` from the
`storage_profiles` section of the file named by `MOUNTAINASH_PROFILES_CONFIG`, or
from explicit settings parameters ([named profiles](examples/named_profiles/)).
Reference credentials with `secret:<record>.<field>` and select a reader at the
application boundary:

```python
from pathlib import Path
from mountainash_settings import SettingsParameters
from mountainash_settings.secrets import FilesystemBackend
from mountainash_transport import StorageFacade, resolve_storage

with FilesystemBackend(Path("/private/config-records")) as config_reader:
    params = SettingsParameters.create(config_files=["profiles.yaml"], secret_store=config_reader)
    profile, auth = resolve_storage("lake", settings_parameters=params)
    with StorageFacade.from_path(
        "s3://reports/2026/sales.csv", profile, auth_profile=auth,
    ) as storage:
        data = storage.read("s3://reports/2026/sales.csv")
```

A `secret:` reference requires the selected reader; missing records and failed
lookups are errors, with no provider-name or environment fallback.

### Managed HTTP OAuth

HTTP and HTTPS use default connection settings when no storage profile is supplied:

```python
from mountainash_transport import StorageFacade

url = "https://files.example.com/data.csv"
with StorageFacade.from_path(url) as storage:
    data = storage.read(url)
```

You can also pass `auth_profile=` without a storage profile. Supply an explicit
`HTTPStorageProfile` to customize timeouts, headers, or other HTTP settings.

Managed OAuth2 uses a raw token store, separate from the configuration reader.
The application supplies the OAuth provider and auth profile; auth-client owns
token acquisition and refresh:

```python
from pathlib import Path
from mountainash_settings.secrets import FilesystemBackend
from mountainash_transport import StorageFacade
from mountainash_transport.settings.storage.profiles.http_storage_profile import HTTPStorageProfile

with FilesystemBackend(Path("/private/oauth-records")) as tokens:
    with StorageFacade.from_path(
        "https://files.example.com/data", HTTPStorageProfile(),
        auth_profile=oauth_auth, oauth_provider=provider, token_store=tokens,
    ) as storage:
        data = storage.read("https://files.example.com/data")
```

Transport borrows both stores; the application keeps them open until all
operations finish and owns closure.

## Storage errors and strict queries

Implemented Local, S3-family, SFTP and HTTP backends translate their own I/O
failures into public exceptions, retaining the native exception as `__cause__`.
The same contract applies when reading, fetching ranges or closing an opened
stream—not only when opening it.

| Condition | Exception |
|---|---|
| Missing resource | `PathNotFoundError` |
| Missing, invalid or expired credentials | `AuthenticationError` |
| Access denied | `PermissionDeniedError` |
| Connection or timeout failure | `StorageConnectionError` |
| Other backend I/O/service failure | `StorageError` |

`PermissionDeniedError` subclasses `AuthenticationError`: existing broad auth
handlers still work. Catch permission denial **before** authentication failure
when distinguishing them. Denial does not prove credentials are valid; an S3
HEAD denial also does not prove an object is absent. Existing specialised
errors such as `ObjectChangedError` retain their identity and causes.

**Query migration:** `exists(path)` returns `False` only for established absence.
It now raises on denied access or operational failure instead of disguising
those failures as absence. `get_size(path)` returns `None` only after successful
access with unknown size; zero is valid. Missing size queries raise
`PathNotFoundError`, including on Local. S3 object queries use HEAD without a
denied-HEAD fallback to prefix listing; bucket-root checks retain LIST behavior.

Caller input, invalid arguments, transform/decoder failures and cancellation
are not reclassified as backend failures. A failed write may leave partial
data; error mapping does not add rollback or retries. Stream cleanup ordering
and ownership remain unchanged. boto3 managed uploads may close seekable caller
inputs. Paramiko 3.4.0 suppresses some native final-close failures internally;
transport translates escaping errors, not failures hidden by the SDK.

## Connection lifetime

A facade owns the connection it creates. Use `with StorageFacade.from_path(...)`
or call `close()` explicitly. Close is terminal: later I/O and context re-entry
raise `StorageConnectionError`; `supports()` remains available. Repeated close is
harmless, including after a cleanup failure. No reliable GC cleanup is promised.

Close sequential/random remote streams before their facade. Closing a stream
does not close its reusable facade; fully buffered results are independent and
remain readable after facade close. `copy_between()` borrows both facades and
requires both to be open; it never closes them. Token stores remain caller-owned.

Construction and context-body errors remain primary if cleanup also fails;
cleanup failures are attached as exception notes. Explicit close reports cleanup
failure after attempting remaining owned cleanup. A failed native close is not
retried by another close call.

Connection objects themselves remain explicitly reconnectable. `connect()`
releases a previous native client before replacing it; if release fails, that
attempt raises without creating a replacement. A later explicit connect may
succeed. SFTP exclusively owns its SSH connection: normal close and failed
startup release both, while successful channel replacement reuses healthy SSH.

Tunnel disconnect closes its inner connection, listener, accepted sockets and
SSH connection before waiting for workers. Serving and request workers share a
one-second wait budget; expiry raises `ConnectionTimeoutError` after those cleanup
attempts. This bounds worker waiting, not SDK close calls, and cannot kill an
arbitrarily stuck thread. Background channel/socket cleanup failures are reported
to the owner, or attached as notes when a body/startup error or timeout is primary.


## Learn more

Explore the [storage recipes](examples/): each runs offline and independently,
using the same small dataset.

| Guide | Contents |
|---|---|
| [AGENTS.md](AGENTS.md) | Architecture, package map, commands and conventions |
| [TESTING.md](TESTING.md) | Test layout and markers |
| [RELEASE.md](RELEASE.md) | Release rehearsal, public-dependency gate and publication |

Design principles, backlog, specs and plans live in
[mountainash-central](https://github.com/mountainash-io/mountainash-central)
under `mountainash-transport`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Branch from `develop`; PRs target
`develop`. Run `hatch run test:test` and `hatch run ruff:check` before opening one.

Part of the [Mountain Ash ecosystem](https://github.com/mountainash-io), alongside
`mountainash-settings`, `mountainash-auth-client`, `mountainash-files`,
`mountainash-data` and `mountainash`. Authentication models and OAuth flows belong
to `mountainash-auth-client`.

## License

Proprietary — see [LICENSE](LICENSE).
