---
title: Backends
---

# Backends

mountainash-transport ships four storage backends: local files, the S3 family (AWS S3, S3 Express One Zone, Cloudflare R2, MinIO and Backblaze B2), SFTP and HTTP(S). Each one is a class composed from per-capability mixins and registered for one or more provider types. The same facade call works on all of them as far as their protocols overlap. Where a store's own semantics differ (directory removal, copy limits, listing cost), the backend keeps the store's behaviour rather than emulating another's.

This page assumes the protocol and registry model from [Architecture: protocols and dispatch](../13-architecture/index.md), the connections from [Leaf connections](../11-connections/index.md#leaf-connections), and the access modes from [Read access modes](../09-read-access-modes/index.md#choosing-an-access-mode). Users who only need to know what a backend can do can read the support matrix and skip the rest.

## Support matrix

<!-- concept:211 -->
The support matrix records which storage protocols each registered backend class implements. It is derived, not maintained by hand: the rows below come from running `issubclass()` against every class in `get_registered_backends()`, one column per protocol.

```python
import mountainash_transport as mt
from mountainash_transport.storage.registry import get_registered_backends

protocols = [
    mt.StorageReadProtocol, mt.StorageWriteProtocol, mt.StorageEnumerateProtocol,
    mt.StorageDeleteProtocol, mt.StorageMetadataProtocol, mt.StorageCopyProtocol,
    mt.StorageDirectoryProtocol, mt.RangedReadProtocol,
]
for provider, cls in sorted(get_registered_backends().items()):
    have = [p.__name__.removeprefix("Storage").removesuffix("Protocol")
            for p in protocols if issubclass(cls, p)]
    print(f"{provider:10} {cls.__name__:22} {' '.join(have)}")
```

Output:

```text
b2         S3StorageBackend       Read Write Enumerate Delete Metadata Copy RangedRead
http       HTTPStorageBackend     Read Write Metadata RangedRead
local      LocalStorageBackend    Read Write Enumerate Delete Metadata Copy Directory
minio      S3StorageBackend       Read Write Enumerate Delete Metadata Copy RangedRead
r2         S3StorageBackend       Read Write Enumerate Delete Metadata Copy RangedRead
s3         S3StorageBackend       Read Write Enumerate Delete Metadata Copy RangedRead
s3express  S3StorageBackend       Read Write Enumerate Delete Metadata Copy RangedRead
sftp       SFTPStorageBackend     Read Write Enumerate Delete Metadata Directory RangedRead
```

| Backend | Provider types | Extra | Read | Write | Enumerate | Delete | Metadata | Copy | Directory | RangedRead |
|---|---|---|---|---|---|---|---|---|---|---|
| `LocalStorageBackend` | `local` | none | yes | yes | yes | yes | yes | yes | yes | no (native handle) |
| `S3StorageBackend` | `s3`, `s3express`, `r2`, `minio`, `b2` | `[s3]` | yes | yes | yes | yes | yes | yes | no | yes |
| `SFTPStorageBackend` | `sftp` | `[sftp]` | yes | yes | yes | yes | yes | no | yes | yes |
| `HTTPStorageBackend` | `http` (also serves `https://`) | `[http]` | yes | yes | no | no | yes | no | no | yes |

The RangedRead column is satisfied structurally. No backend class inherits from `RangedReadProtocol`; the S3, SFTP and HTTP read mixins define `open_ranged`, and that method alone makes `issubclass()` true. Local has no `open_ranged`, and its random access comes from the native file handle instead (see [Local](#local)).

`tests/storage/protocols/test_backend_conformance.py` asserts the same result for the first seven columns. Its expected sets agree with the output above for `local`, `s3`, `r2`, `s3express`, `minio`, `sftp` and `http`. The test has no RangedRead column and no `b2` row; B2 is registered to the same `S3StorageBackend` class as the other S3 flavours, so it has the same capabilities.

At runtime, `StorageFacade.supports(protocol)` answers the same question for one facade, as shown in [Capabilities and supports()](../06-storage-facade/index.md#capabilities-and-supports). The provider types with profiles but no backend (GCS, Azure, FTP, SMB, GitHub) do not appear here; a facade for one raises `BackendNotImplementedError`. The [support matrix and known limits](../../reference/support-matrix.md) reference page collects this table with the documented limits.

## Local

<!-- concept:212 -->
`LocalStorageBackend` (`src/mountainash_transport/storage/backends/local/`) works on the local filesystem with the standard library only, so it is the one backend available on a base install. It implements every protocol except `RangedReadProtocol`. It needs no connection: a facade built with a local storage profile gets a `NullConnection`, one built without a profile gets none, and the backend's `connect()` and `disconnect()` do nothing. Paths are plain filesystem paths or `file://` URLs. A local storage profile's `ROOT_PATH` becomes the declared root for the location policy, as described in [Confining local paths](../08-location-policy/index.md#confining-local-paths). Native `OSError`s are translated at each call: `FileNotFoundError` to `PathNotFoundError`, `PermissionError` to `PermissionDeniedError`, other `OSError`s to `StorageError`.

<!-- concept:169 -->
### Native local handles

A random-access read on local storage returns a reader over the native file object from `open(path, "rb")`. The facade does not wrap it in a ranged reader or an extra buffer, so the handle keeps whatever methods the native file has, including `seek`, `tell` and `fileno`. OS errors raised later by those methods are translated in the same way as errors at open time.

```python
import os, tempfile
from mountainash_transport import PathNotFoundError, RangedReadProtocol, StorageFacade

root = tempfile.mkdtemp()
with StorageFacade.for_local() as local:
    path = os.path.join(root, "data", "a.bin")
    local.write(path, b"0123456789")                 # creates data/ by default
    print(local.supports(RangedReadProtocol))         # -> False

    with local.read_stream(path, access="random") as fh:
        print(fh.seekable(), fh.fileno() > 0)        # native handle methods
        fh.seek(-3, os.SEEK_END)
        print(fh.read())                              # -> b'789'

    local.rmdir(os.path.join(root, "data"))           # removes the file too
    print(os.path.exists(path))                       # -> False

    try:
        local.read(path)
    except PathNotFoundError as exc:
        print(type(exc).__name__, "<-", type(exc.__cause__).__name__)
```

Output:

```text
False
True True
b'789'
False
PathNotFoundError <- FileNotFoundError
```

A `RangePolicy` has no effect on local reads, because there is no range cache to tune.

## S3 family

<!-- concept:213 -->
`S3StorageBackend` (`src/mountainash_transport/storage/backends/s3/`) wraps a boto3 client supplied by `S3Connection`. It implements read, write, enumerate, delete, metadata, copy and ranged read. Object stores have no directories, so it does not implement `StorageDirectoryProtocol`, and `create_parents` is accepted and ignored on writes. Paths are `s3://bucket/key` or `bucket/key`.

Each operation maps to one boto3 call or paginator. `write` uses `put_object`; `write_stream` uses `upload_fileobj`, which switches to multipart upload for large streams. Sequential reads return the `get_object` body as a forward-only stream. Ranged reads issue a `head_object` for the size and ETag, then one `get_object` with a `Range` header per cache miss, sending `IfMatch` with the strong ETag so that a change to the object raises `ObjectChangedError` instead of mixing two versions.

The example runs against a local S3-compatible endpoint. The server bootstrapping lines are omitted; `endpoint` is its URL and the bucket `reports` already exists.

```python
from mountainash_auth_client import IAMAuthProfile
from mountainash_transport import PathNotFoundError, RangedReadProtocol, StorageFacade
from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile

profile = S3StorageProfile(FLAVOR="minio", ENDPOINT_URL=endpoint, BUCKET="reports", REGION="us-east-1")
auth = IAMAuthProfile(ACCESS_KEY_ID="x", SECRET_ACCESS_KEY="y")

with StorageFacade.from_path("s3://reports/", profile, auth_profile=auth) as s3:
    for name in ("a.csv", "b.csv", "c.csv"):
        s3.write(f"s3://reports/daily/{name}", b"0123456789")

    print(s3.supports(RangedReadProtocol))                 # -> True
    with s3.read_stream("s3://reports/daily/a.csv", access="random") as fh:
        fh.seek(-3, 2)
        print(fh.read())                                   # -> b'789'

    result = s3.list_objects("s3://reports/daily/", max_results=2)
    print([e.name for e in result.objects])

    s3.copy("s3://reports/daily/a.csv", "s3://reports/archive/a.csv")
    print(s3.exists("s3://reports/archive/a.csv"))         # -> True

    try:
        s3.read("s3://reports/missing.csv")
    except PathNotFoundError as exc:
        print(type(exc).__name__, exc, "<-", type(exc.__cause__).__name__)
```

Output:

```text
True
b'789'
['a.csv', 'b.csv']
True
PathNotFoundError s3://reports/missing.csv <- NoSuchKey
```

The credentials come from an `IAMAuthProfile` owned by mountainash-auth-client, not from the storage profile; see [Credentials come from auth-client](../02-mountainash-ecosystem/index.md#credentials-come-from-auth-client).

<!-- concept:214 -->
### One class, five provider types

`S3StorageBackend` is registered with five stacked `@register_storage_backend` decorators, for `S3`, `S3EXPRESS`, `R2`, `MINIO` and `B2`. The registry therefore returns the same class for `s3://`, `s3express://`, `r2://`, `minio://` and `b2://` paths, as the support matrix output shows. The differences between the services (endpoint URL, `use_ssl` default, `region_name="auto"` for R2, addressing style) are settled by the storage profile's `FLAVOR` field (`aws`, `express`, `r2`, `minio` or `b2`) and applied by `S3Connection` when it builds the boto3 client, as described in [Provider profiles](../05-storage-profiles/index.md#provider-profiles). The backend code never branches on the flavour. The names `R2StorageBackend`, `S3ExpressStorageBackend`, `MinIOStorageBackend` and `B2StorageBackend` remain importable from the backend package as aliases of `S3StorageBackend`.

## SFTP

<!-- concept:215 -->
`SFTPStorageBackend` (`src/mountainash_transport/storage/backends/sftp/`) uses a paramiko `SFTPClient` from an `SFTPConnection`, which wraps an `SSHConnection` (see [Leaf connections](../11-connections/index.md#leaf-connections)). It implements read, write, enumerate, delete, metadata, directory and ranged read. It does not implement `StorageCopyProtocol`, because SFTP version 3 has no server-side copy; `copy_between` moves data through the client instead. Paths are remote paths, or `sftp://host[:port]/path` URLs whose host and port must match the connected profile's `HOST` and `PORT`, otherwise the call raises `LocationNotAllowed`.

Sequential reads pull from the remote file on demand without prefetching. Ranged reads open one remote handle, read its size from `stat`, and serve each range with `seek` and `read` on that handle; there is no version pinning, so a file changed during a random read is not detected. Enumeration accepts only `None` or `"/"` as the delimiter. The SFTP tests replace the paramiko client with in-process fakes (`tests/storage/backends/test_sftp.py`) or with a fake whose calls act on a temporary directory (`tests/storage/backends/test_directory_semantics.py`); this page has no SFTP example because it needs a running SFTP server.

## HTTP

<!-- concept:216 -->
`HTTPStorageBackend` (`src/mountainash_transport/storage/backends/http/`) sends every request through the `HttpRequestEngine` described in [Making requests](../12-http-engine/index.md#making-requests), so the engine's retry, timeout, redirect and redaction policy and its auth strategy apply to storage calls too. It implements read (`GET`), write (`PUT`), metadata (`HEAD`) and ranged read. It is the only backend that accepts an `auth_strategy`, which carries the managed OAuth2 token flow, and the only one that receives the facade's location check per request, so redirects are checked against the policy as well.

Ranged reads probe the server with `Range: bytes=0-0` instead of relying on `HEAD` or `Accept-Ranges`. A server that answers `200` instead of `206`, or returns an encoded (for example gzip) representation, raises `RangeNotSupportedError`. Python's built-in `http.server` does not honour `Range`, which makes the refusal easy to see. The server bootstrapping lines are omitted; `base` is its URL.

```python
from mountainash_transport import (
    RangeNotSupportedError, StorageEnumerateProtocol, StorageFacade,
)

url = f"{base}/report.csv"
with StorageFacade.from_path(url) as web:
    print(web.read(url))
    print(web.get_size(url))
    print(web.supports(StorageEnumerateProtocol))     # -> False
    try:
        web.read_stream(url, access="random")
    except RangeNotSupportedError as exc:
        print(type(exc).__name__, exc)
```

Output:

```text
b'id,value\n1,42\n'
14
False
RangeNotSupportedError Expected 206, received 200
```

With no storage profile, the facade creates a default `HTTPStorageProfile` and its connection, so a bare URL is enough. Range probes send `Accept-Encoding: identity` and pin later ranges to a strong ETag with `If-Match` when the server supplies one.

## Read plumbing

The facade returns two kinds of remote read stream. Sequential reads use forward-only adapters over the SDK's native stream. Random reads use `RangedReader` over the backend's `RangedSource`. Both are defined in private modules under `src/mountainash_transport/_core/`; callers see only a binary file object. The user-facing choice between them is in [Choosing an access mode](../09-read-access-modes/index.md#choosing-an-access-mode).

<!-- concept:164 -->
### RangedReader

`RangedReader` (`_core/ranged_io.py`) is an `io.RawIOBase` over a `RangedSource`. It is seekable, and seeking only moves a position: no network request happens until `read()`. Reads go through an fsspec cache chosen by the `RangePolicy` (`readahead`, `blockcache`, `bytes` or `none`, with `block_size` and, for `blockcache`, `max_blocks`), which calls the source's `fetch(start, end)` for the bytes it lacks. A fetch that returns fewer bytes than requested raises `StorageError`. Closing the reader calls the source's `on_close`, which is how the SFTP backend closes its remote handle. Tuning is described in [Range tuning](../09-read-access-modes/index.md#range-tuning).

!!! note
    `RangedReader` reads through fsspec's cache classes using their internal `_fetch` method rather than a documented fsspec API. An fsspec release that changes that method would affect random reads on S3, SFTP and HTTP. The `[http]` extra constrains fsspec to `>=2026.6.0,<2027`. See the [support matrix and known limits](../../reference/support-matrix.md).

<!-- concept:165 -->
### Sequential stream adapters

`ForwardOnlyReader` and `IterBytesReader` (`_core/sequential_io.py`) adapt a native source into an `io.RawIOBase` that the backends wrap in `io.BufferedReader`. `ForwardOnlyReader` takes a sized `read` callable and a `close` callable; S3 passes the `get_object` body's methods and SFTP the remote file handle's. `IterBytesReader` takes an iterator of chunks, which the HTTP backend uses for `httpx` streaming responses, and holds at most one incoming chunk. Both translate errors raised during `read` or `close` with the backend's error mapping, so a failure partway through a stream surfaces as a `StorageError` subclass with the native exception as its cause. Neither reads ahead of the caller.

## Where backends differ

<!-- concept:217 -->
The protocols fix method names and error types. Some behaviour is left to the store, and the backends keep the store's semantics rather than emulating one another.

!!! warning "Directory removal"
    `rmdir` on local storage calls `shutil.rmtree`, so it removes the directory and everything in it. On SFTP it calls the server's `rmdir`, which removes only an empty directory and fails on a non-empty one. S3 and HTTP have no `rmdir`. Code that must behave the same on both should empty the directory first. See [Deleting, directories and parent creation](../07-file-operations/index.md#deleting-directories-and-parent-creation) and the [support matrix and known limits](../../reference/support-matrix.md).

!!! warning "SFTP write buffering"
    The SFTP backend's `write_from_stream` reads the whole source stream into memory and then writes it as bytes. This applies to `write_stream`, to `write` with a transform pipeline, and to `copy_between` with an SFTP destination. Memory use grows with the payload. See the [support matrix and known limits](../../reference/support-matrix.md).

!!! warning "S3 copy is one request"
    `copy()` on the S3 backend makes a single `copy_object` call with no multipart fallback. It is bounded by the provider's single-request copy limit (AWS [documents 5 GB](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CopyObject.html) for `CopyObject`), and larger objects fail. To copy such an object, stream it: `read_stream` followed by `write_stream` uploads through boto3's multipart-capable `upload_fileobj`. `copy_between` streams the same way unless both facades share one profile object, in which case it calls `copy()`. See the [support matrix and known limits](../../reference/support-matrix.md).

!!! warning "S3 listing with a limit"
    `list_objects(..., max_results=n)` on S3 pages through every result under the prefix and then truncates to `n` (objects first, then common prefixes). The number of requests depends on the size of the prefix, not on `n`. The SFTP backend stops as soon as it has `n` entries. See the [support matrix and known limits](../../reference/support-matrix.md).

Other differences follow from the stores themselves. Deleting a missing local or SFTP file raises `PathNotFoundError`; deleting a missing S3 key succeeds. Ranged reads are pinned to an ETag on S3 and HTTP but not on SFTP. The `create_parents` option on writes applies to local and SFTP only.

<!-- concept:219 -->
### Backend error mapping

Each backend package has a private `_helpers.py` with a `_mapped(path)` context manager that its mixins place around every native call. It turns the SDK's exception into a `StorageError` subclass and raises it `from` the original, so the native error stays available as `__cause__`. The examples above show `FileNotFoundError` becoming `PathNotFoundError` on local storage and botocore's `NoSuchKey` doing the same on S3.

| Native condition | Local | S3 (botocore) | SFTP (paramiko) | HTTP (engine) |
|---|---|---|---|---|
| Missing | `FileNotFoundError` | `NoSuchKey`, `NoSuchBucket`, 404 | `ENOENT` | `HttpNotFoundError` |
| Bad or expired credentials | n/a | `InvalidAccessKeyId`, `ExpiredToken`, 401 and others | paramiko authentication failure | `HttpAuthenticationError` |
| Access denied | `PermissionError` | `AccessDenied`, 403 | `EACCES`, `EPERM` | `HttpForbiddenError` |
| Network or timeout | `ConnectionError`, `TimeoutError` | botocore connection errors, `RequestTimeout` | SSH and socket errors | connection and timeout errors |
| Object changed | n/a | `PreconditionFailed`, 412 | n/a | 412 |

These map to `PathNotFoundError`, `AuthenticationError`, `PermissionDeniedError`, `StorageConnectionError` and `ObjectChangedError` in that row order; anything else from the SDK becomes a plain `StorageError`. Errors that describe the caller's input (botocore parameter validation, invalid URLs, the caller's own stream failing) are not translated. The HTTP mapping also removes user information from URLs in messages. The exception hierarchy itself is described in [Errors](../03-installation/index.md#errors).
