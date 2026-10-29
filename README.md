# mountainash-transport

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

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
| Path dispatch | Scheme-to-provider detection and suffix inference on a base install; aliases, strict normalisation and joining (`StoragePath`) with `[http]` | [Paths](examples/#paths) |
| Profiles and auth | Per-provider storage profiles emitting SDK kwargs; auth profiles paired and validated at connection time; named profiles from configuration | [Profiles and authentication](examples/#profiles-and-authentication) |
| HTTP transport | `HttpRequestEngine` with retry, timeout and redirect policies and typed errors | [HTTP](examples/#http) |
| Connections | SSH, SFTP and S3 connections; SSH tunnelling to reach internal services through a bastion | [AGENTS.md](AGENTS.md#connections) |

## Supported storage

Operations follow the backend's capability protocols; unsupported calls raise
`UnsupportedOperationError`.

| Provider | Path schemes | Read | Write | Metadata | Delete | Copy | Directories | Object enumeration |
|---|---|---|---|---|---|---|---|---|
| Local filesystem | bare paths, `file://` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Yes |
| S3, S3 Express, R2, MinIO, B2 | `s3://`, `r2://`, … | ✓ | ✓ | ✓ | ✓ | ✓ | | ✓ |
| SFTP | `sftp://` | ✓ | ✓ | ✓ | ✓ | | ✓ | Yes |
| HTTP/HTTPS | `http://`, `https://` | ✓ | ✓ | ✓ | | | | |

Azure Blob/Files, GCS, FTP/FTPS, SMB and GitHub have storage profiles and
recognised schemes but no backend yet: constructing a facade for them raises
`BackendNotImplementedError`.

## Installation

Requires **Python 3.12+**. The base install has no runtime dependency beyond
`typing-extensions` and covers local files and `LocationPolicy`. Remote storage
and storage profiles need `[http]` (included by every backend extra); without it
they raise `MissingExtraError` naming the extra.

This README describes the **0.1.0 development baseline**. Until the sibling
packages are published, install development checkouts side by side:

```bash
git clone --branch develop https://github.com/mountainash-io/mountainash-transport.git
cd mountainash-transport
python -m pip install -e ".[s3]"
```

| Extra | Adds |
|---|---|
| `[http]` | mountainash-settings, mountainash-auth-client, pydantic, universal_pathlib, httpx, fsspec — HTTP/HTTPS, storage profiles, connections |
| `[s3]` | `[http]` + boto3, s3fs, minio |
| `[sftp]` | `[http]` + paramiko, smart-open[ssh] |
| `[encryption]` | python-gnupg (for `GPG`) |
| `[oauth1]` | `[http]` + authlib |
| `[gcs]`, `[azure]` | `[http]` + SDKs for the pending GCS and Azure backends |
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

Gzip decoding is bounded. `Gzip(max_decompressed_bytes=...)` defaults to 1 GiB
of decoded output. Reading or seeking past the limit raises `TransformError`
before the excess bytes are held in memory, which protects against decompression
bombs. For trusted data, pass a larger value, or `None` to remove the bound,
for example `storage.read(path, infer=True, gzip=Gzip(max_decompressed_bytes=None))`.

## Write parent directories

`write()` and `write_stream()` accept keyword-only `create_parents=True`,
including when a `pipeline` is supplied:

```python
storage.write(path, data, create_parents=False)
storage.write_stream(path, source, pipeline=Gzip(), create_parents=False)
```

- **Local and SFTP:** the default recursively creates missing parent directories.
  With `False`, the backend opens the destination without creating or checking
  parents first. A missing parent raises `PathNotFoundError`; an existing parent
  permits the write.
- **S3 family and HTTP:** either value is accepted and ignored; object keys and
  HTTP resources have no directory-parent operations.

**Migration:** SFTP writes now create parents by default, matching Local.
Pass `create_parents=False` to retain SFTP's previous missing-parent failure.
This controls directory creation, not atomic file replacement: a write can still
partially modify a destination, and concurrent filesystem changes remain possible.
Custom `StorageWriteProtocol` backends must accept the keyword on both
`write_from_bytes()` and `write_from_stream()`.

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

### SFTP host-key verification

SFTP/SSH connections check the server's key against the system known-hosts and
`KNOWN_HOSTS_FILE`. `HOST_KEY_POLICY` controls a host whose key is not known:

| Value | Behaviour | Security |
|---|---|---|
| `reject` (default) | Refuse the connection | Verified hosts only |
| `warn` | Log a warning and connect; key not saved | No verification; man-in-the-middle possible on every connection |
| `auto_add` | Accept and remember the key for this client | Trust on first use; man-in-the-middle possible on first contact |

Use `warn` or `auto_add` only on trusted networks or in CI. Any other value,
including the former `ignore`, raises a validation error naming the allowed
values. **Migration:** `ignore` previously behaved as `reject`; remove it or set
`reject`.

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
inputs. Paramiko suppresses some native final-close failures internally;
transport translates escaping errors, not failures hidden by the SDK.

## Filesystem directory semantics

Local and SFTP `mkdir(path, parents=True)` create missing ancestors and accept
an existing directory. With `parents=False`, only the final directory is
created; a missing parent or existing destination raises a storage error.
Recursive creation is not atomic: ancestors already created remain if a later
step fails. SFTP preserves remote relative paths and symlink/`..` traversal
without changing the session's working directory.

Local and SFTP metadata identify directories as `EntryType.DIRECTORY`, following
symlinks through their native stat operation. If an SFTP server omits mode
information, metadata retains the `FILE` fallback; it is not proof of a regular
file. SFTP metadata and listing timestamps are now UTC-aware, matching Local;
missing timestamps remain `None`. Code comparing these timestamps with naive
datetimes must supply a timezone.

Directory removal remains backend-specific: Local removes a directory tree;
SFTP removes an empty directory. This change does not alter removal or
symlink classification in directory listings.

### Exact-path object enumeration

Local/SFTP `list_objects(path, delimiter=None)` returns a selected regular file or
recursively enumerates the files beneath a selected directory. It never matches
similarly named siblings: `reports` does not select `reports-old`. With
`delimiter="/"`, immediate files are returned in `objects` and immediate
directories (including empty ones) in `common_prefixes`. The facade defaults to
`"/"`; backend/protocol calls default to `None`.

Confirmed missing paths return an empty enumeration. A trailing separator still
requires a directory: `file/` and `file/child` raise `StorageError`.
**Local listing migration:** `list_dir(file)` now raises a mapped not-directory
error and `list_dir(missing)` raises `PathNotFoundError`, rather than returning
an empty list.
SFTP applies the same directory-only rule, recovering not-directory failures
when the server reports them as “no such file.”

`max_results` caps objects and common prefixes combined; zero performs no native
I/O. Negative limits and delimiters other than `None` or `"/"` raise `ValueError`.
Results have no sorting or stable limited-subset guarantee. Local result paths
are absolute; SFTP retains relative/absolute POSIX path spelling. Both preserve
aliases and native `link/..` resolution without changing the working directory.

Explicitly selected directory links are followed. Discovered directory links
are not recursively followed, but appear as common prefixes in `"/"` mode;
Windows directory junctions follow the same rule. Valid file links are included,
broken links and special files are omitted, and access/traversal failures raise
rather than returning partial results.

SFTP recovers unavailable listing types with native LSTAT. If required type
information remains unavailable at the root, an entry, a link target or an
ancestor checked after an ambiguous failure, enumeration raises `StorageError`.
Optional size/time fields remain `None` when absent. This does not change the
existing missing-mode fallback in metadata or successful `list_dir` formatting.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from mountainash_transport import StorageFacade

with TemporaryDirectory() as directory:
    path = Path(directory) / "report.csv"
    path.write_bytes(b"data")
    with StorageFacade.for_local() as storage:
        result = storage.list_objects(str(path))
        assert [(entry.path, entry.size) for entry in result.objects] == [(str(path), 4)]
        assert result.common_prefixes == ()
```

## S3 object-prefix enumeration

S3 has objects and literal key prefixes, not directories. A prefix `reports/`
excludes `reports-old` but still selects deeper keys such as `reports/sub/b.csv`.
`reports/a.csv` can select the exact key, `reports/a.csv.bak` and
`reports/a.csv/chunk`; `reports/a.csv/` selects only keys below that slash.
Delimiter `"/"` groups matching keys into common prefixes; it does not turn
selection into exact-file lookup. Slash-ending marker objects remain objects.

Enumeration preserves trailing/repeated slashes and dot-like key components in
both URL and bare bucket/key forms. This corrects earlier URL normalization that
could broaden selection. Other operations' path parsing is unchanged.
Public S3 facade construction now binds the already-connected SDK client without
opening another connection.

S3 limits count objects and common prefixes together, but do not promise early
pagination termination or the filesystem backends' no-I/O zero limit. Existing
service restrictions remain: S3 Express supports slash-terminated prefixes and
the `"/"` delimiter. A missing prefix returns an empty result; missing/denied
buckets raise typed errors.

## Location policy

Pass a `LocationPolicy` (`from mountainash_transport.location import LocationPolicy`)
to `StorageFacade` / `StorageFacade.from_path` / `for_local` to confine what a
facade may touch.

- **`root`** confines local paths: symlinks and `..` are resolved and anything
  outside the root raises `LocationNotAllowed`. A local profile's `ROOT_PATH`
  now confines too (it becomes the root when the policy sets none).
  `MOUNT_SPEC` has been removed. `LocalStorageProfile` is a settings profile
  and needs `[http]`; on a base install use `LocationPolicy(root=...)`.
- **`allowed_remote`** maps a scheme to the hosts (or S3 buckets) it may reach,
  e.g. `{"http": frozenset({"api.example.com"})}`. HTTP is refused unless listed;
  every request is checked, including redirects and auth-flow follow-ups,
  before it is sent.
- **Profile permission.** A caller-supplied SFTP profile permits its own `HOST`;
  an S3-family profile with a `BUCKET` permits only that bucket, and one with no
  `BUCKET` permits any bucket at its endpoint. A profile never widens
  `allowed_remote` for other hosts.
- **`allow_unconfined=True`** opts out explicitly. With no policy, behaviour is
  unchanged.
- Unknown URL schemes are refused with a redacted error (credentials are never
  echoed).

Limits: the check is on the host name, so DNS rebinding is not defended
against, and managed-OAuth token endpoints are not covered by the policy.
See the path-confinement design spec for the full threat model.

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

Licensed under the [Apache License, Version 2.0](LICENSE). See [NOTICE](NOTICE).
