---
title: Installation and the package surface
---

# Installation and the package surface

`mountainash-transport` installs as a small base package with optional extras. The base install reads and writes local files with no third-party dependency beyond `typing-extensions`. Each extra adds what one group of endpoints needs: HTTP and storage profiles, S3, SFTP, GPG encryption, OAuth 1.0a signing. The package root exposes the public API lazily, so importing it stays cheap, and a feature whose extra is missing fails with an error that names the extra.

This page assumes Python 3.12 or later and the vocabulary of [What transport does](../01-what-transport-does/index.md).

## Base install and extras

<!-- concept:113 -->

### The base install

The base install declares one runtime dependency, `typing-extensions`. It covers:

- `StorageFacade` on local paths (bare paths and `file://` URLs), with every local operation: read, write, streams, listing, metadata, delete, copy and directories;
- the `Gzip` transform, `Pipeline` and suffix inference with `infer_pipeline`;
- `LocationPolicy` from `mountainash_transport.location`, for confining local paths to a root;
- the error classes, `RetryPolicy` and the other HTTP policy and error names, which are importable but do nothing on their own.

This works on a base install, in an environment that contains only `mountainash-transport` and `typing-extensions`:

```python
import tempfile
from pathlib import Path

from mountainash_transport import Gzip, StorageFacade
from mountainash_transport.location import LocationPolicy

with tempfile.TemporaryDirectory() as root:
    path = str(Path(root) / "notes.txt.gz")
    with StorageFacade.for_local(policy=LocationPolicy(root=root)) as storage:
        storage.write(path, b"base install only\n", pipeline=Gzip())
        print(storage.read(path, infer=True))
```

Output:

```text
b'base install only\n'
```

Everything else needs at least the `[http]` extra: remote storage, storage profiles (including `LocalStorageProfile`), named profiles, connections, `StoragePath` and the HTTP request engine.

The base install is a tested contract. `tests/test_slim_install.py` runs local operations in a subprocess that blocks every import outside the standard library, `typing-extensions` and `mountainash_transport`. Every backend module must import under that block, so a backend that imports its SDK at module level fails the test. Maintainers adding a backend import SDKs inside the functions that use them; see [Tests that guard the contracts](../15-maintaining/index.md#tests-that-guard-the-contracts).

<!-- concept:114 -->

### Optional extras

| Extra | Adds | Enables |
|---|---|---|
| `[http]` | `mountainash-settings`, `mountainash-auth-client`, `pydantic`, `universal_pathlib`, `httpx`, `fsspec` | HTTP and HTTPS storage, storage profiles, `resolve_storage`, connections, `StoragePath`, the HTTP request engine |
| `[s3]` | `[http]` plus `boto3`, `s3fs`, `aiobotocore`, `minio` | The S3 backend: AWS S3, S3 Express, R2, MinIO, B2 |
| `[sftp]` | `[http]` plus `paramiko`, `smart-open[ssh]` | The SFTP backend, SSH connections and SSH tunnels |
| `[encryption]` | `python-gnupg` | The `GPG` transform |
| `[oauth1]` | `[http]` plus `authlib` | OAuth 1.0a request signing |
| `[gcs]`, `[azure]` | `[http]` plus the Google Cloud Storage or Azure SDKs | SDKs only; transport has no GCS or Azure backend yet |
| `[all]` | Everything above | |

Every backend extra includes `[http]`, because storage profiles and credentials come from `mountainash-settings` and `mountainash-auth-client` (see [The Mountainash packages](../02-mountainash-ecosystem/index.md#the-mountainash-packages)). `[encryption]` is the exception: GPG works on local files without `[http]`. The `[gcs]` and `[azure]` extras exist for the GCS and Azure storage profiles, but opening a facade for `gs://` or `azure://` paths still raises `BackendNotImplementedError` (see [Specs, the registry and settings-only providers](../05-storage-profiles/index.md#specs-the-registry-and-settings-only-providers)).

The distribution name is `mountainash-transport` and the import name is `mountainash_transport`. Version 0.1.0 is a development baseline, and until the sibling packages are published, they are installed from development checkouts placed side by side. With `uv` and checkouts in one parent directory:

```bash
uv pip install ./mountainash-settings ./mountainash-auth-client "./mountainash-transport[s3,sftp]"
```

With `pip`, from inside a transport checkout:

```bash
python -m pip install -e ".[s3]"
```

Choose extras by the endpoints the application reaches. A tool that reads S3 and writes local files needs `[s3]`, and one that also decrypts GPG files needs `[s3,encryption]`. Packages built on transport declare matching extras that pass through to it. `mountainash-files[s3]`, for example, installs `mountainash-transport[s3]`.

<!-- concept:116 -->

### The lazy package root

`mountainash_transport` resolves its public names on first use ([PEP 562](https://peps.python.org/pep-0562/) module `__getattr__`). `import mountainash_transport` loads almost nothing, and `from mountainash_transport import StorageFacade` imports only the facade and its dependencies. Local-only code therefore never imports `httpx` or the cloud SDKs, even when they are installed.

```python
import sys

import mountainash_transport

print("facade loaded:", "mountainash_transport.storage.facade" in sys.modules)
StorageFacade = mountainash_transport.StorageFacade  # first access imports the module
print("facade loaded:", "mountainash_transport.storage.facade" in sys.modules)
print("httpx loaded: ", "httpx" in sys.modules)
```

Output:

```text
facade loaded: False
facade loaded: True
httpx loaded:  False
```

On a base install, accessing a root name that needs `[http]` raises `MissingExtraError` at that point, not at `import mountainash_transport`:

```python
import mountainash_transport
from mountainash_transport import MissingExtraError

for name in ("StorageFacade", "Gzip", "infer_pipeline", "RetryPolicy", "HttpNotFoundError",
             "StoragePath", "resolve_storage", "create_connection", "HttpRequestEngine"):
    try:
        getattr(mountainash_transport, name)
    except MissingExtraError as error:
        print(f"{name:18} needs [{error.extra}]")
    else:
        print(f"{name:18} available")
```

Output on a base install:

```text
StorageFacade      available
Gzip               available
infer_pipeline     available
RetryPolicy        available
HttpNotFoundError  available
StoragePath        needs [http]
resolve_storage    needs [http]
create_connection  needs [http]
HttpRequestEngine  needs [http]
```

The root also binds `storage`, a convenience factory that returns a `StorageFacade` for a provider type (see [Creating a facade](../06-storage-facade/index.md#creating-a-facade)). Because of that binding, `mountainash_transport.storage` is the factory function, not the `storage` subpackage. Import submodules with `from` imports, for example `from mountainash_transport.storage.facade import StorageFacade`, rather than `import mountainash_transport.storage.backends as backends`, which raises `ImportError`. The lazy-export table is in `src/mountainash_transport/__init__.py`.

## Errors

<!-- concept:218 -->

### The error families

Transport translates the failures of the libraries it wraps into its own exceptions, so callers catch transport types instead of `OSError`, `botocore`, `paramiko` or `httpx` exceptions. The native exception stays attached as the cause for debugging, except where HTTP credential redaction removes it. There are three families, one per layer, and they do not share a base class:

| Family | Root class | Raised by | Main subclasses |
|---|---|---|---|
| Storage | `StorageError` | `StorageFacade`, backends, profiles, location policy | `PathNotFoundError`; `AuthenticationError` and its subclass `PermissionDeniedError`; `StorageConnectionError`; `UnsupportedOperationError`; `BackendNotImplementedError`; `MissingExtraError`; `TransformError`; `RangeNotSupportedError`; `ObjectChangedError`; `ProfileResolutionError` and its subclass `ProfileNotFoundError`; `LocationNotAllowed` |
| Connections | `TransportConnectionError` | `create_connection`, SSH, SFTP, S3 and tunnel connections | `ConnectionTimeoutError`, `UnsupportedAuthProfileError` |
| HTTP engine | `HttpTransportError` | `HttpRequestEngine` | `HttpResponseError` with client (4xx) and server (5xx) subclasses such as `HttpNotFoundError` and `HttpServiceUnavailableError`; `HttpConnectionError`; `HttpTimeoutError`; `HttpRedirectError` and others |

Code that uses `StorageFacade` mostly sees the storage family. The HTTP storage backend translates HTTP failures into storage errors, so a missing URL read through a facade raises `PathNotFoundError`, not `HttpNotFoundError`. The connection and HTTP families appear when you use `create_connection` or `HttpRequestEngine` directly, and connection errors can also surface while a facade is being constructed.

Each storage error marks a distinct condition. `PathNotFoundError` means established absence. `UnsupportedOperationError` means the backend lacks the capability, and is raised before any I/O. `BackendNotImplementedError` means the provider has a profile but no backend:

```python
import tempfile
from pathlib import Path

from mountainash_transport import (
    BackendNotImplementedError, PathNotFoundError, StorageError, StorageFacade,
    UnsupportedOperationError,
)

with tempfile.TemporaryDirectory() as root, StorageFacade.for_local() as storage:
    try:
        storage.read(str(Path(root) / "missing.csv"))
    except PathNotFoundError as error:
        print("PathNotFoundError, a StorageError:", isinstance(error, StorageError))

with StorageFacade.from_path("https://files.example.com/a.csv") as storage:
    try:
        storage.delete("https://files.example.com/a.csv")  # refused before any request
    except UnsupportedOperationError as error:
        print("UnsupportedOperationError:", error)

try:
    StorageFacade.from_path("gs://bucket/key.csv")
except BackendNotImplementedError as error:
    print("BackendNotImplementedError:", error)
```

Output:

```text
PathNotFoundError, a StorageError: True
UnsupportedOperationError: HTTPStorageBackend does not support 'delete'
BackendNotImplementedError: The 'gcs' storage provider is not yet implemented. Implemented providers: ['b2', 'http', 'local', 'minio', 'r2', 's3', 's3express', 'sftp']
```

`PermissionDeniedError` subclasses `AuthenticationError`, so a handler for authentication failures also catches denials. To tell them apart, catch `PermissionDeniedError` first. A denial does not prove that the credentials are valid. Caller mistakes, such as invalid arguments, are not translated and keep their native types (`ValueError`, `TypeError`). How each backend maps its native errors is described in [Where backends differ](../14-backends/index.md#where-backends-differ).

<!-- concept:115 -->

### MissingExtraError

`MissingExtraError` is raised when a feature needs a package from the `[http]` stack (`mountainash-settings`, `mountainash-auth-client`, `pydantic`, `universal_pathlib`, `httpx` or `fsspec`) that is not installed. It subclasses both `StorageError` and `ImportError`, so existing `except ImportError` handlers still catch it. Its `extra` attribute names the extra to install and `feature` names what needed it. On a base install:

```python
from mountainash_transport import MissingExtraError, StorageFacade

try:
    StorageFacade.from_path("https://example.com/data.csv")
except MissingExtraError as error:
    print(type(error).__name__, "| extra:", error.extra, "| feature:", error.feature)
    print(error)
    print("also an ImportError:", isinstance(error, ImportError))
```

Output:

```text
MissingExtraError | extra: http | feature: storage profiles
The [http] extra is required for storage profiles: pip install 'mountainash-transport[http]'
also an ImportError: True
```

!!! warning "`MissingExtraError` covers the `[http]` stack only"
    A missing backend SDK is not reported as `MissingExtraError`. A missing `boto3` or `paramiko` raises `TransportConnectionError` when the S3 or SSH connection is created, and using `GPG` without `[encryption]` raises a plain `ImportError`. Each message names the extra to install. Catch `TransportConnectionError` and `ImportError` as well as `MissingExtraError` when probing for optional backends. See the [support matrix and known limits](../../reference/support-matrix.md).

This code ran in an environment with `[http]` but without `[s3]`:

```python
from mountainash_auth_client import IAMAuthProfile

from mountainash_transport import MissingExtraError, StorageFacade
from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile

profile = S3StorageProfile(FLAVOR="aws", REGION="ap-southeast-2", BUCKET="reports")
auth = IAMAuthProfile(ACCESS_KEY_ID="example-access-key", SECRET_ACCESS_KEY="example-secret")
try:
    StorageFacade.from_path("s3://reports/sales.csv", profile, auth_profile=auth)
except Exception as error:
    print(type(error).__name__)
    print("is MissingExtraError:", isinstance(error, MissingExtraError))
    print("is ImportError:", isinstance(error, ImportError))
    print("names the extra:", "mountainash-transport[s3]" in str(error))
```

Output:

```text
TransportConnectionError
is MissingExtraError: False
is ImportError: False
names the extra: True
```

The translation is implemented in `src/mountainash_transport/_core/extras.py`. Only a `ModuleNotFoundError` for a top-level `[http]`-stack module is converted; any other import failure is re-raised unchanged.
